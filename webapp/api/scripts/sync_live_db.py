import sqlite3
import json

def sync_live_db():
    cache_conn = sqlite3.connect('webapp/data/unlisted_search_cache.sqlite3')
    live_conn = sqlite3.connect('webapp/data/unified_companies.db')
    
    # 1. Sync has_contacts
    contacts = cache_conn.execute("SELECT org_id FROM contacts_cache WHERE contacts_json != '[]'").fetchall()
    count_contacts = 0
    for (org_id,) in contacts:
        acn = org_id.replace('asic_', '').replace('rr_', '')
        res = live_conn.execute("UPDATE companies SET has_contacts = 1 WHERE acn = ?", (acn,))
        if res.rowcount > 0:
            count_contacts += 1

    # 2. Sync revenue and employees
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
            if res.rowcount > 0:
                count_metrics += 1
                
    live_conn.commit()
    cache_conn.close()
    live_conn.close()
    
    print(f"Synced {count_contacts} contacts and {count_metrics} metrics to live DB.")

sync_live_db()
