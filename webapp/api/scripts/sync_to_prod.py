"""
sync_to_prod.py
Pushes all locally-scraped data to production Railway DB.
Run after any local scraping session (Apollo, RocketReach, AFR scraper).

Tables synced:
  - contacts      (Apollo / RocketReach)
  - metrics       (RocketReach revenue/employees)
  - company_news  (AFR scraper)
"""
import sqlite3, requests, json, sys

LOCAL_DB = "webapp/api/unified_companies.db"
PROD_URL = "https://gp-busopp-project-production.up.railway.app/api/admin/sql"

def esc(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"

def run_sql(sql):
    res = requests.post(PROD_URL, json={"query": sql}, timeout=20)
    if res.status_code != 200:
        return False, res.text[:200]
    return True, None

def sync_table(conn, name, select_sql, build_insert):
    rows = conn.execute(select_sql).fetchall()
    print(f"\n[{name}] Syncing {len(rows)} rows...")
    ok = fail = 0
    for r in rows:
        sql = build_insert(r)
        success, err = run_sql(sql)
        if success:
            ok += 1
        else:
            print(f"  FAIL: {err}")
            fail += 1
    print(f"  -> {ok} synced, {fail} failed.")
    return ok, fail

conn = sqlite3.connect(LOCAL_DB)
conn.row_factory = sqlite3.Row

total_ok = total_fail = 0

# --- company_news ---
ok, fail = sync_table(
    conn, "company_news",
    "SELECT acn, source, url, title, summary, fetched_at FROM company_news",
    lambda r: (
        f"INSERT OR IGNORE INTO company_news (acn, source, url, title, summary, fetched_at) "
        f"VALUES ({esc(r['acn'])}, {esc(r['source'])}, {esc(r['url'])}, "
        f"{esc(r['title'])}, {esc(r['summary'])}, {r['fetched_at'] or 'NULL'})"
    )
)
total_ok += ok; total_fail += fail

# --- metrics ---
ok, fail = sync_table(
    conn, "metrics",
    "SELECT acn, revenue, employees, source, updated_at FROM metrics",
    lambda r: (
        f"INSERT OR REPLACE INTO metrics (acn, revenue, employees, source, updated_at) "
        f"VALUES ({esc(r['acn'])}, {r['revenue'] or 'NULL'}, {r['employees'] or 'NULL'}, "
        f"{esc(r['source'])}, {esc(r['updated_at'])})"
    )
)
total_ok += ok; total_fail += fail

# --- contacts ---
ok, fail = sync_table(
    conn, "contacts",
    "SELECT acn, name, title, email, linkedin_url, source, updated_at, raw_json FROM contacts",
    lambda r: (
        f"INSERT OR IGNORE INTO contacts (acn, name, title, email, linkedin_url, source, updated_at, raw_json) "
        f"VALUES ({esc(r['acn'])}, {esc(r['name'])}, {esc(r['title'])}, {esc(r['email'])}, "
        f"{esc(r['linkedin_url'])}, {esc(r['source'])}, {esc(r['updated_at'])}, {esc(r['raw_json'])})"
    )
)
total_ok += ok; total_fail += fail

conn.close()
print(f"\n=== SYNC COMPLETE: {total_ok} rows synced, {total_fail} failed ===")
