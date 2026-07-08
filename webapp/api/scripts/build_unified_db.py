import sqlite3
import json
import os
import re
import csv
import io
import urllib.request
import zipfile
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", HERE.parent)))

_ASIC_DATASET_API = "https://data.gov.au/data/api/3/action/package_show?id=asic-companies"

# Same normalization as main.py
SUFFIX_RE = re.compile(
    r"\b(PTY LTD|PTY LIMITED|PTY\. LTD\.|PTY\. LIMITED|LTD|LIMITED|LTD\.|LIMITED\.|NL|N\.L\.|INC|INC\.|INCORPORATED|CORP|CORPORATION|LLC|L\.L\.C\.|PLC|P\.L\.C\.)\b"
)
PUNCT_RE = re.compile(r"[^\w\s]")

def normalize_company_name(name: str) -> str:
    name = name.upper()
    name = SUFFIX_RE.sub("", name)
    name = PUNCT_RE.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()

def _resolve_asic_zip_url() -> str:
    """Ask data.gov.au's CKAN API for this week's company register download link (filename changes monthly)."""
    req = urllib.request.Request(_ASIC_DATASET_API, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        meta = json.loads(r.read().decode("utf-8"))
    zips = [res for res in meta["result"]["resources"] if (res.get("format") or "").upper() == "ZIP"]
    if not zips:
        raise RuntimeError("No ZIP resource found in ASIC company dataset metadata")
    return zips[0]["url"]

def build_unified():
    cache_db_path = DATA_DIR / "unlisted_search_cache.sqlite3"
    infringements_path = DATA_DIR / "asic_infringement_notices.json"
    
    tmp_db_path = DATA_DIR / "unified_companies.building.sqlite3"
    final_db_path = DATA_DIR / "unified_companies.db"
    
    if tmp_db_path.exists():
        tmp_db_path.unlink()
    
    journal_path = tmp_db_path.with_suffix(".sqlite3-journal")
    if journal_path.exists():
        journal_path.unlink()
        
    conn = sqlite3.connect(str(tmp_db_path))
    c = conn.cursor()
    c.execute("PRAGMA temp_store = FILE")
    c.execute("PRAGMA cache_size = -10000") # 10MB cache max
    c.execute("PRAGMA synchronous = OFF")
    c.execute("PRAGMA journal_mode = MEMORY")
    
    c.execute("""
        CREATE TABLE companies (
            acn TEXT PRIMARY KEY,
            name TEXT,
            name_norm TEXT,
            status TEXT,
            type TEXT,
            class TEXT,
            subclass TEXT,
            state TEXT,
            is_large_prop BOOLEAN,
            has_infringement BOOLEAN,
            revenue REAL,
            employees INTEGER,
            has_contacts BOOLEAN
        )
    """)
    
    print("[asic] Refreshing company register index (~1-2 min, ~3.5M rows)...", file=sys.stderr)
    url = _resolve_asic_zip_url()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        zip_bytes = io.BytesIO(resp.read())

    # Preload infringements
    print("Loading infringements...", file=sys.stderr)
    inf_by_name = {}
    if infringements_path.exists():
        with open(infringements_path, "r", encoding="utf-8") as f:
            notices = json.load(f)
            for n in notices:
                norm = normalize_company_name(n.get("name", ""))
                if norm:
                    inf_by_name[norm] = True

    print("Importing ASIC companies from ZIP...", file=sys.stderr)
    row_count = 0
    with zipfile.ZipFile(zip_bytes) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(csv_name) as f:
            wrapper = io.TextIOWrapper(f, encoding="utf-8-sig")
            reader = csv.DictReader(wrapper, delimiter="\t")
            
            batch = []
            for row in reader:
                # Strip keys in case of whitespace
                row = {k.strip(): v for k, v in row.items() if k}
                name_raw = row.get("Company Name", "")
                if not name_raw:
                    continue
                    
                norm = normalize_company_name(name_raw)
                is_large_prop = 1 if row.get("Class") in ('APTY', 'LMSH', 'PROP') else 0
                has_inf = 1 if norm in inf_by_name else 0
                
                batch.append((
                    row.get("ACN"), name_raw, norm, row.get("Status"), 
                    row.get("Type"), row.get("Class"), row.get("Sub Class"), row.get("State Registration number"),
                    is_large_prop, has_inf, None, None, 0
                ))
                
                row_count += 1
                if len(batch) >= 100000:
                    c.executemany("""
                        INSERT OR IGNORE INTO companies (
                            acn, name, name_norm, status, type, class, subclass, state, 
                            is_large_prop, has_infringement, revenue, employees, has_contacts
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    batch.clear()
            
            if batch:
                c.executemany("""
                    INSERT OR IGNORE INTO companies (
                        acn, name, name_norm, status, type, class, subclass, state, 
                        is_large_prop, has_infringement, revenue, employees, has_contacts
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)

    conn.commit()
    print(f"Imported {row_count} ASIC companies.", file=sys.stderr)
    
    # Apply Apollo Cache (Revenue, Employees, Contacts)
    print("Applying Apollo cache...", file=sys.stderr)
    if cache_db_path.exists():
        c.execute(f"ATTACH DATABASE '{cache_db_path}' AS cache")
        
        # Contacts
        c.execute("""
            UPDATE companies 
            SET has_contacts = 1 
            WHERE acn IN (
                SELECT REPLACE(org_id, 'asic_', '') 
                FROM cache.contacts_cache 
                WHERE contacts_json != '[]'
            )
        """)
        
        # Revenue/Employees from companies table
        c.execute("""
            UPDATE companies
            SET 
                revenue = json_extract(c2.data_json, '$.annual_revenue'),
                employees = json_extract(c2.data_json, '$.estimated_num_employees')
            FROM cache.companies c2
            WHERE companies.acn = REPLACE(c2.apollo_id, 'asic_', '')
        """)
        conn.commit()

    print("Creating indexes...", file=sys.stderr)
    c.execute("CREATE INDEX idx_name_norm ON companies(name_norm)")
    c.execute("CREATE INDEX idx_revenue ON companies(revenue)")
    c.execute("CREATE INDEX idx_status ON companies(status)")
    c.execute("CREATE INDEX idx_has_infringement ON companies(has_infringement)")
    c.execute("CREATE INDEX idx_is_large_prop ON companies(is_large_prop)")
    c.execute("CREATE INDEX idx_has_contacts ON companies(has_contacts)")
    
    conn.close()
    
    # Swap in the new database
    if final_db_path.exists():
        final_db_path.unlink()
    tmp_db_path.rename(final_db_path)
    
    # Cleanup duplicate databases if they exist to instantly reclaim ~1GB disk space
    for old_db in ["asic_register_v2.sqlite3", "asic_register.sqlite3"]:
        old_path = DATA_DIR / old_db
        if old_path.exists():
            old_path.unlink()
            
    print("Unified DB built successfully.", file=sys.stderr)

if __name__ == "__main__":
    build_unified()
