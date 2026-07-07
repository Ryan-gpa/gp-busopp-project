"""FastAPI backend — wraps the Disclosure Review Kit engine."""
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import io
import json
import re
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import urllib.error
import zipfile
import requests
import re
from pathlib import Path

def _load_dotenv():
    """Load webapp/.env into os.environ (existing env vars take precedence)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

_load_dotenv()

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


# ── ASIC company register (free, weekly, data.gov.au) ───────────────────────
# Gives us every registered Australian company (no revenue/employee data) so
# Apollo hits can be validated as real, active companies rather than left as
# an unverifiable stub. See CLAUDE.md "What still needs building".
_ASIC_DATASET_API = "https://data.gov.au/data/api/3/action/package_show?id=asic-companies"
_ASIC_DB_PATH = HERE / "asic_register.sqlite3"
_ASIC_REFRESH_TTL = 7 * 86400  # ASIC republishes the snapshot weekly
_asic_build_lock = threading.Lock()
_asic_building = False


def _asic_db_is_fresh() -> bool:
    return _ASIC_DB_PATH.exists() and (time.time() - _ASIC_DB_PATH.stat().st_mtime) < _ASIC_REFRESH_TTL


def _resolve_asic_zip_url() -> str:
    """Ask data.gov.au's CKAN API for this week's company register download link (filename changes monthly)."""
    req = urllib.request.Request(_ASIC_DATASET_API, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        meta = json.loads(r.read().decode("utf-8"))
    zips = [res for res in meta["result"]["resources"] if (res.get("format") or "").upper() == "ZIP"]
    if not zips:
        raise RuntimeError("No ZIP resource found in ASIC company dataset metadata")
    return zips[0]["url"]


def _build_asic_register_db():
    """Download the current ASIC company register snapshot and index it (name -> status/type/ACN) in SQLite."""
    print("[asic] Refreshing company register index (~1-2 min, ~3M rows)...", file=sys.stderr)
    url = _resolve_asic_zip_url()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        zip_bytes = io.BytesIO(resp.read())

    tmp_path = _ASIC_DB_PATH.with_suffix(".building.sqlite3")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(str(tmp_path))
    conn.execute("CREATE TABLE companies (name_norm TEXT, name TEXT, acn TEXT, type TEXT, status TEXT)")

    row_count = 0
    with zipfile.ZipFile(zip_bytes) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(csv_name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
            reader = csv.reader(text, delimiter="\t")
            header = next(reader)
            idx = {h.strip(): i for i, h in enumerate(header)}
            need = max(idx["Company Name"], idx["ACN"], idx["Type"], idx["Status"])
            batch = []
            for row in reader:
                if len(row) <= need:
                    continue
                name = row[idx["Company Name"]].strip()
                if not name:
                    continue
                norm = normalize_company_name(name)
                if not norm:
                    continue
                batch.append((norm, name, row[idx["ACN"]].strip(), row[idx["Type"]].strip(), row[idx["Status"]].strip()))
                row_count += 1
                if len(batch) >= 20000:
                    conn.executemany("INSERT INTO companies VALUES (?,?,?,?,?)", batch)
                    batch = []
            if batch:
                conn.executemany("INSERT INTO companies VALUES (?,?,?,?,?)", batch)

    conn.execute("CREATE INDEX idx_name_norm ON companies(name_norm)")
    conn.commit()
    conn.close()
    tmp_path.replace(_ASIC_DB_PATH)
    print(f"[asic] Register index built: {row_count} rows", file=sys.stderr)


def _ensure_asic_register_async():
    """Kick off a background refresh if the local index is missing or stale. Never blocks the caller."""
    global _asic_building
    if _asic_db_is_fresh() or _asic_building:
        return
    with _asic_build_lock:
        if _asic_building:
            return
        _asic_building = True

    def _run():
        global _asic_building
        try:
            _build_asic_register_db()
        except Exception as e:
            print(f"[asic] Could not refresh register: {e}", file=sys.stderr)
        finally:
            _asic_building = False

    threading.Thread(target=_run, daemon=True).start()


def _asic_lookup(name: str) -> dict | None:
    """Look up a company name against the ASIC register. Returns None if the index isn't built yet."""
    if not _ASIC_DB_PATH.exists():
        return None
    norm = normalize_company_name(name or "")
    if not norm:
        return None
    conn = sqlite3.connect(str(_ASIC_DB_PATH))
    try:
        cur = conn.execute(
            "SELECT name, acn, type, status FROM companies WHERE name_norm = ? ORDER BY (status = 'REGD') DESC LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {"matchedName": row[0], "acn": row[1], "type": row[2], "status": row[3]}


_ensure_asic_register_async()


# ── Unlisted-search cache (SQLite) ───────────────────────────────────────────
# Every Apollo mixed_companies/search call spends part of a 200-calls/hour
# budget (one paginated search can cost up to MAX_PAGES calls on its own).
# Caching identical searches means a repeat lookup returns instantly with zero
# Apollo calls, and every company we've ever fetched is persisted so a future
# CEO/CFO contact-enrichment pass can run against this table directly instead
# of re-querying Apollo's organization search to rediscover the same companies.
_UNLISTED_CACHE_DB = HERE / "unlisted_search_cache.sqlite3"
_UNLISTED_CACHE_TTL = 86400  # 24h for a complete result
_UNLISTED_CACHE_TTL_PARTIAL = 900  # 15 min for a result cut short by rate limiting


def _unlisted_cache_conn():
    conn = sqlite3.connect(str(_UNLISTED_CACHE_DB))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS search_cache ("
        "query_hash TEXT PRIMARY KEY, params_json TEXT, result_json TEXT, fetched_at REAL, ttl REAL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS companies ("
        "apollo_id TEXT PRIMARY KEY, name TEXT, domain TEXT, data_json TEXT, "
        "first_seen REAL, last_seen REAL)"
    )
    return conn


def _unlisted_query_hash(revenue_min, revenue_max, locations) -> str:
    key = json.dumps(
        {"revenue_min": revenue_min, "revenue_max": revenue_max, "locations": sorted(locations or [])},
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()


def _unlisted_cache_get(query_hash: str):
    conn = _unlisted_cache_conn()
    try:
        row = conn.execute(
            "SELECT result_json, fetched_at, ttl FROM search_cache WHERE query_hash = ?", (query_hash,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    result_json, fetched_at, ttl = row
    if time.time() - fetched_at > ttl:
        return None
    return json.loads(result_json), fetched_at


def _unlisted_cache_put(query_hash: str, params: dict, result: dict, now: float, partial: bool):
    conn = _unlisted_cache_conn()
    try:
        ttl = _UNLISTED_CACHE_TTL_PARTIAL if partial else _UNLISTED_CACHE_TTL
        conn.execute(
            "INSERT OR REPLACE INTO search_cache VALUES (?,?,?,?,?)",
            (query_hash, json.dumps(params), json.dumps(result), now, ttl),
        )
        conn.commit()
    finally:
        conn.close()


def _estimate_org_revenue(org: dict):
    rev = org.get("organization_revenue") or org.get("annual_revenue") or org.get("estimated_revenue")
    if rev is not None:
        try:
            return float(rev)
        except (TypeError, ValueError):
            pass
    emp = org.get("estimated_num_employees")
    if emp is not None:
        try:
            return float(emp) * 150000
        except (TypeError, ValueError):
            pass
    return None


def _local_companies_matching(revenue_min, revenue_max) -> list:
    """Fall back to companies persisted from past searches when a live Apollo
    call fails (e.g. rate limiting). Best-effort only — it only covers
    companies we've happened to fetch before, not a real search of Apollo."""
    if not _UNLISTED_CACHE_DB.exists():
        return []
    try:
        r_min = float(revenue_min) if revenue_min is not None else None
    except (TypeError, ValueError):
        r_min = None
    try:
        r_max = float(revenue_max) if revenue_max is not None else None
    except (TypeError, ValueError):
        r_max = None

    conn = _unlisted_cache_conn()
    try:
        rows = conn.execute("SELECT data_json, last_seen FROM companies").fetchall()
    finally:
        conn.close()

    matches = []
    for data_json, last_seen in rows:
        org = json.loads(data_json)
        rev_val = _estimate_org_revenue(org)
        if rev_val is None:
            continue
        if r_min is not None and rev_val < r_min:
            continue
        if r_max is not None and rev_val > r_max:
            continue
        org["_locallyCachedAt"] = last_seen
        matches.append(org)
    return matches


def _unlisted_companies_upsert(organizations: list, now: float):
    conn = _unlisted_cache_conn()
    try:
        for org in organizations:
            org_id = org.get("id")
            if not org_id:
                continue
            existing = conn.execute(
                "SELECT first_seen FROM companies WHERE apollo_id = ?", (org_id,)
            ).fetchone()
            first_seen = existing[0] if existing else now
            conn.execute(
                "INSERT OR REPLACE INTO companies VALUES (?,?,?,?,?,?)",
                (org_id, org.get("name"), org.get("domain") or org.get("primary_domain"), json.dumps(org), first_seen, now),
            )
        conn.commit()
    finally:
        conn.close()


@app.post("/api/unlisted/search")
async def unlisted_search(body: dict):
    revenue_min = body.get("revenueMin")
    revenue_max = body.get("revenueMax")
    locations = body.get("locations", ["Australia"])

    query_hash = _unlisted_query_hash(revenue_min, revenue_max, locations)
    cached = _unlisted_cache_get(query_hash)
    if cached:
        cached_result, fetched_at = cached
        return {**cached_result, "fetchedAt": fetched_at, "fromCache": True}

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
        
        # Convert revenue filters to employee ranges (proxy)
        try:
            r_min = float(revenue_min) if revenue_min is not None else 0
            r_max = float(revenue_max) if revenue_max is not None else 99999999999
            
            emp_min = int(r_min / 150000)
            emp_max = int(r_max / 150000)
            
            ranges = []
            if emp_min <= 10 and emp_max >= 1: ranges.append("1,10")
            if emp_min <= 20 and emp_max >= 11: ranges.append("11,20")
            if emp_min <= 50 and emp_max >= 21: ranges.append("21,50")
            if emp_min <= 100 and emp_max >= 51: ranges.append("51,100")
            if emp_min <= 250 and emp_max >= 101: ranges.append("101,250")
            if emp_min <= 500 and emp_max >= 251: ranges.append("251,500")
            if emp_min <= 1000 and emp_max >= 501: ranges.append("501,1000")
            if emp_min <= 5000 and emp_max >= 1001: ranges.append("1001,5000")
            if emp_min <= 10000 and emp_max >= 5001: ranges.append("5001,10000")
            if emp_max >= 10001: ranges.append("10001+")
            if ranges:
                payload["organization_num_employees_ranges"] = ranges
                
            # Always sort ascending by employee count so that entering small minimums 
            # returns companies near that minimum instead of defaulting to Canva every time.
            payload["sort_by"] = "organization_num_employees"
            payload["sort_ascending"] = True
        except:
            pass
                
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "Cache-Control": "no-cache"
        }

        # Page through the full result set instead of returning Apollo's first
        # page only. Apollo caps page * per_page at 50,000 records, but the
        # real ceiling in practice is this plan's rate limit: 200 calls/hour
        # for mixed_companies/search (confirmed via the x-rate-limit-hourly
        # response header). MAX_PAGES is capped well under that so a single
        # search can't burn the whole hourly quota by itself.
        MAX_PAGES = 15  # 1,500 orgs per search = 7.5% of the 200/hour quota
        PER_PAGE = 100
        organizations = []
        total_entries = None
        total_pages = None
        rate_limited = False
        served_from_local_fallback = False
        page = 1

        while True:
            payload["page"] = page
            payload["per_page"] = PER_PAGE
            try:
                resp = requests.post("https://api.apollo.io/v1/mixed_companies/search", json=payload, headers=headers, timeout=30)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("retry-after")
                    if page == 1:
                        # Apollo itself is unavailable for a fresh fetch — fall back to
                        # whatever we've already persisted locally from past searches
                        # instead of failing outright.
                        fallback = _local_companies_matching(revenue_min, revenue_max)
                        if fallback:
                            organizations = fallback
                            served_from_local_fallback = True
                            break
                        wait_msg = f" Retry in {int(retry_after) // 60} min." if retry_after else ""
                        raise HTTPException(429, f"Apollo API rate limit reached (200 calls/hour on this plan).{wait_msg}")
                    rate_limited = True
                    break  # keep whatever we already fetched before hitting the limit
                resp.raise_for_status()
                page_data = resp.json()
            except HTTPException:
                raise
            except Exception as e:
                if page == 1:
                    fallback = _local_companies_matching(revenue_min, revenue_max)
                    if fallback:
                        organizations = fallback
                        served_from_local_fallback = True
                        break
                    raise HTTPException(502, f"Failed to search Apollo API: {str(e)}")
                break  # keep whatever we already fetched if a later page fails

            page_orgs = page_data.get("organizations", [])
            organizations.extend(page_orgs)

            pagination = page_data.get("pagination", {})
            total_entries = pagination.get("total_entries", total_entries)
            total_pages = pagination.get("total_pages", total_pages)

            if not page_orgs:
                break
            if total_pages is not None and page >= total_pages:
                break
            if page >= MAX_PAGES:
                break
            page += 1
            time.sleep(0.2)  # stay polite to Apollo's rate limiter

        data = {
            "organizations": organizations,
            "pagination": {
                "total_entries": total_entries,
                "total_pages": total_pages,
                "fetched_entries": len(organizations),
                "fetched_pages": page,
                "rate_limited": rate_limited,
                "served_from_local_fallback": served_from_local_fallback,
                "truncated": bool(rate_limited or served_from_local_fallback or (total_pages and page < total_pages)),
            },
        }
    
    # Snapshot raw org data before anything below mutates these dicts in
    # place (adding dataSource/contacts/_exclusion_reason etc.) — the
    # companies cache should hold clean data reusable by any future query,
    # not this query's derived, query-specific fields.
    _raw_organizations_snapshot = [dict(o) for o in organizations]

    # ASX Exclusion Filter — token-prefix match, not just exact string equality.
    # Apollo frequently returns a shortened trading name ("Commonwealth Bank")
    # while ASX's register holds the full legal name ("Commonwealth Bank of
    # Australia"); an exact-string check misses that and lets ASX-listed
    # companies leak into the "unlisted prospects" list.
    global _companies_cache
    asx_by_first_token: dict = {}
    for c in _companies_cache:
        toks = tuple(normalize_company_name(c["name"]).split())
        if toks:
            asx_by_first_token.setdefault(toks[0], []).append(toks)

    def _asx_match_reason(org_name: str):
        org_toks = tuple(normalize_company_name(org_name).split())
        if not org_toks:
            return None
        for asx_toks in asx_by_first_token.get(org_toks[0], []):
            if org_toks == asx_toks:
                return "exact_normalized_name_match"
            shorter, longer = (org_toks, asx_toks) if len(org_toks) <= len(asx_toks) else (asx_toks, org_toks)
            # Require at least 2 shared leading words so a single generic
            # word (e.g. "Australian") can't trigger a false-positive exclusion.
            if len(shorter) >= 2 and longer[: len(shorter)] == shorter:
                return "prefix_token_match"
        return None

    kept = []
    excluded = []

    for org in organizations:
        reason = _asx_match_reason(org.get("name") or "")
        if reason:
            org["_asx_exclusion_reason"] = reason
            excluded.append(org)
        else:
            kept.append(org)
            
    # Load thresholds
    tier1 = []
    tier2 = []
    excluded_over_max = []
    excluded_under_min = []
    excluded_incomplete_data = []
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
        emp_count = org.get("estimated_num_employees")

        # A company with no revenue AND no employee estimate has zero signal
        # for which tier it belongs in. Previously this defaulted such a
        # company straight into the search's floor value, which meant every
        # no-data company auto-passed the filter and polluted results with
        # "Unknown" rows. Report it separately instead of guessing.
        try:
            rev_val = float(rev) if rev is not None else (float(emp_count) * 150000 if emp_count is not None else None)
        except (TypeError, ValueError):
            rev_val = None

        if rev_val is None:
            org["_exclusion_reason"] = "incomplete_data"
            excluded_incomplete_data.append(org)
            continue

        try:
            r_min_val = float(revenue_min) if revenue_min is not None else None
        except (TypeError, ValueError):
            r_min_val = None

        # Tier 2's own label promises "$20-50M" (t2_min) — enforce that floor
        # even when the user's own Revenue Min is blank or set below it, so a
        # sub-$20M company can never land in a table that says otherwise.
        effective_min = max(t2_min, r_min_val) if r_min_val is not None else t2_min

        # revenueMax narrows the Apollo employee-range query, but that's only
        # a proxy — it doesn't guarantee Apollo (or our own employee*150k
        # estimate) stays under the cap. Enforce it for real here so setting
        # a max actually excludes companies bigger than it, instead of a
        # megacap slipping through into "Tier 1" just because rev_val >= t1_min.
        try:
            r_max_val = float(revenue_max) if revenue_max is not None else None
        except (TypeError, ValueError):
            r_max_val = None

        if rev_val < effective_min:
            org["_exclusion_reason"] = "below_revenue_min"
            excluded_under_min.append(org)
            continue

        if r_max_val is not None and rev_val > r_max_val:
            org["_exclusion_reason"] = "exceeds_revenue_max"
            excluded_over_max.append(org)
            continue

        if rev_val >= t1_min:
            tier1.append(org)
        else:
            tier2.append(org)

    now = time.time()
    pagination = data.get("pagination") or {}
    result = {
        "tier1": tier1,
        "tier2": tier2,
        "excludedAsxMatches": excluded,
        "excludedOverMax": excluded_over_max,
        "excludedUnderMin": excluded_under_min,
        "excludedIncompleteData": excluded_incomplete_data,
        "thresholds": {"t1Min": t1_min, "t2Min": t2_min},
        "pagination": pagination,
    }

    if pagination.get("served_from_local_fallback"):
        # Nothing new was actually fetched from Apollo — don't upsert (no new
        # data) and don't cache this degraded result over a potentially
        # good future fetch's cache slot.
        oldest = min((o.get("_locallyCachedAt") for o in organizations if o.get("_locallyCachedAt")), default=now)
        return {**result, "fetchedAt": oldest, "fromCache": True}

    _unlisted_companies_upsert(_raw_organizations_snapshot, now)
    _unlisted_cache_put(
        query_hash,
        {"revenueMin": revenue_min, "revenueMax": revenue_max, "locations": locations},
        result,
        now,
        # Only a real rate-limit cutoff gets a short TTL — hitting our own
        # MAX_PAGES safety cap is an expected, complete-enough result and
        # should get the full 24h TTL like any other successful search.
        partial=bool(pagination.get("rate_limited")),
    )
    return {**result, "fetchedAt": now, "fromCache": False}


@app.get("/api/unlisted/validate/{company_id}")
def validate_unlisted(company_id: str, name: str = ""):
    # Confirms the candidate is a real, active company on ASIC's public register
    # (free weekly bulk extract from data.gov.au). This is existence/status only —
    # ASIC's public data has no revenue or employee figures, so it cannot confirm
    # "large proprietary company" status. A definitive large-proprietary check
    # still requires a paid per-document Form 388 lodgement pull from ASIC Connect.
    if not name.strip():
        return {"status": "unverified", "reason": "No company name supplied"}

    if not _ASIC_DB_PATH.exists():
        _ensure_asic_register_async()
        return {"status": "pending", "reason": "ASIC register index is still building"}

    match = _asic_lookup(name)
    if not match:
        return {"status": "not_found", "reason": "No matching company name on the ASIC register"}
    if match["status"] != "REGD":
        return {
            "status": "deregistered",
            "reason": f"ASIC status: {match['status']}",
            "acn": match["acn"],
            "matchedName": match["matchedName"],
        }
    return {
        "status": "verified",
        "reason": "Active on ASIC company register",
        "acn": match["acn"],
        "asicType": match["type"],
        "matchedName": match["matchedName"],
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
