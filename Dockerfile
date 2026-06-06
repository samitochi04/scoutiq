# ── ScoutIQ Backend (FastAPI) ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
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

# Port
ENV PORT=8000
EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["sh", "-c", "python -m uvicorn api:app --host 0.0.0.0 --port ${PORT}"]