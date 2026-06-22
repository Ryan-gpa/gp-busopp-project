"""Run at Docker build time to pre-cache the ASX listed companies CSV."""
import csv
import json
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "asx_companies_cache.json"
URL = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"

try:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        content = r.read().decode("utf-8", errors="replace")

    rows = list(csv.reader(content.splitlines()))
    companies = [
        {"code": row[1].strip().upper(), "name": row[0].strip()}
        for row in rows[2:]
        if len(row) >= 2 and row[1].strip() and row[0].strip()
    ]

    OUT.write_text(json.dumps({"companies": companies, "ts": 0}))
    print(f"[build] Pre-fetched {len(companies)} ASX companies → {OUT}", file=sys.stderr)

except Exception as e:
    print(f"[build] Warning: ASX prefetch failed (combobox will lazy-load at runtime): {e}", file=sys.stderr)
    # Non-fatal — build continues without the cache file
    sys.exit(0)
