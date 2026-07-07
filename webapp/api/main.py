"""FastAPI backend — wraps the Disclosure Review Kit engine."""
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import io
import json
import re
import os
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
import urllib.error
import requests
import re
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

try:
    import box_client as _box
    _BOX_AVAILABLE = True
except Exception:
    _BOX_AVAILABLE = False

import glob as _glob
import shutil as _shutil

def _find_libreoffice() -> str | None:
    """Return a usable LibreOffice executable path, or None if not found."""
    # Common command names (Linux / Railway Docker)
    for cmd in ("libreoffice", "soffice"):
        if _shutil.which(cmd):
            return cmd
    # Windows installation paths
    if sys.platform == "win32":
        for pattern in (
            r"C:\Program Files\LibreOffice*\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice*\program\soffice.exe",
        ):
            matches = _glob.glob(pattern)
            if matches:
                return matches[0]
    # macOS
    mac = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.isfile(mac):
        return mac
    return None

app = FastAPI(title="Disclosure Review Kit API")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"[ERROR] Unhandled exception on {request.url}:\n{tb}", file=sys.stderr)
    return JSONResponse(status_code=500, content={"detail": str(exc), "traceback": tb[-2000:]})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
HERE = Path(__file__).parent
KIT_DIR = (HERE / "../../disclosure-review-kit").resolve()
OUTPUT_DIR = KIT_DIR / "output"

# ASX public token (same one asx.com.au uses)
ASX_TOKEN = "83ff96335c2d45a094df02a206a39ff4"
ASX_FILE_URL = "https://asx.api.markitdigital.com/asx-research/1.0/file/{key}"
ASX_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/pdf",
    "Origin": "https://www.asx.com.au",
    "Referer": "https://www.asx.com.au/",
    "Authorization": f"Bearer {ASX_TOKEN}",
}


@app.get("/api/health")
def health():
    return {"ok": True, "test": "reload-working", "kitDir": str(KIT_DIR)}


_companies_cache: list = []
_companies_cache_time: float = 0.0
_COMPANIES_TTL: float = 86400  # 24 hours
_COMPANIES_DISK_CACHE = HERE / "asx_companies_cache.json"


def _load_companies_from_disk():
    """Populate in-memory cache from the bundled disk cache (written at Docker build time)."""
    global _companies_cache, _companies_cache_time
    if not _COMPANIES_DISK_CACHE.exists():
        return
    try:
        data = json.loads(_COMPANIES_DISK_CACHE.read_text())
        companies = data.get("companies") if isinstance(data, dict) else data
        if isinstance(companies, list) and companies:
            _companies_cache = companies
            disk_ts = data.get("ts", 0) if isinstance(data, dict) else 0
            # When ts=0 (Docker-build snapshot), treat as fetched ~23h ago so the
            # first request returns immediately instead of blocking on a network call.
            # This causes the TTL to expire ~1h later, triggering a live refresh then.
            if disk_ts == 0:
                disk_ts = time.time() - (_COMPANIES_TTL - 3600)
            _companies_cache_time = disk_ts
            print(f"[asx] Loaded {len(companies)} companies from disk cache", file=sys.stderr)
    except Exception as e:
        print(f"[asx] Could not load disk cache: {e}", file=sys.stderr)


_load_companies_from_disk()


@app.get("/api/asx/companies")
def get_asx_companies():
    global _companies_cache, _companies_cache_time
    now = time.time()
    if _companies_cache and (now - _companies_cache_time) < _COMPANIES_TTL:
        return {"companies": _companies_cache}

    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[asx] Company list fetch failed: {e}", file=sys.stderr)
        if _companies_cache:
            # Return disk/stale cache so the combobox still works
            return {"companies": _companies_cache}
        raise HTTPException(502, f"Could not fetch ASX company list: {str(e)}")

    companies = []
    rows = list(csv.reader(content.splitlines()))
    # Row 0: metadata, Row 1: blank, Row 2: column headers, Row 3+: data
    for row in rows[3:]:
        if len(row) >= 2:
            name = row[0].strip()
            code = row[1].strip().upper()
            if code and name:
                companies.append({"code": code, "name": name})

    if companies:
        _companies_cache = companies
        _companies_cache_time = now
        # Persist to disk so the next cold start doesn't need a network request
        try:
            _COMPANIES_DISK_CACHE.write_text(json.dumps({"companies": companies, "ts": now}))
        except Exception as e:
            print(f"[asx] Could not write disk cache: {e}", file=sys.stderr)

    return {"companies": companies}


