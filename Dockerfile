# ── Build stage: React frontend ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy entire app directory first
COPY app/ .

# Install dependencies
RUN npm ci --verbose

# Build for production
ENV NODE_ENV=production
RUN npm run build

# Verify build succeeded
RUN test -d dist || (echo "❌ React build failed - dist/ not found" && exit 1)
RUN ls -la dist/ || echo "Dist contents:"

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
COPY --from=builder /app/dist ./app/dist

# Copy .env files for reference (not used in container, will be set via Coolify)
COPY .env.example .

# Port (can be overridden by Coolify)
ENV PORT=8080
EXPOSE 8080

# Run FastAPI with Uvicorn, using PORT environment variable
CMD ["sh", "-c", "python -m uvicorn api:app --host 0.0.0.0 --port ${PORT}"]