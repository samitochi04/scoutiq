"""
asgi.py — ASGI wrapper for FastMCP server

Exposes the MCP server as an ASGI application for Cloud Run + uvicorn.

Run locally:
    uvicorn mcp_server.asgi:app --reload --port 8080

Run in Cloud Run:
    gcloud run deploy scoutiq-mcp --source . --region us-central1 --allow-unauthenticated
"""
import os
import sys
from pathlib import Path
from starlette.applications import Starlette
from starlette.routing import Mount

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# Set up Vertex AI credentials
# For Cloud Run: Uses Application Default Credentials (ADC) automatically
# For local dev: Uses GOOGLE_APPLICATION_CREDENTIALS from .env if present
_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
if _creds:
    _path = Path(_creds)
    if not _path.is_absolute():
        _path = ROOT / _creds.lstrip("./\\")
    if _path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_path)

# Import the MCP server
from mcp_server.server import mcp

# Disable host validation — required for Cloud Run's internal routing
mcp.settings.host = "0.0.0.0"

# Expose the ASGI app
app = mcp.sse_app()
http_app = mcp.streamable_http_app()  # POST /mcp               (Agent Builder)

app = Starlette(routes=[
    Mount("/", app=sse_app),       # handles /sse and /messages
    Mount("/mcp", app=http_app),   # handles /mcp for Agent Builder
])