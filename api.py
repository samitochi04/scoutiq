"""
api.py — ScoutIQ Frontend API

FastAPI backend that bridges the React frontend with the Google ADK agent.
Exposes:
  POST /api/chat      — query the agent, streams SSE events
  GET  /api/health    — health check
  GET  /              — serves the built React app (production)

Run locally:
    uvicorn api:app --host 0.0.0.0 --port 8001 --reload

Environment variables:
  MONGODB_CLUSTER_CONNECTION — MongoDB Atlas URI
  GOOGLE_APPLICATION_CREDENTIALS — GCP service account key path
  GCP_PROJECT_ID — GCP project ID (default: aideplus)
  GCP_REGION — GCP region (default: us-central1)
  AGENT_BUILDER_URL — (optional) override agent endpoint
"""

import os
import json
import logging
import uuid
import base64
import tempfile
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ── Setup ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── Credentials ───────────────────────────────────────────────────────────────
# Priority:
# 1. GCP_SERVICE_ACCOUNT_JSON (base64-encoded) — from Coolify secrets
# 2. GOOGLE_APPLICATION_CREDENTIALS (file path) — from local .env or direct env var
# 3. Application Default Credentials (ADC) — if on Google Cloud

_creds_b64 = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "")
if _creds_b64:
    # Decode base64 and write to temp file
    try:
        creds_json = base64.b64decode(_creds_b64).decode("utf-8")
        # Write to temp file that persists for container lifetime
        creds_path = Path("/tmp/gcp_credentials.json")
        creds_path.write_text(creds_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)
        logger.info("✅ GCP credentials loaded from GCP_SERVICE_ACCOUNT_JSON")
    except Exception as e:
        logger.error(f"❌ Failed to decode GCP_SERVICE_ACCOUNT_JSON: {e}")
        raise RuntimeError("Invalid GCP_SERVICE_ACCOUNT_JSON: must be valid base64")
else:
    # Fall back to file path (local dev)
    _creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if _creds:
        _path = Path(_creds)
        if not _path.is_absolute():
            _path = ROOT / _creds.lstrip("./\\")
        if _path.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_path)
            logger.info(f"✅ GCP credentials loaded from file: {_path}")
        else:
            logger.warning(f"⚠️  GCP credentials file not found: {_path}")
    else:
        logger.info(
            "⏳ No GOOGLE_APPLICATION_CREDENTIALS set — using Application Default Credentials"
        )

GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "aideplus")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")

# ── ADK Agent ────────────────────────────────────────────────────────────────
_runner = None
_session_service = None
_agent = None


def _get_agent_and_runner():
    """Initialize and return the ADK agent and runner from agent.py"""
    global _runner, _session_service, _agent

    if _runner is None:
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from agent.agent import root_agent

            _agent = root_agent
            _session_service = InMemorySessionService()
            _runner = Runner(
                agent=_agent,
                app_name="scoutiq",
                session_service=_session_service,
            )
            logger.info(
                f"✅ ScoutIQ Agent initialized: {_agent.name} (model: {_agent.model})"
            )
        except ImportError as e:
            logger.error(f"❌ Failed to import agent.py: {e}")
            raise RuntimeError(
                "ScoutIQ agent not available. Check that agent.py exists and google-adk is installed."
            )
        except Exception as e:
            logger.error(f"❌ ADK Runner initialization failed: {e}")
            raise RuntimeError(f"Failed to initialize ScoutIQ agent: {e}")

    return _runner, _session_service, _agent


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="ScoutIQ API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── Request model ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    mode: str = "Full Report"
    session_id: str = ""


# ── SSE helpers ───────────────────────────────────────────────────────────────
def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"