def _fetch_asx_report(ticker: str, report_type: str) -> bytes:
    """Fetch the latest annual or half-year report PDF from ASX for a given ticker."""
    t = ticker.upper().strip()
    if not t:
        raise HTTPException(400, "ASX ticker code is required.")
        
    # Resolve XID using the kit's asx_history module
    sys.path.insert(0, str(KIT_DIR / "lib"))
    import asx_history

    xid = asx_history.resolve_xid(t)
    if not xid:
        raise HTTPException(404, f"Could not resolve ASX ticker '{t}'.")

    # Fetch recent announcements (looking back 2 years / 24 months to find the latest report)
    cutoff = datetime.now(timezone.utc) - timedelta(days=2 * 365)
    try:
        raw_items = asx_history.fetch_paginated(xid, cutoff)
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch announcements from ASX: {str(e)}")

    # Find the latest matching report announcement
    matching_item = None
    search_type = report_type.lower()
    if search_type == "auto":
        search_type = "annual"  # Default to annual report when fetching automatically

    for item in raw_items:
        headline = (item.get("headline") or "").lower()
        types = ", ".join(item.get("announcementTypes") or []) or item.get("announcementType") or ""
        types = types.lower()

        is_match = False
        if search_type == "annual":
            if "annual report" in headline or "appendix 4e" in headline or "annual financial" in headline or "annual report" in types or "appendix 4e" in types:
                is_match = True
        elif search_type in ("interim", "half-year", "half_year"):
            if "half yearly" in headline or "half-year" in headline or "appendix 4d" in headline or "interim report" in headline or "half yearly" in types or "half-year" in types or "appendix 4d" in types or "interim report" in types:
                is_match = True

        if is_match:
            matching_item = item
            break

    if not matching_item:
        raise HTTPException(404, f"Could not find any latest {search_type} report announcement for ticker '{t}'.")

    doc_key = matching_item.get("documentKey")
    if not doc_key:
        raise HTTPException(404, f"Found announcement '{matching_item.get('headline')}', but it has no document key.")

    # Download the PDF from the ASX file service
    url = ASX_FILE_URL.format(key=doc_key)
    req = urllib.request.Request(url, headers=ASX_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            pdf_data = r.read()
        if pdf_data[:5] != b"%PDF-":
            raise HTTPException(502, "The downloaded file from ASX is not a valid PDF.")
        return pdf_data
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code, f"ASX API returned {e.code} when downloading report PDF.")
    except urllib.error.URLError as e:
        raise HTTPException(502, f"Could not reach ASX API to download PDF: {e.reason}")


@app.post("/api/review")
async def review(
    file: UploadFile | None = File(default=None),
    ticker: str = Form(default=""),
    report_type: str = Form(default="auto"),
    materiality: str = Form(default=""),
    no_asx: str = Form(default="false"),
    download_asx: str = Form(default="false"),
    as_of_period: str = Form(default="false"),
    box_file_id: str = Form(default=""),
    user_id: str = Form(default=""),
    display_name: str = Form(default=""),
):
    """Run review.py on a PDF and return findings.json. Does NOT build the Word report yet."""
    if not file and not ticker.strip() and not box_file_id.strip():
        raise HTTPException(400, "Please upload a PDF file, specify an ASX ticker, or pick a file from Box.")

    # Determine source and fetch PDF bytes
    pdf_bytes = None
    report_file_label = ""
    box_folder_id = ""
    if box_file_id.strip():
        source = "box"
        if not _BOX_AVAILABLE or not _box.is_configured():
            raise HTTPException(503, "Box is not configured.")
        try:
            pdf_bytes, box_filename = _box.download_file(box_file_id.strip())
            report_file_label = box_filename
            box_folder_id = _box.get_file_parent_folder(box_file_id.strip()) or ""
        except Exception as e:
            raise HTTPException(502, f"Failed to download from Box: {str(e)}")

    elif file:
        source = "upload"
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(400, "Please upload a PDF file.")
        pdf_bytes = await file.read()
        report_file_label = file.filename or "upload"
    else:
        source = "asx"
        pdf_bytes = _fetch_asx_report(ticker, report_type)
        report_file_label = f"ASX:{ticker.strip().upper()}"

    # Create pending audit entry before running subprocess (captures failed runs too)
    audit_id = hashlib.sha256(f"{time.time()}{user_id}".encode()).hexdigest()[:12]
    _append_audit({
        "id": audit_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "userId": user_id.strip() or "anonymous",
        "displayName": display_name.strip() or "Anonymous",
        "ticker": ticker.strip().upper() or None,
        "entity": None,
        "reportType": report_type,
        "source": source,
        "reportFile": report_file_label,
        "asxEnabled": no_asx.lower() != "true",
        "downloadAsx": download_asx.lower() == "true",
        "outcome": "pending",
        "errorMessage": None,
        "docxName": None,
        "docxGeneratedAt": None,
        "boxFolderId": box_folder_id or None,
    })

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        pdf_path = tmp.name

    try:
        cmd = [sys.executable, "lib/review.py", "--report", pdf_path]
        if ticker.strip():
            cmd += ["--ticker", ticker.strip()]
        if report_type and report_type != "auto":
            cmd += ["--type", report_type]
        if materiality.strip():
            cmd += ["--materiality", materiality.strip()]
        if no_asx.lower() == "true":
            cmd += ["--no-asx"]
        if download_asx.lower() == "true":
            cmd += ["--download-asx"]
        if as_of_period.lower() == "true":
            cmd += ["--as-of-period"]

        # Downloading PDFs locally for a large company can take several minutes.
        review_timeout = 600 if download_asx.lower() == "true" else 300
        try:
            result = subprocess.run(cmd, cwd=str(KIT_DIR), capture_output=True, text=True, timeout=review_timeout)
        except subprocess.TimeoutExpired:
            mins = review_timeout // 60
            raise HTTPException(500, f"Review timed out after {mins} minutes. Try again with 'Download announcement PDFs locally' unchecked, or with ASX disabled.")

        if result.returncode != 0:
            err_out = (result.stderr or result.stdout or "no output captured").strip()
            _update_audit(audit_id, {"outcome": "error", "errorMessage": err_out[-300:]})
            raise HTTPException(500, f"Review failed (exit {result.returncode}):\n{err_out[-2000:]}")

        findings_path = OUTPUT_DIR / "findings.json"
        if not findings_path.exists():
            _update_audit(audit_id, {"outcome": "error", "errorMessage": "findings.json not produced"})
            raise HTTPException(500, "findings.json was not produced.")

        with open(findings_path, encoding="utf-8") as f:
            findings = json.load(f)

        _update_audit(audit_id, {"outcome": "success", "entity": findings.get("entity", "")})
        return {"findings": findings, "auditId": audit_id}

    finally:
        try:
            os.unlink(pdf_path)
        except OSError:
            pass


