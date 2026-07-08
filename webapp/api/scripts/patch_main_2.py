import sys
from pathlib import Path

def run():
    main_py = Path("webapp/api/main.py")
    content = main_py.read_text(encoding="utf-8")
    
    old_code = """            # Always ensure unified DB is built if it's missing or we just rebuilt the ASIC register
            import api.scripts.build_unified_db as bdb
            print("[asic] Building unified companies DB...")
            bdb.build_unified()"""
            
    new_code = """            # Always ensure unified DB is built if it's missing or we just rebuilt the ASIC register
            print("[asic] Building unified companies DB...")
            import subprocess
            import sys
            script_path = HERE / "scripts" / "build_unified_db.py"
            subprocess.run([sys.executable, str(script_path)], check=True)"""
            
    if old_code not in content:
        print("Could not find old code")
        return
        
    new_content = content.replace(old_code, new_code)
    main_py.write_text(new_content, encoding="utf-8")
    print("Done")

if __name__ == "__main__":
    run()