# ── Stream agent response ─────────────────────────────────────────────────────
async def stream_agent_response(
    query: str, mode: str, session_id: str
) -> AsyncGenerator[str, None]:
    """
    Stream the agent response as SSE events using the ScoutIQ agent from agent.py.

    Events:
      {"type": "thinking", "step": "...", "tool": "...", "status": "running"|"done"}
      {"type": "token", "content": "..."}
      {"type": "similar", "players": [...]}
      {"type": "done", "confidence": "HIGH"|"MEDIUM"|"LOW", "report": "..."}
      {"type": "error", "message": "..."}
    """
    try:
        # Initialize agent and runner from agent.py
        runner, session_service, agent = _get_agent_and_runner()

        from google.genai import types as genai_types

        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"Using agent '{agent.name}' for query: {query[:80]}...")

        # Create or get session
        try:
            session = await session_service.create_session(
                app_name="scoutiq",
                user_id="frontend_user",
                session_id=session_id,
            )
        except Exception as e:
            logger.debug(f"Session creation info: {e}")

        # Build message with mode prefix
        full_query = f"[Mode: {mode}]\n\n{query}" if mode != "Full Report" else query

        message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=full_query)],
        )

        full_report = ""
        seen_tools = set()
        confidence = "MEDIUM"

        # Stream agent response
        async for event in runner.run_async(
            user_id="frontend_user",
            session_id=session_id,
            new_message=message,
        ):
            if hasattr(event, "content") and event.content:
                for part in event.content.parts or []:
                    # Function call
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        tool_key = f"{fc.name}-running"
                        if tool_key not in seen_tools:
                            seen_tools.add(tool_key)
                            step_label = _tool_label(fc.name)
                            yield sse_event(
                                {
                                    "type": "thinking",
                                    "step": step_label,
                                    "tool": fc.name,
                                    "status": "running",
                                }
                            )

                    # Function response
                    if hasattr(part, "function_response") and part.function_response:
                        fr = part.function_response
                        tool_key = f"{fr.name}-done"
                        if tool_key not in seen_tools:
                            seen_tools.add(tool_key)
                            result_count = None
                            if isinstance(fr.response, list):
                                result_count = len(fr.response)

                            # Check for similar players
                            if fr.name == "search_players" and isinstance(
                                fr.response, list
                            ):
                                yield sse_event(
                                    {"type": "similar", "players": fr.response}
                                )

                            yield sse_event(
                                {
                                    "type": "thinking",
                                    "step": _tool_label(fr.name),
                                    "tool": fr.name,
                                    "status": "done",
                                    "result_count": result_count,
                                }
                            )

                    # Text response (streamed tokens) — directly from agent
                    if hasattr(part, "text") and part.text:
                        # Only yield if from the agent, not from sub-agents
                        if event.author == runner.agent.name:
                            chunk = part.text
                            full_report += chunk
                            yield sse_event({"type": "token", "content": chunk})

                            # Detect confidence from agent's report text
                            if "HIGH" in chunk and "confidence" in chunk.lower():
                                confidence = "HIGH"
                            elif "MEDIUM" in chunk and "confidence" in chunk.lower():
                                confidence = "MEDIUM"
                            elif "LOW" in chunk and "confidence" in chunk.lower():
                                confidence = "LOW"

        # Send final report
        yield sse_event(
            {
                "type": "done",
                "confidence": confidence,
                "report": full_report,
            }
        )
        yield sse_done()

    except RuntimeError as e:
        # Agent initialization error
        logger.error(f"❌ Agent initialization error: {e}")
        yield sse_event(
            {
                "type": "error",
                "message": f"Agent initialization error: {str(e)}",
                "details": "Ensure GOOGLE_APPLICATION_CREDENTIALS is set and agent.py is available.",
            }
        )
        yield sse_done()
    except Exception as e:
        logger.error(f"❌ Agent execution error: {e}", exc_info=True)
        yield sse_event(
            {
                "type": "error",
                "message": f"Agent error: {str(e)}",
                "details": "Check server logs and ensure MongoDB/GCP credentials are configured.",
            }
        )
        yield sse_done()


def _tool_label(tool_name: str) -> str:
    labels = {
        "search_players": "Searching player database...",
        "get_player_profile": "Fetching player profile...",
        "get_match_timeline": "Loading match timeline...",
        "get_team_players": "Querying team roster...",
        "resolve_player_position": "Resolving player position...",
        "google_search": "Searching the web for live updates...",
    }
    return labels.get(tool_name, f"Running {tool_name}...")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ScoutIQ API"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if len(request.query) > 2000:
        raise HTTPException(status_code=400, detail="Query too long (max 2000 chars)")

    logger.info(f"Chat request: query='{request.query[:60]}...', mode={request.mode}")

    return StreamingResponse(
        stream_agent_response(request.query, request.mode, request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Serve React build (production) ────────────────────────────────────────────
_react_build = ROOT / "app" / "dist"
if _react_build.exists():
    app.mount("/", StaticFiles(directory=str(_react_build), html=True), name="static")
    logger.info(f"✅ Serving React build from {_react_build}")
else:

    @app.get("/")
    async def root():
        return JSONResponse(
            {
                "service": "ScoutIQ API",
                "note": "React build not found. Run 'npm run build' in the app/ directory.",
                "endpoints": ["/api/health", "/api/chat"],
            }
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8001))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