@app.post("/api/generate")
async def generate(body: dict):
    """Build the Word report from the last findings.json, filtered to selected announcements."""
    selected_keys = set(body.get("selectedKeys", []))
    audit_id = body.get("auditId", "")

    findings_path = OUTPUT_DIR / "findings.json"
    if not findings_path.exists():
        raise HTTPException(400, "No findings.json found — run a review first.")

    with open(findings_path, encoding="utf-8") as f:
        findings = json.load(f)

    # Filter ASX items to selected keys (empty selectedKeys = include all)
    if selected_keys:
        findings["asx"]["items"] = [
            item for item in findings["asx"]["items"]
            if item.get("documentKey") in selected_keys
        ]
        findings["asx"]["count"] = len(findings["asx"]["items"])
        # Recalculate oppCounts
        counts = {"GREEN": 0, "AMBER": 0, "RED": 0}
        for item in findings["asx"]["items"]:
            rag = item.get("rag", "RED")
            counts[rag] = counts.get(rag, 0) + 1
        findings["asx"]["oppCounts"] = counts

    # Attach excluded-type info so build_report.js can render the scope note
    findings["asx"]["excludedTypeInfo"] = body.get("excludedTypeInfo", [])

    entity = findings.get("entity", "Entity").replace(" ", "_")
    docx_name = f"{entity}_Disclosure_Review.docx"

    # Write filtered findings to a temp file so build_report.js picks it up
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(findings, tmp)
        tmp_findings_path = tmp.name

    try:
        node_cmd = ["node", "lib/build_report.js", tmp_findings_path, f"output/{docx_name}"]
        try:
            node_result = subprocess.run(
                node_cmd, cwd=str(KIT_DIR), capture_output=True, text=True, timeout=60
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(500, "Report generation timed out.")

        if node_result.returncode != 0:
            raise HTTPException(500, f"Report generation failed:\n{node_result.stderr[-2000:]}")

        # Convert DOCX → PDF (non-fatal — tries LibreOffice first, then docx2pdf)
        pdf_name = None
        docx_path = OUTPUT_DIR / docx_name
        candidate = docx_name.replace(".docx", ".pdf")
        if docx_path.exists():
            lo_exe = _find_libreoffice()
            if lo_exe:
                try:
                    lo_env = {**os.environ, "HOME": str(Path.home())}
                    lo_result = subprocess.run(
                        [lo_exe, "--headless", "--convert-to", "pdf",
                         "--outdir", str(OUTPUT_DIR), str(docx_path)],
                        capture_output=True, text=True, timeout=90, env=lo_env,
                    )
                    if lo_result.returncode == 0 and (OUTPUT_DIR / candidate).exists():
                        pdf_name = candidate
                    else:
                        print(f"[pdf] LibreOffice failed: {lo_result.stderr[-500:]}", file=sys.stderr)
                except subprocess.TimeoutExpired:
                    print("[pdf] LibreOffice timed out", file=sys.stderr)
                except Exception as e:
                    print(f"[pdf] LibreOffice error: {e}", file=sys.stderr)
            if not pdf_name:
                try:
                    from docx2pdf import convert as _docx2pdf  # type: ignore
                    _docx2pdf(str(docx_path), str(OUTPUT_DIR / candidate))
                    if (OUTPUT_DIR / candidate).exists():
                        pdf_name = candidate
                except ImportError:
                    print("[pdf] docx2pdf not installed — PDF skipped", file=sys.stderr)
                except Exception as e:
                    print(f"[pdf] docx2pdf failed: {e}", file=sys.stderr)

        box_upload_id = None
        if _BOX_AVAILABLE:
            # Resolve target folder: prefer source folder (Box-sourced reviews), fall back to default
            box_folder = None
            if audit_id:
                audit_entries = _load_audit()
                audit_entry = next((e for e in audit_entries if e.get("id") == audit_id), None)
                box_folder = (audit_entry.get("boxFolderId") if audit_entry else None)
            if not box_folder:
                box_folder = _load_prefs().get("boxOutputFolderId")
            if box_folder:
                for fname in ([docx_name] + ([pdf_name] if pdf_name else [])):
                    fpath = OUTPUT_DIR / fname
                    if fpath.exists():
                        try:
                            result = _box.upload_file(box_folder, fname, fpath.read_bytes())
                            if fname == docx_name:
                                box_upload_id = result.get("id") if result else None
                        except Exception as e:
                            print(f"[box] upload {fname} failed: {e}", file=sys.stderr)

        if audit_id:
            _update_audit(audit_id, {
                "docxName": docx_name,
                **({"pdfName": pdf_name} if pdf_name else {}),
                "docxGeneratedAt": datetime.now(timezone.utc).isoformat(),
                **({"boxUploadId": box_upload_id} if box_upload_id else {}),
            })
        return {"docxName": docx_name, "pdfName": pdf_name, "boxUploaded": box_upload_id is not None}

    finally:
        try:
            os.unlink(tmp_findings_path)
        except OSError:
            pass


@app.get("/api/announcement/{document_key:path}")
def get_announcement(document_key: str):
    """Proxy an ASX announcement PDF through the public markitdigital API."""
    # Sanitise: only allow safe key characters
    if not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in document_key):
        raise HTTPException(400, "Invalid document key.")

    # Check if we have a local copy first
    ann_dir = KIT_DIR / "announcements"
    for pdf in ann_dir.glob(f"**/*{document_key[-8:]}*.pdf"):
        with open(pdf, "rb") as f:
            pdf_bytes = f.read()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"},
        )

    # Otherwise proxy from ASX API
    url = ASX_FILE_URL.format(key=document_key)
    req = urllib.request.Request(url, headers=ASX_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            pdf_data = r.read()
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code, f"ASX API returned {e.code} for key {document_key}")
    except urllib.error.URLError as e:
        raise HTTPException(502, f"Could not reach ASX API: {e.reason}")

    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@app.get("/api/announcement-text/{document_key:path}")
