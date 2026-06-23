FROM python:3.11-slim

# Install Node.js + LibreOffice (headless DOCX → PDF conversion)
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg libreoffice-nogui \
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
RUN python /app/webapp/api/fetch_companies.py

# Runtime dirs
RUN mkdir -p disclosure-review-kit/output disclosure-review-kit/announcements disclosure-review-kit/config

EXPOSE 8000
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "cd /app/webapp/api && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
