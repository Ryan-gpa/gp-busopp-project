# Use official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies and Node.js
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy dependency files first to leverage caching
COPY webapp/api/requirements.txt /app/webapp/api/
RUN pip install --no-cache-dir -r /app/webapp/api/requirements.txt

COPY disclosure-review-kit/package.json /app/disclosure-review-kit/
# Set working directory for npm install
WORKDIR /app/disclosure-review-kit
RUN npm install

# Copy the rest of the application code
WORKDIR /app
COPY . .

# Create output directory (gitignored, won't exist in the repo)
RUN mkdir -p disclosure-review-kit/output

# Expose port (FastAPI default, Railway overrides this with $PORT)
EXPOSE 8000

# Set environment variables
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Command to run the FastAPI app
CMD ["sh", "-c", "cd /app/webapp/api && uvicorn main:app --host 0.0.0.0 --port $PORT"]
