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
_in_prod = os.environ.get("RAILWAY_ENVIRONMENT") is not None
HERE = Path(__file__).parent.resolve()
APP_ROOT = Path("/app") if _in_prod else (HERE / "../../").resolve()
DATA_DIR = Path(os.environ.get("DATA_DIR", os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", APP_ROOT / "data"))).resolve()
KIT_DIR = (APP_ROOT / "disclosure-review-kit").resolve()
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


# ── ASIC infringement notices register ───────────────────────────────────────
# ASIC publishes this only as a browsable HTML table (no bulk CSV/API), so we
# scrape it ourselves: a bundled snapshot ships in the repo so the feature
# always works offline, and a background re-scrape refreshes it weekly (same
# pattern as the ASIC company register below). On any scrape failure the
# existing snapshot stays in place untouched.
_INFRINGEMENT_NOTICES_PATH = DATA_DIR / "asic_infringement_notices.json"
_INFRINGEMENT_NOTICES_URL = "https://www.asic.gov.au/online-services/search-asic-registers/infringement-notices-register/"
_INFRINGEMENT_REFRESH_TTL = 7 * 86400
_infringement_by_norm_name: dict = {}
_infringement_refresh_lock = threading.Lock()
_infringement_refreshing = False


def _load_infringement_notices():
    global _infringement_by_norm_name
    if not _INFRINGEMENT_NOTICES_PATH.exists():
        return
    try:
        records = json.loads(_INFRINGEMENT_NOTICES_PATH.read_text(encoding="utf-8"))
        by_name: dict = {}
        for rec in records:
            norm = normalize_company_name(rec.get("name") or "")
            if norm:
                by_name.setdefault(norm, []).append(rec)
        _infringement_by_norm_name = by_name
        print(f"[asic] Loaded {len(records)} infringement notice records ({len(by_name)} companies)", file=sys.stderr)
    except Exception as e:
        print(f"[asic] Could not load infringement notices: {e}", file=sys.stderr)


def _scrape_infringement_notices() -> list:
    """Fetch and parse ASIC's infringement notices register page into records.
    Raises on any failure — callers keep the existing snapshot on error."""
    from bs4 import BeautifulSoup

    resp = requests.get(_INFRINGEMENT_NOTICES_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    records = []
    for heading in soup.find_all(["h2", "h3"]):
        year = heading.get_text(strip=True)
        if not re.fullmatch(r"20\d\d", year):
            continue
        table = heading.find_next("table")
        if not table:
            continue
        rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")[1:]
        for tr in rows:
            cells = tr.find_all("td")
            if len(cells) < 6:
                continue
            name = cells[0].get_text(strip=True)
            if not name:
                continue
            notice_link = cells[3].find("a")
            media_link = cells[4].find("a")
            media_href = media_link["href"] if media_link and media_link.has_attr("href") else None
            records.append({
                "year": year,
                "name": name,
                "licenceOrAcn": cells[1].get_text(strip=True),
                "datePaid": cells[2].get_text(strip=True),
                "noticeId": notice_link.get_text(strip=True) if notice_link else None,
                "noticePdfUrl": notice_link["href"] if notice_link and notice_link.has_attr("href") else None,
                "mediaReleaseId": media_link.get_text(strip=True) if media_link else None,
                "mediaReleaseTitle": media_link["title"] if media_link and media_link.has_attr("title") else None,
                "mediaReleaseUrl": ("https://www.asic.gov.au" + media_href) if media_href and media_href.startswith("/") else media_href,
                "legislation": cells[5].get_text(strip=True),
            })

    # A structural page change would surface here as a tiny/empty parse —
    # refuse to overwrite a known-good snapshot with that.
    if len(records) < 50:
        raise RuntimeError(f"Parse produced only {len(records)} records — page structure likely changed, keeping existing snapshot")
    return records


def _ensure_infringement_notices_async():
    """Re-scrape in the background if the snapshot is older than a week. Never blocks, never clobbers on failure."""
    global _infringement_refreshing
    fresh = _INFRINGEMENT_NOTICES_PATH.exists() and (time.time() - _INFRINGEMENT_NOTICES_PATH.stat().st_mtime) < _INFRINGEMENT_REFRESH_TTL
    if fresh or _infringement_refreshing:
        return
    with _infringement_refresh_lock:
        if _infringement_refreshing:
            return
        _infringement_refreshing = True

    def _run():
        global _infringement_refreshing
        try:
            records = _scrape_infringement_notices()
            tmp = _INFRINGEMENT_NOTICES_PATH.with_suffix(".building.json")
            tmp.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(_INFRINGEMENT_NOTICES_PATH)
            _load_infringement_notices()
            print(f"[asic] Infringement notices refreshed: {len(records)} records", file=sys.stderr)
        except Exception as e:
            print(f"[asic] Infringement notices refresh failed (keeping existing snapshot): {e}", file=sys.stderr)
        finally:
            _infringement_refreshing = False

    threading.Thread(target=_run, daemon=True).start()


_load_infringement_notices()
_ensure_infringement_notices_async()


def _infringement_lookup(name: str) -> list:
    return _infringement_by_norm_name.get(normalize_company_name(name or ""), [])


# ── ASIC company register (free, weekly, data.gov.au) ───────────────────────
# Gives us every registered Australian company (no revenue/employee data) so
# Apollo hits can be validated as real, active companies rather than left as
# an unverifiable stub. See CLAUDE.md "What still needs building".
_ASIC_DATASET_API = "https://data.gov.au/data/api/3/action/package_show?id=asic-companies"
# v2: schema now carries every field ASIC actually publishes (Class, Sub Class,
# dates, ABN, previous state, etc.), not just name/acn/type/status. New
# filename so any pre-existing v1 file (fewer columns) is never queried
# against the new SELECT — it's just orphaned and a fresh build replaces it.
_ASIC_DB_PATH = DATA_DIR / "unified_companies.db"
_ASIC_REFRESH_TTL = 7 * 86400  # ASIC republishes the snapshot weekly
_asic_build_lock = threading.Lock()
_asic_building = False


def _asic_db_is_fresh() -> bool:
    return _ASIC_DB_PATH.exists() and (time.time() - _ASIC_DB_PATH.stat().st_mtime) < _ASIC_REFRESH_TTL



def _ensure_asic_register_async():
    """Kick off a background refresh if the local index is missing or stale. Never blocks the caller."""
    global _asic_building
    
    db_path = DATA_DIR / "unified_companies.db"
    needs_unified = not db_path.exists() or db_path.stat().st_size < 1000000
    
    lock_path = DATA_DIR / ".building.lock"
    is_building = _asic_building or lock_path.exists()
    
    if (_asic_db_is_fresh() and not needs_unified) or is_building:
        return
    with _asic_build_lock:
        if _asic_building:
            return
        _asic_building = True

    def _run():
        global _asic_building
        try:
            print("[asic] Building unified companies DB...")
            import subprocess
            import sys
            script_path = HERE / "scripts" / "build_unified_db.py"
            subprocess.run([sys.executable, str(script_path)], check=True)
            
        except Exception as e:
            err_msg = f"[asic] Could not refresh register: {e}"
            print(err_msg, file=sys.stderr)
            with open(DATA_DIR / "build_error.log", "w") as f:
                f.write(err_msg)
        finally:
            _asic_building = False
            lock_path = DATA_DIR / ".building.lock"
            if lock_path.exists():
                lock_path.unlink()

    threading.Thread(target=_run, daemon=True).start()


def _asic_lookup(name: str) -> dict | None:
    """Look up a company name against the ASIC register."""
    if not _ASIC_DB_PATH.exists():
        return None
    norm = normalize_company_name(name or "")
    if not norm:
        return None
    fields = ["name", "acn", "type", "class", "subclass", "status", "state"]
    conn = sqlite3.connect(str(_ASIC_DB_PATH))
    try:
        cur = conn.execute(
            f"SELECT {', '.join(fields)} FROM companies WHERE name_norm = ? ORDER BY (status = 'REGD') DESC LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return dict(zip(fields, row))


def _asic_lookup_many(names: list) -> dict:
    """Batched register lookup."""
    if not _ASIC_DB_PATH.exists():
        return {}
    fields = ["name", "acn", "type", "class", "subclass", "status", "state"]
    sql = f"SELECT {', '.join(fields)} FROM companies WHERE name_norm = ? ORDER BY (status = 'REGD') DESC LIMIT 1"
    out = {}
    conn = sqlite3.connect(str(_ASIC_DB_PATH))
    try:
        cur = conn.cursor()
        for name in names:
            norm = normalize_company_name(name or "")
            if not norm or norm in out:
                continue
            row = cur.execute(sql, (norm,)).fetchone()
            if row:
                out[norm] = dict(zip(fields, row))
    finally:
        conn.close()
    return out


def _asic_fields_to_api(match: dict) -> dict:
    """ASIC register record -> the camelCased shape the frontend's AsicValidation type expects."""
    fields = {
        "matchedName": match.get("name"),
        "acn": match.get("acn"),
        "asicType": match.get("type"),
        "asicClass": match.get("class"),
        "asicSubClass": match.get("subclass"),
        "stateRegistrationNumber": match.get("state"),
    }
    fields = {k: v for k, v in fields.items() if v}
    if match["status"] != "REGD":
        return {"status": "deregistered", "reason": f"ASIC status: {match['status']}", **fields}
    return {"status": "verified", "reason": "Active on ASIC company register", **fields}


_ensure_asic_register_async()


# ── Unlisted-search cache (SQLite) ───────────────────────────────────────────
# Every Apollo mixed_companies/search call spends part of a 200-calls/hour
# budget (one paginated search can cost up to MAX_PAGES calls on its own).
# Caching identical searches means a repeat lookup returns instantly with zero
# Apollo calls, and every company we've ever fetched is persisted so a future
# CEO/CFO contact-enrichment pass can run against this table directly instead
# of re-querying Apollo's organization search to rediscover the same companies.
_UNLISTED_CACHE_DB = DATA_DIR / "unlisted_search_cache.sqlite3"
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
    conn.execute(
        "CREATE TABLE IF NOT EXISTS contacts_cache ("
        "org_id TEXT PRIMARY KEY, contacts_json TEXT, fetched_at REAL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS contacts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "org_id TEXT, "
        "name TEXT, "
        "title TEXT, "
        "email TEXT, "
        "email_status TEXT, "
        "phone TEXT, "
        "linkedin_url TEXT, "
        "source TEXT, "
        "fetched_at REAL, "
        "UNIQUE(org_id, name))"
    )
    return conn


def _unlisted_query_hash(revenue_min, revenue_max, locations, company_name=None) -> str:
    key = json.dumps(
        {
            "revenue_min": revenue_min,
            "revenue_max": revenue_max,
            "locations": sorted(locations or []),
            "company_name": (company_name or "").strip().lower(),
        },
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
    band_floor = org.get("_revenueBandFloor")
    if band_floor is not None:
        try:
            # RocketReach-discovered: in-band guaranteed by the search filter
            return float(band_floor)
        except (TypeError, ValueError):
            pass
    return None


def _local_companies_matching(revenue_min, revenue_max, company_name=None) -> list:
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
    name_needle = (company_name or "").strip().lower()

    conn = _unlisted_cache_conn()
    try:
        rows = conn.execute("SELECT data_json, last_seen FROM companies").fetchall()
    finally:
        conn.close()

    matches = []
    for data_json, last_seen in rows:
        org = json.loads(data_json)
        if name_needle and name_needle not in (org.get("name") or "").lower():
            continue
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


# ── Apollo quota/credit status tracking ─────────────────────────────────────
# Every real Apollo response already reveals the account state (rate-limit
# headers + 422 "insufficient credits"), so record it passively as calls
# happen. The status endpoint only makes a live probe when nothing recent is
# known, so surfacing this in the UI costs ~zero extra quota.
_apollo_status: dict = {"checkedAt": None}


def _record_apollo_status(resp, include_rate=True):
    try:
        credits_exhausted = resp.status_code == 422 and "credit" in resp.text.lower()
        update = {"checkedAt": time.time(), "creditsExhausted": credits_exhausted}
        if include_rate:
            # Only company-search responses carry the quota pool we display;
            # people endpoints have their own separate pool whose headers
            # would misreport the search quota.
            update.update({
                "hourlyLeft": int(resp.headers["x-hourly-requests-left"]) if resp.headers.get("x-hourly-requests-left") else None,
                "hourlyLimit": int(resp.headers["x-rate-limit-hourly"]) if resp.headers.get("x-rate-limit-hourly") else None,
                "rateLimited": resp.status_code == 429,
            })
        _apollo_status.update(update)
    except Exception:
        pass


@app.get("/api/unlisted/apollo-status")
def apollo_status():
    """Last-known Apollo account health for the UI banner. Probes live only
    when no real call has reported in for 10 minutes."""
    api_key = os.environ.get("APOLLO_API_KEY")
    if not api_key:
        return {"configured": False}
    stale = _apollo_status["checkedAt"] is None or (time.time() - _apollo_status["checkedAt"]) > 600
    if stale:
        try:
            resp = requests.post(
                "https://api.apollo.io/v1/mixed_companies/search",
                json={"organization_locations": ["Australia"], "page": 1, "per_page": 1},
                headers={"X-Api-Key": api_key, "Cache-Control": "no-cache"},
                timeout=10,
            )
            _record_apollo_status(resp)
        except Exception:
            pass
    return {"configured": True, **_apollo_status}


# TODO: this SQLite cache (companies, contacts_cache) is a per-deployment
# local store with no connection to HubSpot. GP already syncs contacts to
# HubSpot elsewhere (see the gp-contacts/gp-enrich pipeline) — companies and
# CEO/CFO contacts found here should eventually push to HubSpot too, so BD
# follow-up doesn't require manually re-entering what Apollo already found.
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
    company_name = body.get("companyName")
    only_proprietary = body.get("onlyProprietary", False)
    only_infringements = body.get("onlyInfringements", False)
    only_with_contacts = body.get("onlyWithContacts", False)
    db_status = body.get("dbStatusFilter", "all")
    entity_type = body.get("entityTypeFilter", "all")
    liability_class = body.get("classFilter", "all")
    subclass = body.get("subclassFilter", "all")

    db_path = DATA_DIR / "unified_companies.db"
    if not db_path.exists():
        from fastapi import HTTPException
        raise HTTPException(400, detail="Database not found. Please wait 1-2 minutes for the background data load to finish, then try again.")
        
    query = """
        SELECT 
            c.acn, c.name, c.name_norm, c.status, c.type, c.class, c.subclass, c.state, 
            c.is_large_prop, 
            EXISTS(SELECT 1 FROM infringements i WHERE i.acn = c.acn) as has_infringement, 
            COALESCE(m.revenue, c.revenue) as revenue, COALESCE(m.employees, c.employees) as employees, 
            EXISTS(SELECT 1 FROM contacts cnt WHERE cnt.acn = c.acn) as has_contacts
        FROM companies c
        LEFT JOIN metrics m ON c.acn = m.acn
        WHERE 1=1
    """
    params = []
    
    if company_name and company_name.strip():
        query += " AND c.name_norm LIKE ?"
        norm = normalize_company_name(company_name.strip())
        params.append(f"%{norm}%")
        
    if revenue_min is not None:
        try:
            rmin = float(revenue_min)
            query += " AND (COALESCE(m.revenue, c.revenue) >= ? OR COALESCE(m.revenue, c.revenue) IS NULL)"
            params.append(rmin)
        except (ValueError, TypeError):
            pass
            
    if revenue_max is not None:
        try:
            rmax = float(revenue_max)
            query += " AND (COALESCE(m.revenue, c.revenue) <= ? OR COALESCE(m.revenue, c.revenue) IS NULL)"
            params.append(rmax)
        except (ValueError, TypeError):
            pass
            
    if only_proprietary:
        query += " AND c.type = 'APTY' AND c.class = 'LMSH' AND c.subclass = 'PROP'"
        
    if only_infringements:
        query += " AND EXISTS(SELECT 1 FROM infringements i WHERE i.acn = c.acn)"
        
    if only_with_contacts:
        query += " AND EXISTS(SELECT 1 FROM contacts cnt WHERE cnt.acn = c.acn)"
        
    if db_status != "all":
        query += " AND c.status = ?"
        params.append(db_status)
        
    if entity_type != "all":
        query += " AND c.type = ?"
        params.append(entity_type)
        
    if liability_class != "all":
        query += " AND c.class = ?"
        params.append(liability_class)
        
    if subclass != "all":
        query += " AND c.subclass = ?"
        params.append(subclass)

    # Note: We must inject the parameters in the correct order for the count_query and data_query.
    # The count_query doesn't join metrics. Wait! The data_query JOINS metrics. If we used params, they apply to where_portion.

    where_portion = "WHERE 1=1" + query.split("WHERE 1=1")[1]
    count_query = f"SELECT COUNT(*) FROM companies c LEFT JOIN metrics m ON c.acn = m.acn {where_portion}"
    data_query = f"""
        SELECT c.acn, c.name, c.name_norm, c.status, c.type, c.class, c.subclass, c.state,
               c.is_large_prop, 
               EXISTS(SELECT 1 FROM infringements i WHERE i.acn = c.acn) as has_infringement, 
               m.revenue, m.employees, 
               EXISTS(SELECT 1 FROM contacts cnt WHERE cnt.acn = c.acn) as has_contacts
        FROM companies c 
        LEFT JOIN metrics m ON c.acn = m.acn {where_portion}
        ORDER BY has_infringement DESC, c.acn DESC
        LIMIT 5000
    """

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        try:
            total_matched = c.execute(count_query, params).fetchone()[0]
        except Exception as e:
            total_matched = None

        rows = c.execute(data_query, params).fetchall()
        
        # Pre-fetch infringements and contacts
        acns = [row['acn'] for row in rows]
        contacts_by_acn = {}
        inf_by_acn = {}
        if acns:
            placeholders = ",".join("?" * len(acns))
            
            # Fetch contacts
            cr_rows = c.execute(f"SELECT acn, raw_json FROM contacts WHERE acn IN ({placeholders})", acns).fetchall()
            import json
            for cr in cr_rows:
                contacts_by_acn.setdefault(cr[0], []).append(json.loads(cr[1]))
                
            # Fetch infringements
            ir_rows = c.execute(f"SELECT acn, raw_json FROM infringements WHERE acn IN ({placeholders})", acns).fetchall()
            for ir in ir_rows:
                inf_by_acn.setdefault(ir[0], []).append(json.loads(ir[1]))
        
        results = []
        for row in rows:
            acn = row['acn']
            org = {
                "id": f"asic_{acn}",
                "name": row['name'],
                "annual_revenue": row['revenue'],
                "estimated_num_employees": row['employees'],
                "domain": "",
                "dataSource": "asic",
                "has_contacts": bool(row['has_contacts'])
            }
            org['asic'] = {
                "status": "verified" if row['status'] == 'REGD' else "deregistered",
                "reason": f"ASIC Status: {row['status']}",
                "acn": acn,
                "type": row['type'],
                "class": row['class'],
                "subclass": row['subclass'],
                "state": row['state']
            }
            if acn in inf_by_acn:
                org["infringementNotices"] = inf_by_acn[acn]
            elif row['has_infringement']:
                org["infringementNotices"] = [{"title": "Infringement Notice"}]
                
            if acn in contacts_by_acn:
                org["contacts"] = contacts_by_acn[acn]
                
            results.append(org)
            
        return {
            "tier1": results,
            "tier2": [],
            "excludedUnderMin": [],
            "excludedOverMax": [],
            "excludedIncompleteData": [],
            "pagination": {
                "total_pages": 1,
                "fetched_pages": 1,
                "rate_limited": False,
                "fetched_entries": len(results),
                "total_entries": total_matched,
                "truncated": total_matched is not None and total_matched > len(results)
            },
            "fetchedAt": time.time(),
            "fromCache": True
        }
    finally:
        conn.close()


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
    return _asic_fields_to_api(match)


@app.get("/api/unlisted/asic-prospects")
def asic_prospects():
    """ASIC-first discovery: start from ASIC's own signals, enrich elsewhere."""
    seen = set()
    prospects = []
    
    import sqlite3
    db_path = DATA_DIR / "unified_companies.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            cache_data = {row[0]: {"annual_revenue": row[1], "estimated_num_employees": row[2]} for row in conn.execute("SELECT acn, revenue, employees FROM metrics").fetchall()}
            has_contacts_set = {row[0] for row in conn.execute("SELECT DISTINCT acn FROM contacts").fetchall()}
        finally:
            conn.close()
    else:
        cache_data = {}
        has_contacts_set = set()

    for norm, records in _infringement_by_norm_name.items():
        if norm in seen:
            continue
        seen.add(norm)
        rec = records[0]
        asic_match = _asic_lookup(rec["name"])
        acn = (asic_match or {}).get("acn") or re.sub(r"\D", "", rec.get("licenceOrAcn") or "") or norm.replace(" ", "_")
        org_id = f"asic_{acn}"
        cached = cache_data.get(acn, {})
        
        org = {
            "id": org_id,
            "name": rec["name"],
            "domain": None,
            "dataSource": "asic",
            "annual_revenue": cached.get("annual_revenue") or cached.get("organization_revenue") or cached.get("revenue"),
            "estimated_num_employees": cached.get("estimated_num_employees") or cached.get("employees"),
            "infringementNotices": records,
            "has_contacts": acn in has_contacts_set,
            "asic": _asic_fields_to_api(asic_match) if asic_match else None,
        }
        prospects.append(org)

    prospects.sort(key=lambda o: (o["infringementNotices"][0].get("year") or ""), reverse=True)

    now = time.time()
    _unlisted_companies_upsert(prospects, now)

    return {
        "tier1": prospects,
        "tier2": [],
        "excludedAsxMatches": [],
        "excludedOverMax": [],
        "excludedUnderMin": [],
        "excludedIncompleteData": [],
        "excludedNotOnAsic": [],
        "asicJoinAvailable": _ASIC_DB_PATH.exists(),
        "thresholds": {"t1Min": 50000000, "t2Min": 20000000},
        "pagination": {
            "fetched_entries": len(prospects),
            "total_entries": len(prospects),
            "discovery_source": "asic",
        },
        "fetchedAt": now,
        "fromCache": False,
    }


_CONTACT_TITLES = [
    "Chief Executive Officer", "CEO",
    "Managing Director", "President",
    "Founder", "Co-Founder",
    "Chief Financial Officer", "CFO",
    "Chief Operating Officer", "COO",
    "Chief Technology Officer", "CTO",
    "General Manager"
]
_CONTACTS_CACHE_TTL = 30 * 86400  # contact/title changes are rare — 30 days is fine


_DISQUALIFYING_TITLE_WORDS = ("assistant", "deputy", "acting", "former", "ex-", "interim", "coordinator")


def _is_decision_maker_title(title: str) -> bool:
    """Apollo's title search does substring matching, so a query for 'Chief
    Executive Officer' also matches 'Executive Assistant to the CEO' — that
    title literally contains the phrase. Filter those out before spending a
    real enrichment credit on someone who isn't the actual decision-maker."""
    t = (title or "").lower()
    return not any(word in t for word in _DISQUALIFYING_TITLE_WORDS)


def _contact_title_rank(title: str) -> int:
    t = (title or "").lower()
    
    # 1. CEO / Chief Executive
    if "chief executive" in t or t.strip() == "ceo":
        return 0
    # 2. Managing Director / President
    if "managing director" in t or "president" in t:
        return 1
    # 3. Founder / Co-Founder
    if "founder" in t:
        return 2
    # 4. CFO / Chief Financial
    if "chief financial" in t or t.strip() == "cfo":
        return 3
    # 5. COO / Chief Operating
    if "chief operating" in t or t.strip() == "coo":
        return 4
    # 6. CTO / Chief Technology
    if "chief technology" in t or t.strip() == "cto":
        return 5
    # 7. General Manager
    if "general manager" in t or t.strip() == "gm":
        return 6
        
    return 99


# ── RocketReach (secondary contact source) ──────────────────────────────────
# Used only when Apollo comes up dry or nameless-emailless, and only if a
# ROCKETREACH_API_KEY env var is configured. Same two-step model as Apollo:
# person/search returns candidates without contact info (free), person/lookup
# reveals emails/phones and consumes RocketReach export credits. All failures
# here are soft — this is a supplement, never a blocker.
# NOTE: response-shape handling below is built from RocketReach's docs
# (docs.rocketreach.co) but has NOT been verified against a live key yet —
# treat the first real run as the integration test.
_ROCKETREACH_API_KEY_ENV = "ROCKETREACH_API_KEY"


def _fmt_millions(v: float) -> str:
    return f"${v / 1_000_000:g}M"


def _rocketreach_company_search(revenue_min, revenue_max, company_name=None) -> list:
    """Company discovery via RocketReach when Apollo is unavailable. Unlike
    Apollo (employee-count proxy), RocketReach filters by revenue natively —
    numeric range strings like "25000000-50000000", verified live (6,431 AU
    companies in the $25-50M band). Search results carry no revenue VALUE,
    but every hit is inside the requested band by construction of the filter,
    so results carry a revenueBand label rather than a fake point estimate.
    Publicly-traded companies (ticker_symbol present) are dropped at the
    source. Returns [] on any failure — best-effort, never raises."""
    rr_key = os.environ.get(_ROCKETREACH_API_KEY_ENV)
    if not rr_key:
        return []
    try:
        r_min = int(float(revenue_min)) if revenue_min is not None else 20_000_000
    except (TypeError, ValueError):
        r_min = 20_000_000
    try:
        r_max = int(float(revenue_max)) if revenue_max is not None else 1_000_000_000_000
    except (TypeError, ValueError):
        r_max = 1_000_000_000_000

    query = {"location": ["Australia"], "revenue": [f"{r_min}-{r_max}"]}
    if company_name and company_name.strip():
        query["name"] = [company_name.strip()]
    band_label = f"{_fmt_millions(r_min)}–{_fmt_millions(r_max) if r_max < 1_000_000_000_000 else '∞'} (band)"

    orgs, seen_ids = [], set()
    for page in range(1, 4):  # up to 300 companies; searches don't spend export credits
        try:
            resp = requests.post(
                "https://api.rocketreach.co/api/v2/searchCompany",
                headers={"Api-Key": rr_key, "Content-Type": "application/json"},
                timeout=30,
                json={"query": query, "page_size": 100, "start": (page - 1) * 100 + 1},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[rocketreach] company search failed (page {page}): {e}", file=sys.stderr)
            break
        companies = data.get("companies", [])
        for c in companies:
            cid = c.get("id")
            if not cid or cid in seen_ids or not c.get("name"):
                continue
            seen_ids.add(cid)
            if c.get("ticker_symbol"):
                continue  # publicly traded — not an unlisted prospect
            domain = (c.get("email_domain") or "").lower()
            if domain.endswith(".gov.au") or domain.endswith(".edu.au"):
                continue  # govt departments/universities pollute RocketReach's AU revenue bands
            orgs.append({
                "id": f"rr_{cid}",
                "name": c["name"],
                "domain": c.get("email_domain"),
                "primary_domain": c.get("email_domain"),
                "dataSource": "rocketreach",
                "revenueBand": band_label,
                "_revenueBandFloor": r_min,
            })
        total = (data.get("pagination") or {}).get("total") or 0
        if not companies or page * 100 >= total:
            break
    return orgs


def _company_identity_for_org(org_id: str):
    if org_id.startswith("asic_"):
        acn = org_id.split("_")[1]
        db_path = DATA_DIR / "unified_companies.db"
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute("SELECT name FROM companies WHERE acn = ?", (acn,)).fetchone()
                if row:
                    return (row[0], None)
            finally:
                conn.close()
            
    conn = _unlisted_cache_conn()
    try:
        row = conn.execute("SELECT name, domain FROM companies WHERE apollo_id = ?", (org_id,)).fetchone()
    finally:
        conn.close()
    return (row[0], row[1]) if row else (None, None)


def _strip_corp_suffixes(name: str) -> str:
    """'Canva Pty Ltd' -> 'Canva', 'COOPER ENERGY (CS) PTY LTD' -> 'COOPER ENERGY'.
    ASIC stores legal names; commercial databases index brands — bridge the gap."""
    if not name:
        return ""
    # Strip (XYZ)
    name = re.sub(r"\(.*?\)", "", name)
    # Strip Pty Ltd, etc at the end
    name = re.sub(r"(\s+(pty\.?|ltd\.?|limited|proprietary))+\s*$", "", name, flags=re.IGNORECASE)
    # Strip some other common useless corporate suffixes
    name = re.sub(r"(\s+(group|holdings|australia))+\s*$", "", name, flags=re.IGNORECASE)
    # Replace multiple spaces with single space
    return re.sub(r"\s+", " ", name).strip()


def _rocketreach_company_lookup(company_name: str) -> dict:
    """Fetch company metrics (revenue, employees) from RocketReach Company Lookup API."""
    rr_key = os.environ.get(_ROCKETREACH_API_KEY_ENV)
    company_name = _strip_corp_suffixes(company_name)
    if not rr_key or not company_name:
        return {}
    
    try:
        res = requests.get(
            "https://api.rocketreach.co/api/v2/company/lookup",
            headers={"Api-Key": rr_key},
            params={"name": company_name},
            timeout=20
        )
        if res.status_code == 200:
            data = res.json()
            return {
                "revenue": data.get("revenue"),
                "employees": data.get("num_employees")
            }
        elif res.status_code == 429:
            print(f"[rocketreach] Rate limit hit during company lookup for {company_name}", file=sys.stderr)
            return {}  # Rate limit reached, gracefully return empty metrics
        else:
            print(f"[rocketreach] lookup returned {res.status_code} for {company_name}", file=sys.stderr)
    except Exception as e:
        print(f"[rocketreach] company lookup failed for {company_name!r}: {e}", file=sys.stderr)
        if "rate limit" in str(e).lower():
            raise
    return {}


def _rocketreach_find_contacts(company_name: str) -> list:
    """Best-effort CEO/CFO lookup via RocketReach. Returns [] on any failure,
    missing key, or no match — never raises."""
    rr_key = os.environ.get(_ROCKETREACH_API_KEY_ENV)
    if not rr_key or not company_name:
        return []

    def _search(name: str):
        sr = requests.post(
            "https://api.rocketreach.co/api/v2/person/search",
            headers={"Api-Key": rr_key, "Content-Type": "application/json"},
            timeout=20,
            json={"query": {"current_employer": [f'"{name}"'], "current_title": _CONTACT_TITLES}, "page_size": 10},
        )
        sr.raise_for_status()
        return sr.json().get("profiles", [])

    try:
        profiles = _search(company_name)
        if not profiles:
            stripped = _strip_corp_suffixes(company_name)
            if stripped and stripped.lower() != company_name.lower():
                profiles = _search(stripped)
    except Exception as e:
        print(f"[rocketreach] search failed for {company_name!r}: {e}", file=sys.stderr)
        return []

    profiles = [p for p in profiles if _is_decision_maker_title(p.get("current_title"))]
    profiles.sort(key=lambda p: _contact_title_rank(p.get("current_title")))

    contacts = []
    for p in profiles[:2]:  # same credit cap as the Apollo path
        pid = p.get("id")
        if not pid:
            continue
        try:
            lr = requests.get(
                "https://api.rocketreach.co/api/v2/person/lookup",
                headers={"Api-Key": rr_key},
                params={"id": pid},
                timeout=30,
            )
            lr.raise_for_status()
            person = lr.json()
        except Exception as e:
            print(f"[rocketreach] lookup failed for profile {pid}: {e}", file=sys.stderr)
            continue
        # Don't gate on person["status"]: verified live that RocketReach
        # returns status "progress" with complete, grade-A data already in
        # the payload (the field tracks ongoing enrichment of remaining
        # attributes, not usability of what's returned). Gate on whether
        # usable data actually exists instead.
        best_email, email_status, best_rank = None, None, -1
        for e_ in person.get("emails") or []:
            cand = e_ if isinstance(e_, dict) else {"email": e_}
            addr = cand.get("email")
            if not addr:
                continue
            # Prefer valid > unknown > invalid, professional > personal —
            # otherwise an invalid professional address listed later can
            # clobber a verified one (seen live on the first keyed run).
            rank = (2 if cand.get("smtp_valid") == "valid" else 0) + (1 if cand.get("type") == "professional" else 0)
            if rank > best_rank:
                best_email, best_rank = addr, rank
                email_status = "verified" if cand.get("smtp_valid") == "valid" else cand.get("smtp_valid")
        phones = []
        for ph in person.get("phones") or []:
            num = ph.get("number") if isinstance(ph, dict) else ph
            if num and num not in phones:
                phones.append(num)
        name = person.get("name") or p.get("name")
        if not name:
            continue
        if not (best_email or phones or person.get("linkedin_url") or p.get("linkedin_url")):
            continue  # genuinely nothing usable yet
        contacts.append({
            "name": name,
            "title": p.get("current_title") or person.get("current_title") or "",
            "email": best_email,
            "emailStatus": email_status,
            "linkedinUrl": person.get("linkedin_url") or p.get("linkedin_url"),
            "phoneNumbers": phones,
            "source": "rocketreach",
        })
    return contacts


def _merge_contact_sources(apollo_contacts: list, rr_contacts: list) -> list:
    """Merge RocketReach results into Apollo's: same-name entries are combined
    (RocketReach fills missing email/phones, source becomes both), new names
    are appended."""
    merged = list(apollo_contacts)
    by_name = {(c.get("name") or "").strip().lower(): c for c in merged}
    for rc in rr_contacts:
        key = (rc.get("name") or "").strip().lower()
        existing = by_name.get(key)
        if existing:
            filled = False
            if not existing.get("email") and rc.get("email"):
                existing["email"] = rc["email"]
                existing["emailStatus"] = rc.get("emailStatus")
                filled = True
            if not existing.get("phoneNumbers") and rc.get("phoneNumbers"):
                existing["phoneNumbers"] = rc["phoneNumbers"]
                filled = True
            if filled:
                existing["source"] = "apollo+rocketreach"
        else:
            merged.append(rc)
            by_name[key] = rc
    return merged


def _persist_contacts(conn, org_id, contacts_list, now):
    save_contacts(org_id, contacts_list, source if 'source' in locals() else 'apollo')
    for c in contacts_list:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO contacts 
                (org_id, name, title, email, email_status, phone, linkedin_url, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                org_id,
                c.get("name"),
                c.get("title"),
                c.get("email"),
                c.get("emailStatus"),
                ", ".join(c.get("phoneNumbers", [])) if c.get("phoneNumbers") else None,
                c.get("linkedinUrl"),
                c.get("source"),
                now
            ))
        except Exception as e:
            print(f"Error persisting contact: {e}")

def _fetch_and_persist_rr_metrics(org_id: str, company_name: str) -> dict:
    """Fetch company metrics from RR (or Apollo fallback) and immediately persist."""
    metrics = _rocketreach_company_lookup(company_name)
    if not metrics.get("revenue") and not metrics.get("employees"):
        metrics = _apollo_company_lookup(company_name)
        if not metrics.get("revenue") and not metrics.get("employees"):
            return metrics

    rev = metrics.get("revenue")
    emp = metrics.get("employees")
    source = metrics.get("dataSource", "rocketreach")
    
    try:
        import time
        live_conn = sqlite3.connect(str(DATA_DIR / "unified_companies.db"))
        acn = org_id.replace('asic_', '').replace('rr_', '')
        live_conn.execute("UPDATE companies SET revenue = ?, employees = ? WHERE acn = ?", (rev, emp, acn))
        
        live_conn.execute("""
            INSERT OR REPLACE INTO metrics (org_id, acn, revenue, employees, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (org_id, acn, rev, emp, source, time.time()))
        
        live_conn.commit()
    except Exception as e:
        pass
    finally:
        if 'live_conn' in locals():
            live_conn.close()

    return metrics

    rev = metrics.get("revenue")
    emp = metrics.get("employees")
    
    # 1. Update live DB so UI sees it instantly upon reload without rebuilding
    try:
        live_conn = sqlite3.connect(str(DATA_DIR / "unified_companies.db"))
        acn = org_id.replace('asic_', '')
        live_conn.execute("UPDATE companies SET revenue = ?, employees = ? WHERE acn = ?", (rev, emp, acn))
        live_conn.commit()
    except Exception as e:
        print(f"Failed to update live DB with RR metrics for {acn}: {e}", file=sys.stderr)
    finally:
        if 'live_conn' in locals():
            live_conn.close()

    # 2. Update cache DB so it survives full rebuilds
    try:
        cache_conn = _unlisted_cache_conn()
        row = cache_conn.execute("SELECT data_json FROM companies WHERE apollo_id = ?", (org_id,)).fetchone()
        if row and row[0]:
            data = json.loads(row[0])
            data["annual_revenue"] = rev
            data["estimated_num_employees"] = emp
            cache_conn.execute("UPDATE companies SET data_json = ? WHERE apollo_id = ?", (json.dumps(data), org_id))
        else:
            # Create a mock Apollo data_json so build_unified_db.py can extract it later
            mock_data = {"annual_revenue": rev, "estimated_num_employees": emp}
            cache_conn.execute(
                "INSERT INTO companies (apollo_id, name, data_json, first_seen, last_seen) VALUES (?, ?, ?, ?, ?)",
                (org_id, company_name, json.dumps(mock_data), time.time(), time.time())
            )
        cache_conn.commit()
    except Exception as e:
        print(f"Failed to update cache DB with RR metrics for {org_id}: {e}", file=sys.stderr)
    finally:
        if 'cache_conn' in locals():
            cache_conn.close()

    return metrics


def _apollo_company_lookup(company_name: str) -> dict:
    import os, requests
    api_key = os.environ.get("APOLLO_API_KEY")
    if not api_key:
        return {}
    try:
        headers = {"X-Api-Key": api_key, "Cache-Control": "no-cache"}
        search_resp = requests.post(
            "https://api.apollo.io/api/v1/mixed_companies/search",
            headers=headers,
            timeout=20,
            json={"q_organization_name": company_name, "page": 1, "per_page": 1},
        )
        if search_resp.status_code == 200:
            orgs = search_resp.json().get("organizations", [])
            if orgs:
                org = orgs[0]
                return {
                    "revenue": org.get("annual_revenue") or org.get("organization_revenue"),
                    "employees": org.get("estimated_num_employees")
                }
    except Exception as e:
        print(f"[apollo] company lookup failed for {company_name}: {e}")
    return {}

def _insert_live_contacts(org_id: str, contacts_list: list, source: str):
    acn = org_id.replace('asic_', '').replace('rr_', '')
    try:
        live_conn = sqlite3.connect(str(DATA_DIR / "unified_companies.db"))
        live_conn.execute("UPDATE companies SET has_contacts = 1 WHERE acn = ?", (acn,))
        
        live_conn.execute("DELETE FROM contacts WHERE org_id = ?", (org_id,))
        import time
        now = time.time()
        for c in contacts_list:
            name = c.get("name")
            title = c.get("title") or c.get("current_title")
            email = c.get("email") or c.get("current_work_email")
            linkedin = c.get("linkedin_url") or c.get("linkedin")
            
            live_conn.execute("""
                INSERT INTO contacts (org_id, acn, name, title, email, linkedin_url, source, updated_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (org_id, acn, name, title, email, linkedin, source, now, json.dumps(c)))
            
        live_conn.commit()
    except Exception as e:
        pass
    finally:
        if 'live_conn' in locals():
            live_conn.close()


def save_contacts(org_id: str, contacts_list: list, source: str):
    import time, json
    now = time.time()
    conn = _unlisted_cache_conn()
    try:
        conn.execute("INSERT OR REPLACE INTO contacts_cache (org_id, contacts_json, fetched_at) VALUES (?, ?, ?)",
                     (org_id, json.dumps(contacts_list), now))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
        
    _insert_live_contacts(org_id, contacts_list, source)


@app.get("/api/unlisted/contacts/{org_id}")
def find_contacts(org_id: str, source: str = "auto", force: bool = False):
    """Find CEO/CFO contacts for a company by Apollo organization id.

    Two Apollo calls, on demand only (never automatic for a whole result
    set): mixed_people/api_search to find candidates (free, obfuscated names),
    then people/match per candidate to reveal full name + verified email
    (costs a real Apollo credit per candidate — capped at 2 per company).
    """
    conn = _unlisted_cache_conn()
    try:
        row = conn.execute(
            "SELECT contacts_json, fetched_at FROM contacts_cache WHERE org_id = ?", (org_id,)
        ).fetchone()
    finally:
        conn.close()
    
    if row and (time.time() - row[1]) < _CONTACTS_CACHE_TTL and not force:
        cached_data = json.loads(row[0])
        if cached_data:  # Ignore empty cached results ([]) to force re-fetch with new fuzzy logic
            rev, emp = None, None
            cache_conn = _unlisted_cache_conn()
            try:
                comp_row = cache_conn.execute("SELECT data_json FROM companies WHERE apollo_id = ?", (org_id,)).fetchone()
                if comp_row and comp_row[0]:
                    data = json.loads(comp_row[0])
                    rev = data.get("annual_revenue") or data.get("organization_revenue") or data.get("revenue")
                    emp = data.get("estimated_num_employees") or data.get("employees")
            except Exception:
                pass
            finally:
                cache_conn.close()
            return {"contacts": cached_data, "fromCache": True, "fetchedAt": row[1], "revenue": rev, "employees": emp}

    # If user explicitly requested RocketReach - go straight there regardless of org_id prefix
    if source == "rocketreach":
        rr_name, _ = _company_identity_for_org(org_id)
        rr_contacts = _rocketreach_find_contacts(rr_name)
        metrics = _fetch_and_persist_rr_metrics(org_id, rr_name)
        now = time.time()
        conn = _unlisted_cache_conn()
        try:
            save_contacts(org_id, rr_contacts, "rocketreach")
        finally:
            conn.close()
        return {"contacts": rr_contacts, "fromCache": False, "fetchedAt": now, "source": "rocketreach", "revenue": metrics.get("revenue"), "employees": metrics.get("employees")}

    # Companies discovered outside Apollo (rr_ = RocketReach, asic_ = ASIC
    # infringement prospects) don't exist in Apollo's org namespace — its
    # people search can't resolve them, so go straight to RocketReach by
    # company name unless caller explicitly requested Apollo.
    if source != "apollo" and org_id.startswith(("rr_", "asic_")):
        rr_name, _ = _company_identity_for_org(org_id)
        rr_contacts = _rocketreach_find_contacts(rr_name)
        metrics = _fetch_and_persist_rr_metrics(org_id, rr_name)
        now = time.time()
        conn = _unlisted_cache_conn()
        try:
            save_contacts(org_id, rr_contacts, "rocketreach")
        finally:
            conn.close()
        return {"contacts": rr_contacts, "fromCache": False, "fetchedAt": now, "source": "rocketreach", "revenue": metrics.get("revenue"), "employees": metrics.get("employees")}

    api_key = os.environ.get("APOLLO_API_KEY")
    if not api_key:
        return {"contacts": [], "fromCache": False, "reason": "No Apollo API key configured"}

    headers = {"X-Api-Key": api_key, "Cache-Control": "no-cache"}
    try:
        search_resp = requests.post(
            "https://api.apollo.io/api/v1/mixed_people/api_search",
            headers=headers,
            timeout=20,
            json={"organization_ids": [org_id], "person_titles": _CONTACT_TITLES, "page": 1, "per_page": 10},
        )
        _record_apollo_status(search_resp, include_rate=False)
        if search_resp.status_code == 429:
            raise HTTPException(429, "Apollo people-search rate limit reached — try again shortly.")
        search_resp.raise_for_status()
        candidates = search_resp.json().get("people", [])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Apollo people search failed: {e}")

    candidates = [c for c in candidates if _is_decision_maker_title(c.get("title"))]
    candidates.sort(key=lambda p: _contact_title_rank(p.get("title")))
    top_candidates = candidates[:2]  # cap real credit spend: at most 2 reveals per company

    company_name, _company_domain = _company_identity_for_org(org_id)

    # No Apollo candidates at all - try RocketReach before concluding
    # "nobody found"; whatever the answer, it's cacheable.
    if not top_candidates:
        rr_contacts = _rocketreach_find_contacts(company_name)
        metrics = _fetch_and_persist_rr_metrics(org_id, company_name)
        now = time.time()
        conn = _unlisted_cache_conn()
        try:
            save_contacts(org_id, rr_contacts, "rocketreach")
        finally:
            conn.close()
        return {"contacts": rr_contacts, "fromCache": False, "fetchedAt": now, "source": "rocketreach", "revenue": metrics.get("revenue"), "employees": metrics.get("employees")}

    contacts = []
    enrich_failed = False
    for c in top_candidates:
        person_id = c.get("id")
        if not person_id:
            continue
        try:
            enrich_resp = requests.post(
                "https://api.apollo.io/api/v1/people/match",
                headers=headers,
                timeout=20,
                json={"id": person_id},
            )
            _record_apollo_status(enrich_resp, include_rate=False)
            if enrich_resp.status_code in (402, 422):
                # Apollo's lead-credit balance, not the API rate limit, is
                # exhausted — this happened silently before and got cached as
                # a false "no contacts found" for 30 days. Never do that again.
                enrich_failed = True
                continue
            enrich_resp.raise_for_status()
            person = enrich_resp.json().get("person") or {}
        except Exception:
            enrich_failed = True
            continue
        if not person.get("name"):
            continue
            
        phones = []
        for phone in person.get("phone_numbers", []):
            num = phone.get("sanitized_number") or phone.get("raw_number")
            if num and num not in phones:
                phones.append(num)
                
        contacts.append({
            "name": person["name"],
            "title": c.get("title") or person.get("title") or "",
            "email": person.get("email"),
            "emailStatus": person.get("email_status"),
            "linkedinUrl": person.get("linkedin_url"),
            "phoneNumbers": phones,
            "source": "apollo",
        })

    metrics = {}
    if not contacts and enrich_failed:
        # Every Apollo reveal failed (usually exhausted lead credits) —
        # RocketReach can still save the request if it's configured.
        rr_contacts = _rocketreach_find_contacts(company_name)
        if rr_contacts:
            metrics = _fetch_and_persist_rr_metrics(org_id, company_name)
            now = time.time()
            conn = _unlisted_cache_conn()
            try:
                save_contacts(org_id, rr_contacts, "rocketreach")
            finally:
                conn.close()
            return {"contacts": rr_contacts, "fromCache": False, "fetchedAt": now, "source": "rocketreach", "revenue": metrics.get("revenue"), "employees": metrics.get("employees")}
        # Do not cache the failure as "no contacts found." Surface it.
        raise HTTPException(
            502,
            f"Found {len(top_candidates)} candidate(s) but couldn't reveal them "
            "(Apollo lead credits may be exhausted — check Settings > Plans/Billing).",
        )

    # Apollo found people but no usable contact info (the "names but no
    # email or phone" case) — let RocketReach fill the gaps or add people.
    if contacts and not any(c.get("email") or c.get("phoneNumbers") for c in contacts):
        rr_contacts = _rocketreach_find_contacts(company_name)
        if rr_contacts:
            metrics = _fetch_and_persist_rr_metrics(org_id, company_name)
            contacts = _merge_contact_sources(contacts, rr_contacts)

    now = time.time()
    conn = _unlisted_cache_conn()
    try:
        _persist_contacts(conn, org_id, contacts, now)
        conn.commit()
        
        # Check if we already have company metrics cached
        has_metrics = False
        row = conn.execute("SELECT data_json FROM companies WHERE apollo_id = ?", (org_id,)).fetchone()
        if row and row[0]:
            cached_data = json.loads(row[0])
            if cached_data.get("annual_revenue") or cached_data.get("organization_revenue") or cached_data.get("revenue"):
                has_metrics = True
    finally:
        conn.close()

    # If Apollo was used but we still don't have company metrics, fetch them via RocketReach
    if not has_metrics and not metrics:
        metrics = _fetch_and_persist_rr_metrics(org_id, company_name)

    res = {"contacts": contacts, "fromCache": False, "fetchedAt": now}
    if metrics:
        res["revenue"] = metrics.get("revenue")
        res["employees"] = metrics.get("employees")
    return res


@app.get("/api/unlisted/export/contacts.csv")
def export_contacts_csv():
    """Every contact ever revealed, joined with its company, as a CSV whose
    headers match HubSpot's default import mapping. Stopgap until a real
    HubSpot API sync exists (needs a HUBSPOT_API_KEY private-app token) — see
    the HubSpot TODO above _unlisted_companies_upsert."""
    conn = _unlisted_cache_conn()
    try:
        rows = conn.execute(
            "SELECT cc.org_id, cc.contacts_json, cc.fetched_at, c.name, c.domain "
            "FROM contacts_cache cc LEFT JOIN companies c ON c.apollo_id = cc.org_id "
            "WHERE cc.contacts_json != '[]'"
        ).fetchall()
    finally:
        conn.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "First Name", "Last Name", "Email", "Job Title",
        "Company Name", "Website URL", "Phone Number", "LinkedIn URL",
        "Email Status", "Source", "Acquired At",
    ])
    for org_id, contacts_json, fetched_at, company_name, domain in rows:
        for c in json.loads(contacts_json):
            name_parts = (c.get("name") or "").split(" ", 1)
            acquired = datetime.fromtimestamp(fetched_at, tz=timezone.utc).strftime("%Y-%m-%d") if fetched_at else ""
            writer.writerow([
                name_parts[0],
                name_parts[1] if len(name_parts) > 1 else "",
                c.get("email") or "",
                c.get("title") or "",
                company_name or "",
                domain or "",
                "; ".join(c.get("phoneNumbers") or []),
                c.get("linkedinUrl") or "",
                c.get("emailStatus") or "",
                f"{(c.get('source') or 'apollo').replace('+', ' + ').title()} via Unlisted Companies tool",
                acquired,
            ])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="unlisted_contacts_hubspot.csv"'},
    )


@app.get("/api/admin/backfill-apollo-metrics")
def backfill_apollo_metrics(limit: int = 10):
    conn = _unlisted_cache_conn()
    
    # 1. Backfill companies that are in the companies table but missing revenue
    rows = conn.execute("SELECT apollo_id, data_json FROM companies").fetchall()
    count = 0
    backfilled = []
    
    for apollo_id, data_json in rows:
        data = json.loads(data_json) if data_json else {}
        rev = data.get("annual_revenue") or data.get("organization_revenue") or data.get("revenue")
        if not rev:
            name, _ = _company_identity_for_org(apollo_id)
            if not name:
                name = data.get("name")
            if name:
                try:
                    metrics = _fetch_and_persist_rr_metrics(apollo_id, name)
                    if metrics:  # only count if we didn't get rate limited early return
                        count += 1
                        backfilled.append(name)
                        if count >= limit:
                            break
                except Exception as e:
                    print(f"Failed to backfill {name}: {e}")

    # 2. Backfill companies that have contacts but NO entry (or no revenue) in the companies table
    if count < limit:
        contact_rows = conn.execute("SELECT org_id FROM contacts_cache").fetchall()
        for c_row in contact_rows:
            org_id = c_row[0]
            comp = conn.execute("SELECT data_json FROM companies WHERE apollo_id = ?", (org_id,)).fetchone()
            rev = None
            if comp and comp[0]:
                data = json.loads(comp[0])
                rev = data.get("annual_revenue") or data.get("organization_revenue") or data.get("revenue")
            
            if not rev:
                name, _ = _company_identity_for_org(org_id)
                if name and name not in backfilled:
                    try:
                        metrics = _fetch_and_persist_rr_metrics(org_id, name)
                        if metrics:
                            count += 1
                            backfilled.append(name)
                            if count >= limit:
                                break
                    except Exception as e:
                        print(f"Failed to backfill {name} from contacts: {e}")

    conn.close()
    return {"message": f"Backfilled {count} companies.", "companies": backfilled}

@app.post("/api/admin/migrate-erd")
def migrate_erd():
    import sys, subprocess, os
    from pathlib import Path
    script_path = Path(__file__).parent / "scripts" / "migrate_to_erd.py"
    res = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
    return {"stdout": res.stdout, "stderr": res.stderr}

from pydantic import BaseModel
class SqlReq(BaseModel):
    query: str

from fastapi import BackgroundTasks

@app.post("/api/admin/backfill-infringements")
def backfill_infringements(background_tasks: BackgroundTasks):
    def run_backfill():
        import time
        try:
            live_conn = sqlite3.connect(str(DATA_DIR / "unified_companies.db"))
            live_conn.row_factory = sqlite3.Row
            rows = live_conn.execute("SELECT acn, name FROM companies WHERE EXISTS(SELECT 1 FROM infringements i WHERE i.acn = companies.acn)").fetchall()
            
            for row in rows:
                acn = row['acn']
                name = row['name']
                org_id = f"asic_{acn}"
                
                print(f"Backfilling {name} ({acn})...")
                
                # Fetch metrics
                try:
                    _fetch_and_persist_rr_metrics(org_id, name)
                except Exception as e:
                    print(f"Metrics fetch error for {name}: {e}")
                
                # Fetch contacts
                try:
                    rr_contacts = _rocketreach_find_contacts(name)
                    if rr_contacts:
                        _insert_live_contacts(org_id, rr_contacts, "rocketreach")
                except Exception as e:
                    print(f"Contact fetch error for {name}: {e}")
                    if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                        print("Rate limit or quota hit. Stopping backfill.")
                        break
                
                time.sleep(2)
        except Exception as e:
            print(f"Backfill loop error: {e}")
        finally:
            if 'live_conn' in locals():
                live_conn.close()

    background_tasks.add_task(run_backfill)
    return {"status": "started", "message": "Backfill running in background."}


@app.post("/api/admin/test-infringements")
def test_infringements():
    import json
    p = DATA_DIR / "asic_infringement_notices.json"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {"count": len(data), "sample": data[0] if data else None}
    else:
        return {"error": "file not found", "path": str(p)}


@app.post("/api/admin/debug-migrate")
def debug_migrate():
    from pathlib import Path
    import subprocess, sys
    script = Path(__file__).parent / "scripts" / "migrate_to_erd.py"
    res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    return {"stdout": res.stdout, "stderr": res.stderr}


@app.post("/api/admin/test-rr")
def test_rr():
    import os, requests, json
    rr_key = os.environ.get('ROCKETREACH_API_KEY')
    company_name = 'Sephora Australia Pty Ltd'

    res = requests.get(
        'https://api.rocketreach.co/api/v2/company/lookup',
        headers={'Api-Key': rr_key},
        params={'name': company_name}
    )
    return {"status_code": res.status_code, "json": res.json()}


@app.post("/api/admin/test-rr-person")
def test_rr_person():
    import os, requests, json
    rr_key = os.environ.get('ROCKETREACH_API_KEY')
    company_name = 'Sephora Australia Pty Ltd'

    sr = requests.post(
        "https://api.rocketreach.co/api/v2/person/search",
        headers={"Api-Key": rr_key, "Content-Type": "application/json"},
        timeout=20,
        json={"query": {"current_employer": [f'"{company_name}"']}, "page_size": 2},
    )
    return {"status_code": sr.status_code, "json": sr.json()}


@app.post("/api/admin/test-rr-person-cooper")
def test_rr_person_cooper():
    import os, requests, json
    rr_key = os.environ.get('ROCKETREACH_API_KEY')
    company_name = 'Cooper Energy'

    sr = requests.post(
        "https://api.rocketreach.co/api/v2/person/search",
        headers={"Api-Key": rr_key, "Content-Type": "application/json"},
        timeout=20,
        json={"query": {"current_employer": [f'"{company_name}"']}, "page_size": 1},
    )
    return {"status_code": sr.status_code, "json": sr.json()}


@app.post("/api/admin/test-rr-person-lookup")
def test_rr_person_lookup():
    import os, requests, json
    rr_key = os.environ.get('ROCKETREACH_API_KEY')
    pid = 77050780

    lr = requests.get(
        "https://api.rocketreach.co/api/v2/person/lookup",
        headers={"Api-Key": rr_key},
        params={"id": pid},
        timeout=30,
    )
    return {"status_code": lr.status_code, "json": lr.json()}

@app.post("/api/admin/sql")
def execute_sql(req: SqlReq):
    import sqlite3
    db_path = DATA_DIR / "unified_companies.db"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(req.query)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

@app.post("/api/admin/sync-live")
def sync_live_db():
    cache_conn = _unlisted_cache_conn()
    live_conn = sqlite3.connect(str(DATA_DIR / "unified_companies.db"))
    
    contacts = cache_conn.execute("SELECT org_id FROM contacts_cache WHERE contacts_json != '[]'").fetchall()
    count_contacts = 0
    for (org_id,) in contacts:
        acn = org_id.replace('asic_', '').replace('rr_', '')
        res = live_conn.execute("UPDATE companies SET has_contacts = 1 WHERE acn = ?", (acn,))
        if res.rowcount > 0: count_contacts += 1

    companies = cache_conn.execute("SELECT apollo_id, data_json FROM companies").fetchall()
    count_metrics = 0
    for (org_id, data_json) in companies:
        if not data_json: continue
        acn = org_id.replace('asic_', '').replace('rr_', '')
        data = json.loads(data_json)
        rev = data.get("annual_revenue") or data.get("organization_revenue") or data.get("revenue")
        emp = data.get("estimated_num_employees") or data.get("employees")
        if rev or emp:
            res = live_conn.execute("UPDATE companies SET revenue = ?, employees = ? WHERE acn = ?", (rev, emp, acn))
            if res.rowcount > 0: count_metrics += 1
            
    live_conn.commit()
    cache_conn.close()
    live_conn.close()
    return {"message": f"Synced {count_contacts} contacts and {count_metrics} metrics"}

@app.post("/api/admin/rebuild-unified")
def admin_rebuild_unified():
    """Manually force a rebuild of the unified database."""
    db_path = DATA_DIR / "unified_companies.db"
    if db_path.exists():
        db_path.unlink()
    journal = db_path.with_suffix(".db-journal")
    if journal.exists():
        journal.unlink()
    
    lock_path = DATA_DIR / ".building.lock"
    if lock_path.exists():
        lock_path.unlink()
        
    global _asic_building
    _asic_building = False
    
    _ensure_asic_register_async()
    return {"status": "rebuilding", "message": "Unified DB deleted and rebuild triggered"}

@app.get("/api/admin/debug")
def debug_info():
    import os
    env_vars = {
        "DATA_DIR_env": os.environ.get("DATA_DIR"),
        "RAILWAY_VOLUME_MOUNT_PATH_env": os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    }
    
    try:
        contents = {}
        for f in os.listdir(DATA_DIR):
            p = DATA_DIR / f
            contents[f] = p.stat().st_size
    except Exception as e:
        contents = str(e)
        
    return {
        "resolved_DATA_DIR": str(DATA_DIR),
        "env": env_vars,
        "contents": contents
    }

@app.get("/api/admin/system-status")
def system_status():
    status = {}
    
    # 1. Unified DB
    unified_db_path = DATA_DIR / "unified_companies.db"
    lock_path = DATA_DIR / ".building.lock"
    is_building = _asic_building or lock_path.exists()
    
    status["unified_db"] = {
        "exists": unified_db_path.exists(),
        "building": is_building,
        "last_modified": unified_db_path.stat().st_mtime if unified_db_path.exists() else None,
        "size_mb": round(unified_db_path.stat().st_size / (1024 * 1024), 2) if unified_db_path.exists() else 0
    }
    
    # 2. ASIC Register DB
    asic_db_path = DATA_DIR / "asic_register_v2.sqlite3"
    status["asic_register"] = {
        "exists": asic_db_path.exists(),
        "building": is_building,
        "last_modified": asic_db_path.stat().st_mtime if asic_db_path.exists() else None,
        "size_mb": round(asic_db_path.stat().st_size / (1024 * 1024), 2) if asic_db_path.exists() else 0
    }
    
    # 3. ASIC Infringements
    inf_path = DATA_DIR / "asic_infringement_notices.json"
    status["infringements"] = {
        "exists": inf_path.exists(),
        "last_modified": inf_path.stat().st_mtime if inf_path.exists() else None,
        "size_kb": round(inf_path.stat().st_size / 1024, 2) if inf_path.exists() else 0
    }
    
    # 4. Apollo
    api_key = os.environ.get("APOLLO_API_KEY")
    apollo_status_dict = apollo_status()
    status["apollo"] = {
        "configured": bool(api_key),
        "rate_limited": apollo_status_dict.get("rateLimited", False),
        "credits_exhausted": apollo_status_dict.get("creditsExhausted", False),
        "hourly_left": apollo_status_dict.get("hourlyLeft"),
        "hourly_limit": apollo_status_dict.get("hourlyLimit"),
        "last_checked": apollo_status_dict.get("checkedAt")
    }
    
    # 5. RocketReach
    rr_key = os.environ.get(_ROCKETREACH_API_KEY_ENV)
    status["rocketreach"] = {
        "configured": bool(rr_key)
    }
    # 6. Disk usage
    import shutil
    disk = shutil.disk_usage(str(DATA_DIR))
    status["disk"] = {
        "total_gb": round(disk.total / (1024**3), 2),
        "used_gb": round(disk.used / (1024**3), 2),
        "free_gb": round(disk.free / (1024**3), 2),
        "used_pct": round(disk.used / disk.total * 100, 1)
    }
    
    # 7. All DB files on volume
    db_files = []
    for f in DATA_DIR.iterdir():
        if f.suffix in (".sqlite3", ".db") or f.name.endswith(".db"):
            db_files.append({"name": f.name, "size_mb": round(f.stat().st_size / (1024*1024), 1)})
    status["volume_files"] = sorted(db_files, key=lambda x: x["size_mb"], reverse=True)
    
    return status

# ── Serve built Vite frontend (production only) ──────────────────────────────
# In development, Vite's dev server handles the frontend.
# In production (Docker / Railway), the built files live at webapp/dist.

from fastapi.responses import FileResponse
import os

@app.post("/api/admin/purge-old-dbs")
def purge_old_dbs():
    """Delete legacy DB files to free disk space before a fresh build."""
    deleted = []
    freed_mb = 0
    for old_name in ["asic_register_v2.sqlite3", "asic_register.sqlite3", "asic_register_v2.building.sqlite3", "unified_companies.building.sqlite3"]:
        p = DATA_DIR / old_name
        if p.exists():
            size_mb = round(p.stat().st_size / (1024*1024), 1)
            p.unlink()
            deleted.append(f"{old_name} ({size_mb}MB)")
            freed_mb += size_mb
    # Also delete stale lock
    lock = DATA_DIR / ".building.lock"
    if lock.exists():
        lock.unlink()
        deleted.append(".building.lock")
    return {"deleted": deleted, "freed_mb": round(freed_mb, 1)}


@app.post("/api/admin/rebuild-db")
def rebuild_db():
    """Force a fresh rebuild of unified_companies.db."""
    global _asic_building
    if _asic_building:
        return {"status": "already_building"}
    _ensure_asic_register_async()
    return {"status": "build_started"}


@app.get("/api/admin/download-db")
def download_unified_db():
    """Download the raw unified database."""
    db_path = DATA_DIR / "unified_companies.db"
    if not db_path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "Database not found or still building.")
    return FileResponse(db_path, filename="unified_companies.db")

@app.post("/api/unlisted/migrate")
def migrate_db(req: Request):
    try:
        script_path = HERE / "scripts" / "migrate_contacts.py"
        res = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, check=True)
        return {"ok": True, "output": res.stdout}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"Migration failed: {e.stderr}")