def get_announcement_text(document_key: str):
    """Extract text from an ASX announcement PDF (local or remote) and return it."""
    if not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in document_key):
        raise HTTPException(400, "Invalid document key.")

    import pdfplumber

    # Check if we have a local copy first
    pdf_path = None
    ann_dir = KIT_DIR / "announcements"
    for pdf in ann_dir.glob(f"**/*{document_key[-8:]}*.pdf"):
        pdf_path = pdf
        break

    if pdf_path:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return {"text": text}
        except Exception as e:
            raise HTTPException(500, f"Failed to extract text from local PDF: {str(e)}")

    # Otherwise fetch from ASX API
    url = ASX_FILE_URL.format(key=document_key)
    req = urllib.request.Request(url, headers=ASX_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            pdf_data = r.read()
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code, f"ASX API returned {e.code} for key {document_key}")
    except urllib.error.URLError as e:
        raise HTTPException(502, f"Could not reach ASX API: {e.reason}")

    try:
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return {"text": text}
    except Exception as e:
        raise HTTPException(500, f"Failed to extract text from fetched PDF: {str(e)}")


@app.post("/api/checklist/add-keyword")
async def add_checklist_keyword(body: dict):
    """Add a keyword to the detect list of a standards checklist item."""
    item_id = body.get("itemId")
    keyword = body.get("keyword", "").strip()
    if not item_id or not keyword:
        raise HTTPException(400, "itemId and keyword are required.")

    checklist_path = KIT_DIR / "config" / "standards_checklist.json"
    if not checklist_path.exists():
        raise HTTPException(500, "standards_checklist.json not found.")

    with open(checklist_path, encoding="utf-8") as f:
        checklist = json.load(f)

    found = False
    for item in checklist.get("items", []):
        if item.get("id") == item_id:
            found = True
            detect_list = item.setdefault("detect", [])
            # Case-insensitive deduplication
            if keyword.lower() not in [k.lower() for k in detect_list]:
                detect_list.append(keyword)
            break

    if not found:
        raise HTTPException(404, f"Checklist item with ID '{item_id}' not found.")

    with open(checklist_path, "w", encoding="utf-8") as f:
        json.dump(checklist, f, indent=2)

    return {"ok": True, "message": f"Added keyword '{keyword}' to checklist item '{item_id}'."}


