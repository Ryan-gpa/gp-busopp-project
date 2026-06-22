FROM python:3.11-slim

# Install Node.js
RUN apt-get update && apt-get install -y curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY webapp/api/requirements.txt /app/webapp/api/
RUN pip install --no-cache-dir -r /app/webapp/api/requirements.txt

# Node deps for report builder
COPY disclosure-review-kit/package.json /app/disclosure-review-kit/
WORKDIR /app/disclosure-review-kit
RUN npm install

# Node deps + build frontend
WORKDIR /app
COPY webapp/package.json webapp/package-lock.json* /app/webapp/
RUN cd /app/webapp && npm install

# Copy all source
COPY . .

# Build Vite frontend
RUN cd /app/webapp && npm run build

# Pre-fetch ASX company list so the combobox works immediately on cold start
RUN python -c "\
import urllib.request, csv, json, sys; \
url='https://www.asx.com.au/asx/research/ASXListedCompanies.csv'; \
req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'*/*'}); \
try: \
    r=urllib.request.urlopen(req, timeout=30); \
    content=r.read().decode('utf-8', errors='replace'); \
    rows=list(csv.reader(content.splitlines())); \
    companies=[{'code':row[1].strip().upper(),'name':row[0].strip()} for row in rows[2:] if len(row)>=2 and row[1].strip() and row[0].strip()]; \
    open('/app/webapp/api/asx_companies_cache.json','w').write(json.dumps({'companies':companies,'ts':0})); \
    print(f'[build] Pre-fetched {len(companies)} ASX companies', file=sys.stderr) \
except Exception as e: print(f'[build] Warning: ASX prefetch failed (combobox will lazy-load): {e}', file=sys.stderr) \
"

# Runtime dirs
RUN mkdir -p disclosure-review-kit/output disclosure-review-kit/announcements disclosure-review-kit/config

EXPOSE 8000
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "cd /app/webapp/api && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
