import sqlite3
import json
import os
from pathlib import Path

# Paths
_in_prod = os.environ.get("ENVIRONMENT") == "production"
HERE = Path(__file__).parent.resolve()
APP_ROOT = Path("/app") if _in_prod else (HERE / "../../").resolve()
DATA_DIR = Path("/data") if _in_prod else (APP_ROOT / "data").resolve()

UNLISTED_DB_PATH = DATA_DIR / "unlisted_search_cache.sqlite3"
UNIFIED_DB_PATH = DATA_DIR / "unified_companies.db"

def migrate():
    # 1. Add contacts table to unlisted_search_cache
    conn = sqlite3.connect(UNLISTED_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id TEXT,
            name TEXT,
            title TEXT,
            email TEXT,
            email_status TEXT,
            phone TEXT,
            linkedin_url TEXT,
            source TEXT,
            fetched_at REAL,
            UNIQUE(org_id, name)
        )
    """)
    
    # 3. Migrate contacts
    cursor = conn.cursor()
    cursor.execute("SELECT org_id, contacts_json, fetched_at FROM contacts_cache")
    rows = cursor.fetchall()
    
    inserted = 0
    for org_id, contacts_json, fetched_at in rows:
        contacts = json.loads(contacts_json)
        for c in contacts:
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
                    fetched_at
                ))
                inserted += 1
            except Exception as e:
                print(f"Error inserting contact {c.get('name')} for {org_id}: {e}")
                
    conn.commit()
    print(f"Migrated {inserted} contacts to normalized table.")
    conn.close()

if __name__ == "__main__":
    migrate()