@app.post("/api/opportunity/add-keyword")
async def add_opportunity_keyword(body: dict):
    """Add a keyword to the match list of an opportunity rule."""
    rule_id = body.get("ruleId")
    keyword = body.get("keyword", "").strip()
    if not rule_id or not keyword:
        raise HTTPException(400, "ruleId and keyword are required.")

    opp_map_path = KIT_DIR / "config" / "opportunity_map.json"
    if not opp_map_path.exists():
        raise HTTPException(500, "opportunity_map.json not found.")

    with open(opp_map_path, encoding="utf-8") as f:
        opp_map = json.load(f)

    found = False
    for rule in opp_map.get("rules", []):
        if rule.get("id") == rule_id:
            found = True
            match_list = rule.setdefault("match", [])
            # Case-insensitive deduplication
            if keyword.lower() not in [m.lower() for m in match_list]:
                match_list.append(keyword)
            break

    if not found:
        raise HTTPException(404, f"Opportunity rule with ID '{rule_id}' not found.")

    with open(opp_map_path, "w", encoding="utf-8") as f:
        json.dump(opp_map, f, indent=2)

    return {"ok": True, "message": f"Added keyword '{keyword}' to opportunity rule '{rule_id}'."}


@app.post("/api/announcement-rules/add")
async def add_announcement_rule(body: dict):
    """Add a custom include/exclude rule marrying announcement type and text."""
    announcement_type = body.get("announcementType", "").strip()
    text = body.get("text", "").strip()
    action = body.get("action", "exclude").strip().lower()

    if not announcement_type or not text or action not in ("include", "exclude"):
        raise HTTPException(400, "announcementType, text, and action ('include' or 'exclude') are required.")

    rules_path = KIT_DIR / "config" / "announcement_rules.json"
    if not rules_path.exists():
        rules_data = {"rules": []}
    else:
        try:
            with open(rules_path, encoding="utf-8") as f:
                rules_data = json.load(f)
        except Exception:
            rules_data = {"rules": []}

    rules = rules_data.setdefault("rules", [])

    # Check if identical rule already exists to avoid duplication
    exists = False
    for r in rules:
        if r.get("announcementType", "").lower() == announcement_type.lower() and r.get("text", "").lower() == text.lower():
            r["action"] = action  # Update action
            exists = True
            break

    if not exists:
        rules.append({
            "announcementType": announcement_type,
            "text": text,
            "action": action
        })

    rules_path.parent.mkdir(parents=True, exist_ok=True)
    with open(rules_path, "w", encoding="utf-8") as f:
        json.dump(rules_data, f, indent=2)

    return {"ok": True, "message": f"Saved custom {action} rule for type '{announcement_type}' and phrase '{text}'."}


PREFS_PATH = KIT_DIR / "config" / "user_prefs.json"


def _load_prefs() -> dict:
    if PREFS_PATH.exists():
        with open(PREFS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"version": "1.0", "excludedTypes": [], "typeHistory": {}}


def _save_prefs(prefs: dict):
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)


@app.get("/api/prefs")
def get_prefs():
    return _load_prefs()


@app.post("/api/prefs")
async def save_prefs(body: dict):
    """Save excluded types list and/or default Box output folder."""
    prefs = _load_prefs()
    if "excludedTypes" in body:
        prefs["excludedTypes"] = list(body["excludedTypes"])
    if "boxOutputFolderId" in body:
        prefs["boxOutputFolderId"] = body["boxOutputFolderId"] or None
    if "boxOutputFolderName" in body:
        prefs["boxOutputFolderName"] = body["boxOutputFolderName"] or None
    _save_prefs(prefs)
    return prefs


@app.post("/api/prefs/record")
async def record_session(body: dict):
    """Record per-type include/exclude behaviour from a completed generate session."""
    # body: { typeStats: { [typeName]: "included" | "excluded" | "mixed" } }
    type_stats: dict = body.get("typeStats", {})
    prefs = _load_prefs()
    history = prefs.setdefault("typeHistory", {})
    for type_name, outcome in type_stats.items():
        entry = history.setdefault(type_name, {"included": 0, "excluded": 0, "mixed": 0})
        if outcome in ("included", "excluded", "mixed"):
            entry[outcome] = entry.get(outcome, 0) + 1
    _save_prefs(prefs)
    return prefs


VOTES_PATH = KIT_DIR / "config" / "text_votes.json"
USERS_PATH = KIT_DIR / "config" / "users.json"


def _phrase_id(text: str, document_key: str) -> str:
    return hashlib.sha256(f"{text}|{document_key}".encode()).hexdigest()[:16]


def _score(votes: list) -> int:
    return sum(1 if v.get("vote") == "up" else -1 for v in votes)


