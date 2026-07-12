import sqlite3
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", HERE.parent.parent / "data")))

def main():
    unified_db_path = DATA_DIR / "unified_companies.db"
    cache_db_path = DATA_DIR / "unlisted_search_cache.sqlite3"
    infringements_json_path = DATA_DIR / "asic_infringement_notices.json" if (DATA_DIR / "asic_infringement_notices.json").exists() else HERE.parent / "asic_infringement_notices.json"
    
    if not unified_db_path.exists():
        print("unified_companies.db not found.")
        return

    conn = sqlite3.connect(str(unified_db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")

    print("Creating ERD tables...")
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS infringements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acn TEXT,
            name TEXT,
            notice_date TEXT,
            offence TEXT,
            penalty_paid TEXT,
            amount REAL,
            url TEXT,
            raw_json TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_infringements_acn ON infringements(acn)")
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            org_id TEXT PRIMARY KEY,
            acn TEXT,
            revenue REAL,
            employees INTEGER,
            source TEXT,
            updated_at REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_acn ON metrics(acn)")
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id TEXT,
            acn TEXT,
            name TEXT,
            title TEXT,
            email TEXT,
            linkedin_url TEXT,
            source TEXT,
            updated_at REAL,
            raw_json TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_acn ON contacts(acn)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_acn_name ON contacts(acn, name)")
    
    # company_news: never DROP — scraped data is expensive to regenerate.
    # Use CREATE IF NOT EXISTS then ALTER to add any missing columns.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS company_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acn TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'AFR',
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            summary TEXT,
            fetched_at REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_company_news_acn ON company_news(acn)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_company_news_source ON company_news(source)")
    # Add source column if this is an older schema that doesn't have it yet
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(company_news)").fetchall()]
    if 'source' not in existing_cols:
        conn.execute("ALTER TABLE company_news ADD COLUMN source TEXT NOT NULL DEFAULT 'AFR'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_company_news_source ON company_news(source)")
    # published_at: date the article was published at the source (nullable, backfilled later)
    if 'published_at' not in existing_cols:
        conn.execute("ALTER TABLE company_news ADD COLUMN published_at TEXT")
    # Backfill any rows that have a null source
    conn.execute("UPDATE company_news SET source = 'AFR' WHERE source IS NULL OR source = ''")

    # NOTE: companies filter indexes (status, type, class, subclass) are NOT created here.
    # Building indexes on 4.4M rows takes 10-30 minutes and would block startup.
    # Apply them once via /api/admin/sql after initial data load.

    # Remove any bad metrics/contacts rows where acn is not a valid 9-digit ASIC ACN
    # (i.e. Apollo hex IDs that were imported by mistake — safe to run repeatedly, fast DELETEs)
    conn.execute("DELETE FROM metrics WHERE org_id NOT LIKE 'asic_%' AND org_id NOT LIKE 'rr_%'")
    conn.execute("DELETE FROM contacts WHERE LENGTH(acn) != 9 OR CAST(acn AS INTEGER) = 0")

    
    print("Migrating Infringements...")
    conn.execute("DROP TABLE IF EXISTS infringements")
    conn.execute("""
        CREATE TABLE infringements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acn TEXT,
            name TEXT,
            notice_date TEXT,
            offence TEXT,
            penalty_paid TEXT,
            amount REAL,
            url TEXT,
            raw_json TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_infringements_acn ON infringements(acn)")
    if infringements_json_path.exists():
        with open(infringements_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            acn = str(item.get("acn", item.get("licenceOrAcn", "")))
            import re
            acn_match = re.search(r'(\d[\d\s]*\d)', acn)
            if not acn_match:
                continue
            acn = acn_match.group(1).replace(" ", "").zfill(9)
            conn.execute("""
                INSERT INTO infringements (acn, name, notice_date, offence, penalty_paid, amount, url, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                acn,
                item.get("name"),
                item.get("date") or item.get("datePaid"),
                item.get("offence"),
                item.get("penaltyPaid"),
                item.get("amount"),
                item.get("noticePdfUrl") or item.get("url"),
                json.dumps(item)
            ))
            
    print("Migrating Metrics...")
    # ONLY import rows where org_id is asic_ or rr_ prefixed — Apollo hex IDs cannot join to companies
    if cache_db_path.exists():
        cache_conn = sqlite3.connect(str(cache_db_path))
        companies = cache_conn.execute("SELECT apollo_id, data_json, last_seen FROM companies").fetchall()
        for org_id, data_json, last_seen in companies:
            if not data_json: continue
            # GUARD: skip any row where org_id is not in ASIC ACN format
            if not (org_id.startswith('asic_') or org_id.startswith('rr_')):
                continue
            acn = None
            if org_id.startswith('asic_'):
                acn = org_id.replace('asic_', '').zfill(9)
            elif org_id.startswith('rr_'):
                acn = org_id.replace('rr_', '').zfill(9)

            data = json.loads(data_json)
            rev = data.get("annual_revenue") or data.get("organization_revenue") or data.get("revenue")
            emp = data.get("estimated_num_employees") or data.get("employees")
            source = data.get("dataSource") or ("apollo" if not org_id.startswith('rr_') else "rocketreach")

            if rev or emp:
                conn.execute("""
                    INSERT OR REPLACE INTO metrics (org_id, acn, revenue, employees, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (org_id, acn, rev, emp, source, last_seen))

        print("Migrating Contacts...")
        # Never DELETE — use INSERT OR IGNORE to add new contacts without wiping prod data
        try:
            contacts = cache_conn.execute("SELECT org_id, contacts_json, fetched_at FROM contacts_cache").fetchall()
            for org_id, contacts_json, fetched_at in contacts:
                if not contacts_json or contacts_json == '[]': continue
                
                acn = None
                if org_id.startswith('asic_'):
                    acn = org_id.replace('asic_', '')
                elif org_id.startswith('rr_'):
                    acn = org_id.replace('rr_', '')
                    
                clist = json.loads(contacts_json)
                for c in clist:
                    name = c.get("name")
                    title = c.get("title") or c.get("current_title")
                    email = c.get("email") or c.get("current_work_email")
                    linkedin = c.get("linkedin_url") or c.get("linkedin")
                    source = "rocketreach" if org_id.startswith('rr_') or c.get("current_work_email") else "apollo"
                    
                    conn.execute("""
                        INSERT OR IGNORE INTO contacts (org_id, acn, name, title, email, linkedin_url, source, updated_at, raw_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (org_id, acn, name, title, email, linkedin, source, fetched_at, json.dumps(c)))
        except sqlite3.OperationalError:
            pass # contacts_cache might not exist
        cache_conn.close()

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    main()
