import sys
import time
from pathlib import Path

def run():
    main_py = Path("webapp/api/main.py")
    content = main_py.read_text(encoding="utf-8")
    
    start_str = '@app.post("/api/unlisted/search")\nasync def unlisted_search(body: dict):'
    end_str = 'return {**result, "fetchedAt": now, "fromCache": False}'
    
    if start_str not in content or end_str not in content:
        print("Could not find bounds")
        return
        
    start_idx = content.find(start_str)
    end_idx = content.find(end_str) + len(end_str)
    
    replacement = '''@app.post("/api/unlisted/search")
async def unlisted_search(body: dict):
    revenue_min = body.get("revenueMin")
    revenue_max = body.get("revenueMax")
    company_name = body.get("companyName")
    only_proprietary = body.get("onlyProprietary", False)
    only_infringements = body.get("onlyInfringements", False)
    only_with_contacts = body.get("onlyWithContacts", False)
    asic_status_filter = body.get("asicStatusFilter", "all")

    db_path = HERE / ".." / "unified_companies.db"
    if not db_path.exists():
        return {"error": "Database not found. Please trigger the ASIC data load first."}
        
    query = """
        SELECT 
            acn, name, name_norm, status, type, class, subclass, state, 
            is_large_prop, has_infringement, revenue, employees, has_contacts
        FROM companies
        WHERE 1=1
    """
    params = []
    
    if company_name and company_name.strip():
        query += " AND name_norm LIKE ?"
        # Note: normalize_company_name must be defined above
        norm = normalize_company_name(company_name.strip())
        params.append(f"%{norm}%")
        
    if revenue_min is not None:
        try:
            rmin = float(revenue_min)
            # Show companies that meet revenue OR haven't been enriched yet
            query += " AND (revenue >= ? OR revenue IS NULL)"
            params.append(rmin)
        except (ValueError, TypeError):
            pass
            
    if revenue_max is not None:
        try:
            rmax = float(revenue_max)
            query += " AND (revenue <= ? OR revenue IS NULL)"
            params.append(rmax)
        except (ValueError, TypeError):
            pass
            
    if only_proprietary:
        query += " AND is_large_prop = 1"
        
    if only_infringements:
        query += " AND has_infringement = 1"
        
    if only_with_contacts:
        query += " AND has_contacts = 1"
        
    if asic_status_filter != "all":
        if asic_status_filter == "pending":
            query += " AND status NOT IN ('REGD', 'DRGD')"
        else:
            query += " AND status = 'REGD'" if asic_status_filter == "verified" else " AND status != 'REGD'"

    query += " LIMIT 500"
    
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        rows = c.execute(query, params).fetchall()
        
        results = []
        for row in rows:
            org = {
                "id": f"asic_{row['acn']}",
                "name": row['name'],
                "annual_revenue": row['revenue'],
                "estimated_num_employees": row['employees'],
                "domain": "",
                "dataSource": "asic",
                "has_contacts": bool(row['has_contacts'])
            }
            _validation_statuses[org['id']] = {
                "status": "verified" if row['status'] == 'REGD' else "deregistered",
                "reason": f"ASIC Status: {row['status']}",
                "acn": row['acn'],
                "type": row['type'],
                "class": row['class'],
                "subclass": row['subclass'],
                "state": row['state']
            }
            if row['has_infringement']:
                org["infringementNotices"] = [{"title": "Infringement Notice"}]
                
            results.append(org)
            
        return {
            "tier1": results,
            "tier2": [],
            "excludedUnderMin": [],
            "excludedOverMax": [],
            "excludedIncompleteData": [],
            "pagination": {"total_pages": 1, "fetched_pages": 1, "rate_limited": False},
            "fetchedAt": time.time(),
            "fromCache": True
        }
    finally:
        conn.close()'''
    
    new_content = content[:start_idx] + replacement + content[end_idx:]
    main_py.write_text(new_content, encoding="utf-8")
    print("Done")

if __name__ == "__main__":
    run()