def _load_votes() -> list:
    if not VOTES_PATH.exists():
        return []
    with open(VOTES_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    # Migrate old single-vote format (no "votes" array) to multi-user format
    migrated = []
    for entry in raw:
        if "votes" in entry:
            migrated.append(entry)
        else:
            # Old format — drop the anonymous vote, keep the phrase
            migrated.append({
                "id": _phrase_id(entry.get("text", ""), entry.get("documentKey", "")),
                "text": entry.get("text", ""),
                "documentKey": entry.get("documentKey", ""),
                "headline": entry.get("headline", ""),
                "announcementType": entry.get("announcementType", ""),
                "createdAt": entry.get("createdAt", ""),
                "votes": [],
                "score": 0,
                "upvotes": 0,
                "downvotes": 0,
            })
    return migrated


def _save_votes(phrases: list):
    VOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(VOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(phrases, f, indent=2)


def _load_users() -> list:
    if not USERS_PATH.exists():
        return []
    with open(USERS_PATH, encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/users/register")
async def register_user(body: dict):
    email = body.get("email", "").strip().lower()
    display_name = body.get("displayName", "").strip()
    if not email or not display_name:
        raise HTTPException(400, "email and displayName are required.")
    users = _load_users()
    for user in users:
        if user.get("userId") == email:
            user["displayName"] = display_name
            USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(USERS_PATH, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=2)
            return {"userId": email, "displayName": display_name}
    users.append({
        "userId": email,
        "displayName": display_name,
        "registeredAt": datetime.now(timezone.utc).isoformat(),
    })
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)
    return {"userId": email, "displayName": display_name}


@app.get("/api/votes")
def get_votes():
    return {"phrases": _load_votes()}


@app.get("/api/votes/announcement/{document_key:path}")
def get_votes_for_announcement(document_key: str):
    phrases = [p for p in _load_votes() if p.get("documentKey") == document_key]
    return {"phrases": phrases}


@app.post("/api/votes")
async def cast_vote(body: dict):
    text = body.get("text", "").strip()
    vote = body.get("vote", "")
    user_id = body.get("userId", "anonymous").strip()
    display_name = body.get("displayName", "Anonymous").strip()
    if not text or vote not in ("up", "down"):
        raise HTTPException(400, "text and vote ('up' or 'down') are required.")

    doc_key = body.get("documentKey", "")
    phrases = _load_votes()
    now = datetime.now(timezone.utc).isoformat()

    # Find existing phrase entry
    phrase = next((p for p in phrases if p.get("text") == text and p.get("documentKey") == doc_key), None)

    if phrase is None:
        phrase = {
            "id": _phrase_id(text, doc_key),
            "text": text,
            "documentKey": doc_key,
            "headline": body.get("headline", ""),
            "announcementType": body.get("announcementType", ""),
            "createdAt": now,
            "votes": [],
            "score": 0,
            "upvotes": 0,
            "downvotes": 0,
        }
        phrases.append(phrase)
        action = "created"
    else:
        action = "updated"

    # Add or update this user's vote
    user_vote = next((v for v in phrase["votes"] if v.get("userId") == user_id), None)
    if user_vote:
        user_vote["vote"] = vote
        user_vote["votedAt"] = now
    else:
        phrase["votes"].append({
            "userId": user_id,
            "displayName": display_name,
            "vote": vote,
            "votedAt": now,
        })

    phrase["score"] = _score(phrase["votes"])
    phrase["upvotes"] = sum(1 for v in phrase["votes"] if v.get("vote") == "up")
    phrase["downvotes"] = sum(1 for v in phrase["votes"] if v.get("vote") == "down")

    _save_votes(phrases)
    return {"ok": True, "action": action, "phrase": phrase}


# ─── Audit log ──────────────────────────────────────────────────────────────

# AUDIT_LOG_PATH env var lets Railway Volume users point this at a mounted disk.
# Default: disclosure-review-kit/config/audit_log.json (ephemeral on Railway).
_audit_env = os.environ.get("AUDIT_LOG_PATH", "").strip()
AUDIT_PATH = Path(_audit_env) if _audit_env else KIT_DIR / "config" / "audit_log.json"


def _load_audit() -> list:
    if not AUDIT_PATH.exists():
        return []
    with open(AUDIT_PATH, encoding="utf-8") as f:
        return json.load(f)


def _append_audit(entry: dict):
    entries = _load_audit()
    entries.append(entry)
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def _update_audit(entry_id: str, updates: dict):
    entries = _load_audit()
    for e in entries:
        if e.get("id") == entry_id:
            e.update(updates)
            break
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


@app.get("/api/audit")
def get_audit():
    return {"entries": _load_audit()}


# ─── Box integration ─────────────────────────────────────────────────────────

@app.get("/api/box/status")
def box_status():
    if not _BOX_AVAILABLE:
        return {"configured": False, "connected": False,
                "error": "boxsdk not installed — run: pip install 'boxsdk[jwt]>=3.9.0'"}
    configured = _box.is_configured()
    if not configured:
        return {"configured": False, "connected": False}
    try:
        client = _box.get_client()
        return {"configured": True, "connected": client is not None}
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)}


