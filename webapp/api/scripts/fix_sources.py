import sqlite3, json
from pathlib import Path

# Paths
unified_db_path = Path('webapp/api/unified_companies.db')
unlisted_db_path = Path('webapp/api/unlisted_search_cache.sqlite3')

try:
    conn_unified = sqlite3.connect(unified_db_path)
    conn_unlisted = sqlite3.connect(unlisted_db_path)
    
    # Get the sources for each org_id from the contacts table
    rows = conn_unified.execute("SELECT DISTINCT org_id, source FROM contacts WHERE org_id LIKE 'asic_%' AND source IS NOT NULL AND source != ''").fetchall()
    
    updates = 0
    for org_id, source in rows:
        cache_row = conn_unlisted.execute("SELECT contacts_json FROM contacts_cache WHERE org_id = ?", (org_id,)).fetchone()
        if cache_row and cache_row[0]:
            contacts = json.loads(cache_row[0])
            changed = False
            for c in contacts:
                if 'source' not in c or c['source'] != source:
                    c['source'] = source
                    changed = True
            
            if changed:
                conn_unlisted.execute("UPDATE contacts_cache SET contacts_json = ? WHERE org_id = ?", (json.dumps(contacts), org_id))
                updates += 1
                
    conn_unlisted.commit()
    print(f"Fixed {updates} companies in contacts_cache.")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn_unified.close()
    conn_unlisted.close()
