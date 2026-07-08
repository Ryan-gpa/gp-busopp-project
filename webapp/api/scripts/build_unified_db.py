import sqlite3
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

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

def build_unified():
    DATA_DIR = Path(os.environ.get("DATA_DIR", os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", HERE.parent)))
    asic_db_path = DATA_DIR / "asic_register_v2.sqlite3"
    cache_db_path = DATA_DIR / "unlisted_search_cache.sqlite3"
    infringements_path = DATA_DIR / "asic_infringement_notices.json"
    unified_db_path = DATA_DIR / "unified_companies.db"
    
    if unified_db_path.exists():
        os.remove(unified_db_path)
    
    journal_path = unified_db_path.with_suffix(".db-journal")
    if journal_path.exists():
        os.remove(journal_path)
        
    conn = sqlite3.connect(str(unified_db_path))
    c = conn.cursor()
    
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
    
    if not asic_db_path.exists():
        print(f"ASIC DB not found at {asic_db_path}")
        return

    # 1. Attach ASIC DB
    c.execute(f"ATTACH DATABASE '{asic_db_path}' AS asic")
    
    print("Importing ASIC companies...")
    c.execute("""
        INSERT OR IGNORE INTO companies (
            acn, name, name_norm, status, type, class, subclass, state, 
            is_large_prop, has_infringement, revenue, employees, has_contacts
        )
        SELECT 
            acn, name, name_norm, status, type, class, sub_class, state_registration_number,
            CASE WHEN class IN ('APTY', 'LMSH', 'PROP') THEN 1 ELSE 0 END,
            0, NULL, NULL, 0
        FROM asic.companies
    """)
    
    conn.commit()
    
    # 2. Add Infringements
    print("Applying infringements...")
    if infringements_path.exists():
        with open(infringements_path, "r", encoding="utf-8") as f:
            notices = json.load(f)
            for n in notices:
                norm = normalize_company_name(n.get("name", ""))
                if norm:
                    c.execute("UPDATE companies SET has_infringement = 1, is_large_prop = 1 WHERE name_norm = ?", (norm,))
        conn.commit()
        
    # 3. Add Apollo Cache (Revenue, Employees, Contacts)
    print("Applying Apollo cache...")
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
        # We need to extract this from JSON. SQLite has JSON functions!
        c.execute("""
            UPDATE companies
            SET 
                revenue = json_extract(c2.data_json, '$.annual_revenue'),
                employees = json_extract(c2.data_json, '$.estimated_num_employees')
            FROM cache.companies c2
            WHERE companies.acn = REPLACE(c2.apollo_id, 'asic_', '')
        """)
        conn.commit()

    c.execute("CREATE INDEX idx_name_norm ON companies(name_norm)")
    c.execute("CREATE INDEX idx_revenue ON companies(revenue)")
    c.execute("CREATE INDEX idx_status ON companies(status)")
    c.execute("CREATE INDEX idx_has_infringement ON companies(has_infringement)")
    c.execute("CREATE INDEX idx_is_large_prop ON companies(is_large_prop)")
    c.execute("CREATE INDEX idx_has_contacts ON companies(has_contacts)")
    
    conn.close()
    print("Unified DB built successfully.")

if __name__ == "__main__":
    build_unified()