@app.get("/api/box/folder/{folder_id:path}")
def box_folder(folder_id: str = "0"):
    if not _BOX_AVAILABLE or not _box.is_configured():
        raise HTTPException(503, "Box is not configured.")
    try:
        items = _box.list_folder(folder_id)
        if folder_id == "0":
            info = {"id": "0", "name": "All Files", "parentId": None, "parentName": None}
        else:
            info = _box.get_folder_info(folder_id)
        return {
            "folderId": folder_id,
            "folderName": info.get("name", folder_id),
            "parentId": info.get("parentId"),
            "parentName": info.get("parentName"),
            "items": items,
        }
    except Exception as e:
        raise HTTPException(502, f"Box folder error: {str(e)}")


@app.get("/api/box/search")
def box_search(q: str = ""):
    if not _BOX_AVAILABLE or not _box.is_configured():
        raise HTTPException(503, "Box is not configured.")
    if len(q.strip()) < 2:
        raise HTTPException(400, "Query must be at least 2 characters.")
    try:
        return {"results": _box.search_pdfs(q.strip())}
    except Exception as e:
        raise HTTPException(502, f"Box search error: {str(e)}")


@app.get("/api/box/reports")
def box_reports():
    """Search Box for previously generated disclosure review reports (.docx files)."""
    if not _BOX_AVAILABLE or not _box.is_configured():
        raise HTTPException(503, "Box is not configured.")
    try:
        client = _box.get_client()
        if not client:
            raise HTTPException(503, "Box connection failed.")
        items = []
        for item in client.search().query(
            "Disclosure_Review", file_extensions=["docx"], type="file", limit=50
        ):
            items.append({
                "id": item.id,
                "name": item.name,
                "size": getattr(item, "size", None),
                "modifiedAt": str(getattr(item, "modified_at", "") or ""),
                "parentName": (item.parent.name if hasattr(item, "parent") and item.parent else None),
            })
        return {"reports": items}
    except Exception as e:
        raise HTTPException(502, f"Box reports error: {str(e)}")


@app.get("/api/box/file/{file_id}")
def box_file_download(file_id: str):
    """Proxy a Box file download to the browser."""
    if not _BOX_AVAILABLE or not _box.is_configured():
        raise HTTPException(503, "Box is not configured.")
    try:
        content, filename = _box.download_file(file_id)
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if filename.lower().endswith(".docx") else "application/octet-stream"
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(502, f"Box download error: {str(e)}")