_FRONTEND_DIR = (HERE / "../dist").resolve()

if _FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="assets")

@app.get('/api/admin/force-fix')
def force_fix():
    import json, traceback
    conn = _unlisted_cache_conn()
    contact_rows = conn.execute('SELECT org_id FROM contacts_cache').fetchall()
    
    backfilled = []
    errors = []
    
    for c_row in contact_rows:
        org_id = c_row[0]
        comp = conn.execute('SELECT data_json FROM companies WHERE apollo_id = ?', (org_id,)).fetchone()
        rev = None
        if comp and comp[0]:
            data = json.loads(comp[0])
            rev = data.get('annual_revenue') or data.get('organization_revenue') or data.get('revenue')
            
        if not rev:
            name, _ = _company_identity_for_org(org_id)
            if not name and org_id.startswith('asic_'):
                # Hardcoded fallback since JSON fails
                names = {'089376349': 'MERCANTILE MUTUAL', '096437900': 'Cooper Energy', '158929938': 'VIVA ENERGY', '160056548': 'MACQUARIE GROUP', '169030737': 'Sephora', '657632972': 'ZIP CO'}
                name = names.get(org_id.split('_')[1])
                
            if name:
                try:
                    metrics = _fetch_and_persist_rr_metrics(org_id, name)
                    if metrics:
                        backfilled.append(name)
                    else:
                        errors.append(f'{name}: fetch returned empty')
                except Exception as e:
                    errors.append(f'{name}: {traceback.format_exc()}')
    
    conn.close()
    return {'message': 'Forced fix', 'companies': backfilled, 'errors': errors}

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str = ""):
        """Catch-all: serve index.html for any non-API path (SPA client-side routing)."""
        index = _FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        raise HTTPException(404, "Frontend not built.")











