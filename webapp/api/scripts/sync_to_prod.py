"""
sync_to_prod.py
Pushes all locally-scraped data to production Railway DB in bulk batches.
Run after any local scraping session (Apollo, RocketReach, AFR scraper).

Tables synced:
  - company_news  (AFR scraper)
  - metrics       (RocketReach revenue/employees)
  - contacts      (Apollo / RocketReach)
"""
import sqlite3, requests

LOCAL_DB = "webapp/api/unified_companies.db"
PROD_URL = "https://gp-busopp-project-production.up.railway.app/api/admin/sql"
BATCH    = 100  # rows per request

def esc(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"

def run_sql(sql):
    try:
        res = requests.post(PROD_URL, json={"query": sql}, timeout=30)
        if res.status_code != 200:
            return False, res.text[:300]
        return True, None
    except Exception as e:
        return False, str(e)

def sync_table(conn, label, select_sql, insert_prefix, row_to_values):
    rows = conn.execute(select_sql).fetchall()
    print(f"\n[{label}] {len(rows)} rows -> batching {BATCH} per request...")
    total_ok = total_fail = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i+BATCH]
        vals  = ",\n  ".join(f"({row_to_values(r)})" for r in batch)
        sql   = f"{insert_prefix}\nVALUES\n  {vals}"
        ok, err = run_sql(sql)
        if ok:
            total_ok += len(batch)
            print(f"  batch {i//BATCH + 1}: {len(batch)} OK")
        else:
            total_fail += len(batch)
            print(f"  batch {i//BATCH + 1}: FAIL — {err}")
    print(f"  -> {total_ok} synced, {total_fail} failed.")
    return total_ok, total_fail

conn = sqlite3.connect(LOCAL_DB)
conn.row_factory = sqlite3.Row
grand_ok = grand_fail = 0

# ── company_news ──────────────────────────────────────────────────────────────
ok, fail = sync_table(
    conn, "company_news",
    "SELECT acn, source, url, title, summary, fetched_at FROM company_news",
    "INSERT OR IGNORE INTO company_news (acn, source, url, title, summary, fetched_at)",
    lambda r: f"{esc(r['acn'])},{esc(r['source'])},{esc(r['url'])},{esc(r['title'])},{esc(r['summary'])},{r['fetched_at'] or 'NULL'}"
)
grand_ok += ok; grand_fail += fail

# ── metrics ───────────────────────────────────────────────────────────────────
ok, fail = sync_table(
    conn, "metrics",
    "SELECT org_id, acn, revenue, employees, source, updated_at FROM metrics",
    "INSERT OR REPLACE INTO metrics (org_id, acn, revenue, employees, source, updated_at)",
    lambda r: f"{esc(r['org_id'])},{esc(r['acn'])},{r['revenue'] or 'NULL'},{r['employees'] or 'NULL'},{esc(r['source'])},{esc(r['updated_at'])}"
)
grand_ok += ok; grand_fail += fail

# ── contacts ──────────────────────────────────────────────────────────────────
ok, fail = sync_table(
    conn, "contacts",
    "SELECT acn, name, title, email, linkedin_url, source, updated_at, raw_json FROM contacts",
    "INSERT OR IGNORE INTO contacts (acn, name, title, email, linkedin_url, source, updated_at, raw_json)",
    lambda r: f"{esc(r['acn'])},{esc(r['name'])},{esc(r['title'])},{esc(r['email'])},{esc(r['linkedin_url'])},{esc(r['source'])},{esc(r['updated_at'])},{esc(r['raw_json'])}"
)
grand_ok += ok; grand_fail += fail

conn.close()
print(f"\n=== SYNC COMPLETE: {grand_ok} rows synced, {grand_fail} failed ===")