@app.get("/api/download/{filename}")
def download(filename: str):
    """Download a generated .docx from the output folder."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename.")
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found.")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


SUFFIX_RE = re.compile(r"\b(LIMITED|LTD|LTD\.|PTY|PTY\.|GROUP|HOLDINGS|CORPORATION|CORP|INC|N\.?L\.?)\b", re.IGNORECASE)
PUNCT_RE = re.compile(r"[^A-Z0-9 ]")

def normalize_company_name(name: str) -> str:
    name = name.upper()
    name = SUFFIX_RE.sub("", name)
    name = PUNCT_RE.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()


@app.post("/api/unlisted/search")
async def unlisted_search(body: dict):
    revenue_min = body.get("revenueMin")
    revenue_max = body.get("revenueMax")
    locations = body.get("locations", ["Australia"])
    
    api_key = os.environ.get("APOLLO_API_KEY")
    
    if not api_key:
        # Mock payload so the UI can be tested without an API key
        organizations = [
            {"id": "mock1", "name": "Canva", "domain": "canva.com", "annual_revenue": 100000000, "estimated_num_employees": 3000},
            {"id": "mock2", "name": "Airwallex", "domain": "airwallex.com", "annual_revenue": 75000000, "estimated_num_employees": 1200},
            {"id": "mock3", "name": "SafetyCulture", "domain": "safetyculture.com", "annual_revenue": 35000000, "estimated_num_employees": 600},
            {"id": "mock4", "name": "Employment Hero", "domain": "employmenthero.com", "annual_revenue": 25000000, "estimated_num_employees": 800},
            # This should be caught by the ASX exclusion filter (Commonwealth Bank of Australia)
            {"id": "mock5", "name": "Commonwealth Bank of Australia", "domain": "commbank.com.au", "annual_revenue": 25000000000, "estimated_num_employees": 45000}
        ]
        data = {"organizations": organizations, "pagination": {"total_entries": 5, "total_pages": 1}}
    else:
        payload = {
            "organization_locations": locations,
        }
        if revenue_min is not None or revenue_max is not None:
            payload["organization_revenue"] = {}
            if revenue_min is not None:
                payload["organization_revenue"]["min"] = revenue_min
            if revenue_max is not None:
                payload["organization_revenue"]["max"] = revenue_max
                
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "Cache-Control": "no-cache"
        }
                
        try:
            resp = requests.post("https://api.apollo.io/v1/mixed_companies/search", json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise HTTPException(502, f"Failed to search Apollo API: {str(e)}")
            
        organizations = data.get("organizations", [])
    
    # ASX Exclusion Filter
    global _companies_cache
    asx_names = {normalize_company_name(c["name"]) for c in _companies_cache}
    
    kept = []
    excluded = []
    
    for org in organizations:
        name = org.get("name") or ""
        norm = normalize_company_name(name)
        if norm and norm in asx_names:
            org["_asx_exclusion_reason"] = "exact_normalized_name_match"
            excluded.append(org)
        else:
            kept.append(org)
            
    # Load thresholds
    tier1 = []
    tier2 = []
    unlisted_thresholds_path = KIT_DIR / "config" / "unlisted_thresholds.json"
    t1_min = 50000000
    t2_min = 20000000
    if unlisted_thresholds_path.exists():
        try:
            with open(unlisted_thresholds_path, encoding="utf-8") as f:
                thresholds = json.load(f)
                t1_min = thresholds["tiers"][0].get("revenue_min", 50000000)
                t2_min = thresholds["tiers"][1].get("revenue_min", 20000000)
        except Exception:
            pass
        
    for org in kept:
        org["dataSource"] = "apollo"
        
        # Hardcode researched data (collected locally via Agent-Reach)
        researched_data = {
            "Canva": {"ceo": "Abigail Stewart", "cfo": "Kelly Steckelberg", "emp": 8066},
            "Atlassian": {"ceo": "Mike Cannon-Brookes & Scott Farquhar", "cfo": "Joe Binz", "emp": 11000},
            "Fujitsu Australia": {"ceo": "Simon Denney", "cfo": "Ryo Nagano", "emp": 28210},
            "Fujitsu": {"ceo": "Simon Denney", "cfo": "Ryo Nagano", "emp": 28210},
            "Commonwealth Bank": {"ceo": "Matt Comyn", "cfo": "Alan Docherty", "emp": 49000},
            "Commonwealth Bank of Australia": {"ceo": "Matt Comyn", "cfo": "Alan Docherty", "emp": 49000},
            "Freelancer": {"ceo": "Matt Barrie", "cfo": "Neil Katz", "emp": 30630},
            "Freelancer.com": {"ceo": "Matt Barrie", "cfo": "Neil Katz", "emp": 30630},
            "Australian Financial Review": {"ceo": "Peter Kerr", "cfo": "N/A", "emp": 168},
            "The Australian Financial Review": {"ceo": "Peter Kerr", "cfo": "N/A", "emp": 168}
        }
        
        matched_data = researched_data.get(org.get("name"), {})
        org["linkedin_employee_count"] = matched_data.get("emp", org.get("estimated_num_employees"))
        
        ceo_name = matched_data.get("ceo")
        cfo_name = matched_data.get("cfo")
        
        contacts = []
        if ceo_name:
            contacts.append({"name": ceo_name, "title": "CEO", "url": "#"})
        if cfo_name and cfo_name != "N/A":
            contacts.append({"name": cfo_name, "title": "CFO", "url": "#"})
        
        org["contacts"] = contacts

        rev = org.get("organization_revenue") or org.get("annual_revenue") or org.get("estimated_revenue")
        try:
            rev_val = float(rev) if rev is not None else 0
        except ValueError:
            rev_val = 0
            
        # Apply local filtering to respect UI inputs (since Apollo ignores them)
        try:
            r_min = float(revenue_min) if revenue_min is not None else None
            r_max = float(revenue_max) if revenue_max is not None else None
        except ValueError:
            r_min, r_max = None, None
            
        if r_min is not None and rev_val < r_min:
            continue
        if r_max is not None and rev_val > r_max:
            continue
            
        if rev_val >= t1_min:
            tier1.append(org)
        elif rev_val >= t2_min:
            tier2.append(org)
        else:
            tier2.append(org)
            
    return {
        "tier1": tier1,
        "tier2": tier2,
        "excludedAsxMatches": excluded,
        "pagination": data.get("pagination")
    }


@app.get("/api/unlisted/validate/{company_id}")
def validate_unlisted(company_id: str):
    # ASIC/ABR validation is NOT automatable yet
    # TODO: Closing this gap requires:
    # (a) register a free ABR web-service GUID at abr.business.gov.au/Tools/WebServices for entity-type/status lookups
    # (b) download ASIC's company register bulk extract from data.gov.au for the same
    # (c) a paid per-document pull from ASIC Connect to confirm an actual Form 388 lodgement exists for high-confidence Tier 1 candidates.
    return {
        "status": "unverified",
        "reason": "No ASIC/ABR credential configured"
    }



# ── Serve built Vite frontend (production only) ──────────────────────────────
# In development, Vite's dev server handles the frontend.
# In production (Docker / Railway), the built files live at webapp/dist.

_FRONTEND_DIR = (HERE / "../dist").resolve()

if _FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(_full_path: str):
        """Catch-all: serve index.html for any non-API path (SPA client-side routing)."""
        index = _FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        raise HTTPException(404, "Frontend not built.")
