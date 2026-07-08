import requests
import json

url = "http://localhost:8000/api/unlisted/search"
payload = {
    "revenueMin": 100,
    "revenueMax": 100000000,
    "locations": ["Australia"]
}

try:
    response = requests.post(url, json=payload)
    print("Status:", response.status_code)
    print("Response:")
    data = response.json()
    print(f"Total Tier 1: {len(data.get('tier1', []))}")
    print(f"Total Tier 2: {len(data.get('tier2', []))}")
    print(f"Total Excluded: {len(data.get('excluded', []))}")
    
    for org in data.get('tier1', []) + data.get('tier2', []):
        print(f"- {org['name']} (Rev: {org.get('annual_revenue')})")
        
except Exception as e:
    print("Error:", e)
