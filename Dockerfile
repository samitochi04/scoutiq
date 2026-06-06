# ── Build stage: React frontend ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app/build

# Copy React app files
COPY app/package*.json ./
RUN npm ci

COPY app/ .
RUN npm run build

# ── Runtime stage: Python API ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python source code
COPY api.py .
COPY agent/ ./agent/
COPY embed/ ./embed/
COPY ingestion/ ./ingestion/
COPY transform/ ./transform/
COPY data/ ./data/

# Copy built React frontend from builder stage
COPY --from=builder /app/build/dist ./app/dist

# Copy .env files for reference (not used in container, will be set via Coolify)
COPY .env.example .

# Port
ENV PORT=8080
EXPOSE 8080

# Run FastAPI with Uvicorn
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]