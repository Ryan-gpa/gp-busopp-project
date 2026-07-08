import sqlite3
import urllib.request
import zipfile
import csv
import os
import requests
from bs4 import BeautifulSoup
from io import BytesIO

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'companies.db')

def get_latest_asic_url():
    # Attempt to find the dataset URL via data.gov.au API
    print("Searching data.gov.au for ASIC Company dataset...")
    search_url = "https://data.gov.au/api/3/action/package_search?q=title:ASIC%20Company"
    try:
        r = requests.get(search_url)
        data = r.json()
        if data.get("success"):
            for result in data["result"]["results"]:
                if "asic-company" in result["name"] or "asic company" in result["title"].lower():
                    for res in result["resources"]:
                        if res["format"].lower() in ["zip", "csv"]:
                            print(f"Found URL: {res['url']}")
                            return res['url']
    except Exception as e:
        print("API search failed:", e)
        pass
    
    # Fallback to a known dataset page
    print("Trying fallback search...")
    fallback_page = "https://data.gov.au/data/dataset/asic-company"
    r = requests.get(fallback_page)
    soup = BeautifulSoup(r.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        if 'asic' in a['href'].lower() and ('zip' in a['href'].lower() or 'csv' in a['href'].lower()):
            return a['href']
    
    return None

def setup_db():
    print(f"Setting up database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS asic_companies (
            acn TEXT PRIMARY KEY,
            company_name TEXT,
            status TEXT,
            type TEXT,
            class TEXT,
            subclass TEXT,
            registration_date TEXT,
            state TEXT,
            postcode TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS enriched_data (
            acn TEXT PRIMARY KEY,
            revenue REAL,
            employees INTEGER,
            contacts_json TEXT,
            last_enriched TEXT
        )
    ''')
    
    # Create indexes for fast filtering
    c.execute('CREATE INDEX IF NOT EXISTS idx_state ON asic_companies(state)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_status ON asic_companies(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_type ON asic_companies(type)')
    
    conn.commit()
    return conn

def import_local_csv(conn, csv_path):
    print("Importing to SQLite from local CSV...")
    c = conn.cursor()
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        first_line = f.readline()
        delimiter = '\t' if '\t' in first_line else ','
        
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader)
        header_lower = [h.lower() for h in header]
        
        def get_idx(keywords):
            for i, h in enumerate(header_lower):
                if any(k in h for k in keywords):
                    return i
            return -1
            
        idx_name = get_idx(["name", "company name"])
        idx_acn = get_idx(["acn"])
        idx_status = get_idx(["status"])
        idx_type = get_idx(["type"])
        idx_class = get_idx(["class"])
        idx_subclass = get_idx(["sub class", "subclass"])
        idx_date = get_idx(["registration"])
        idx_state = get_idx(["state"])
        idx_postcode = get_idx(["postcode"]) 
        
        if idx_name == -1 or idx_acn == -1:
            print("Could not find required columns in header:", header)
            return
            
        count = 0
        batch_size = 10000
        rows = []
        
        for row in reader:
            if len(row) <= max(idx_name, idx_acn):
                continue
                
            name = row[idx_name]
            acn = row[idx_acn]
            status = row[idx_status] if idx_status != -1 and len(row) > idx_status else ""
            ctype = row[idx_type] if idx_type != -1 and len(row) > idx_type else ""
            cclass = row[idx_class] if idx_class != -1 and len(row) > idx_class else ""
            csubclass = row[idx_subclass] if idx_subclass != -1 and len(row) > idx_subclass else ""
            cdate = row[idx_date] if idx_date != -1 and len(row) > idx_date else ""
            cstate = row[idx_state] if idx_state != -1 and len(row) > idx_state else ""
            cpostcode = row[idx_postcode] if idx_postcode != -1 and len(row) > idx_postcode else ""
            
            if "REGD" not in status.upper() and "REGISTERED" not in status.upper():
                continue
                
            rows.append((acn, name, status, ctype, cclass, csubclass, cdate, cstate, cpostcode))
            
            if len(rows) >= batch_size:
                c.executemany("INSERT OR REPLACE INTO asic_companies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
                conn.commit()
                rows = []
                count += batch_size
                
        if rows:
            c.executemany("INSERT OR REPLACE INTO asic_companies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
            conn.commit()
            count += len(rows)
            
    print(f"Finished! Imported {count} active companies.")

def download_and_import(conn, url):
    print(f"Downloading data from {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    
    # We will stream the download as it can be very large
    response = urllib.request.urlopen(req)
    
    # If it's a ZIP file, extract the CSV in memory (might be too large for RAM, let's save to disk first)
    temp_zip = "temp_asic.zip"
    temp_csv = "temp_asic.csv"
    
    if url.lower().endswith('.zip'):
        print("Saving ZIP to disk...")
        with open(temp_zip, 'wb') as f:
            while True:
                chunk = response.read(1024 * 1024 * 10) # 10MB chunks
                if not chunk:
                    break
                f.write(chunk)
        
        print("Extracting CSV...")
        with zipfile.ZipFile(temp_zip, 'r') as z:
            csv_filename = [name for name in z.namelist() if name.lower().endswith('.csv')][0]
            with z.open(csv_filename) as zf, open(temp_csv, 'wb') as f:
                while True:
                    chunk = zf.read(1024 * 1024 * 10)
                    if not chunk:
                        break
                    f.write(chunk)
        
        os.remove(temp_zip)
    else:
        print("Saving CSV to disk...")
        with open(temp_csv, 'wb') as f:
            while True:
                chunk = response.read(1024 * 1024 * 10)
                if not chunk:
                    break
                f.write(chunk)

    import_local_csv(conn, temp_csv)
    os.remove(temp_csv)

if __name__ == "__main__":
    mock_csv = os.path.join(os.path.dirname(__file__), 'asic_mock.csv')
    conn = setup_db()
    if os.path.exists(mock_csv):
        print(f"Using local mock CSV: {mock_csv}")
        # Call the import part of the function by refactoring download_and_import slightly
        # For simplicity in testing, let's just copy the import logic here:
        import_local_csv(conn, mock_csv)
    else:
        url = get_latest_asic_url()
        if not url:
            print("Could not find download URL for ASIC dataset.")
            print("Please manually download the CSV and import it, or provide a direct link.")
        else:
            download_and_import(conn, url)
    conn.close()
