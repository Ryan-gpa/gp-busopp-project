with open("webapp/api/main.py", "a", encoding="utf-8") as f:
    f.write('''
@app.get("/api/admin/system-status")
def system_status():
    status = {}
    
    # 1. Unified DB
    unified_db_path = HERE / ".." / "unified_companies.db"
    status["unified_db"] = {
        "exists": unified_db_path.exists(),
        "building": _asic_building,
        "last_modified": unified_db_path.stat().st_mtime if unified_db_path.exists() else None,
        "size_mb": round(unified_db_path.stat().st_size / (1024 * 1024), 2) if unified_db_path.exists() else 0
    }
    
    # 2. ASIC Register DB
    asic_db_path = HERE / "asic_register_v2.sqlite3"
    status["asic_register"] = {
        "exists": asic_db_path.exists(),
        "building": _asic_building,
        "last_modified": asic_db_path.stat().st_mtime if asic_db_path.exists() else None,
        "size_mb": round(asic_db_path.stat().st_size / (1024 * 1024), 2) if asic_db_path.exists() else 0
    }
    
    # 3. ASIC Infringements
    inf_path = HERE / "asic_infringement_notices.json"
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
    
    return status
''')
