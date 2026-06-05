"""
server.py — ScoutIQ MCP Server (Day 6)

Exposes 5 MongoDB-backed tools to a Gemini agent via the Model Context Protocol.

Tools:
  1. search_players        — vector similarity search (Atlas $vectorSearch)
  2. get_player_profile    — exact player lookup (tournament_profiles + master)
  3. get_match_timeline    — match-by-match breakdown (player_match_stats)
  4. get_team_players      — squad/roster lookup by nationality + year
  5. resolve_player_position — real-time position resolution for "Unknown" positions

Run locally (stdio mode, for Agent Builder):
    python mcp_server/server.py

Run as HTTP server (for Cloud Run):
    Is not; python mcp_server/server.py --transport streamable-http --port 8080
    is now; uvicorn mcp_server.asgi:app --host 0.0.0.0 --port $PORT 
"""
import os
import sys
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# ── Vertex AI credentials ─────────────────────────────────────────────────────
# For Cloud Run: Uses Application Default Credentials (ADC) automatically
# For local dev: Uses GOOGLE_APPLICATION_CREDENTIALS from .env if present
_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
if _creds:
    _path = Path(_creds)
    if not _path.is_absolute():
        _path = ROOT / _creds.lstrip("./\\")
    if _path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_path)
    # else: Cloud Run doesn't need this; ADC will handle it

GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "aideplus")
GCP_REGION  = os.getenv("GCP_REGION", "us-central1")
EMBED_DIM   = 768
INDEX_NAME  = "player_embedding_index"

# ── MongoDB ───────────────────────────────────────────────────────────────────
_mongo_client: MongoClient | None = None

def _get_db():
    global _mongo_client
    if _mongo_client is None:
        uri = os.getenv("MONGODB_CLUSTER_CONNECTION")
        if not uri:
            logger.error("MONGODB_CLUSTER_CONNECTION env var is missing or empty")
            raise ValueError("MONGODB_CLUSTER_CONNECTION not configured")
        
        # Log URI for debugging (obfuscate password)
        uri_preview = uri.split("@")[0] + "@***" if "@" in uri else uri[:50] + "..."
        logger.info(f"Connecting to MongoDB: {uri_preview}")
        
        try:
            _mongo_client = MongoClient(uri, serverSelectionTimeoutMS=10000)
            # Test connection
            _mongo_client.admin.command('ping')
            logger.info("✅ MongoDB connected and ping successful")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {type(e).__name__}: {e}")
            raise
    return _mongo_client["scoutiq"]


# ── Vertex AI embedding (lazy init) ──────────────────────────────────────────
_embed_model = None

def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        import vertexai
        from vertexai.language_models import TextEmbeddingModel
        vertexai.init(project=GCP_PROJECT, location=GCP_REGION)
        _embed_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    return _embed_model


def _embed_query(text: str) -> list[float]:
    try:
        from vertexai.language_models import TextEmbeddingInput
        logger.info(f"Embedding query: {text[:50]}...")
        model  = _get_embed_model()
        inputs = [TextEmbeddingInput(text, "RETRIEVAL_QUERY")]
        result = model.get_embeddings(inputs, output_dimensionality=EMBED_DIM)
        logger.info(f"✅ Embedding successful: {len(result[0].values)} dims")
        return result[0].values
    except Exception as e:
        logger.error(f"❌ Embedding failed: {type(e).__name__}: {e}")
        raise


def _doc_clean(doc: dict) -> dict:
    """Remove MongoDB internals and large embedding vectors from results."""
    doc.pop("_id", None)
    doc.pop("embedding", None)
    return doc


def _name_query(player_name: str) -> dict:
    """
    Build a MongoDB OR query that matches player_name by:
      1. Case-insensitive substring regex on player_name (works for accented exact matches)
      2. player_id slug match (handles ASCII-only input like 'Mbappe' → 'kylian-mbappe')
    """
    import unicodedata, re as _re

    # Slugify the input the same way ingest scripts do
    norm  = unicodedata.normalize("NFKD", player_name)
    ascii_str = norm.encode("ascii", "ignore").decode("ascii")
    slug  = _re.sub(r"[^\w\s-]", "", ascii_str).strip().lower()
    slug  = _re.sub(r"[\s_]+", "-", slug)

    return {
        "$or": [
            {"player_name": {"$regex": player_name, "$options": "i"}},
            {"player_id":   {"$regex": slug,        "$options": "i"}},
        ]
    }


# ── MCP server ────────────────────────────────────────────────────────────────
mcp = FastMCP(
    "scoutiq",
    host="0.0.0.0",
    instructions=(
        "ScoutIQ tools provide real FIFA World Cup player statistics from 1998–2026. "
        "Always use these tools to retrieve real data — never hallucinate stats. "
        "When a player's position is 'Unknown' or missing, call resolve_player_position."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1: search_players
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def search_players(
    query_text: str,
    tournament_year: Optional[int] = None,
    position: Optional[str] = None,
    nationality: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """
    Semantic similarity search for players matching a description or playing style.
    Embeds query_text and runs Atlas $vectorSearch over all World Cup tournament
    profiles (1998–2026).

    Use this for:
    - "who plays like Iniesta?"
    - "find a fast pacey winger"
    - "similar to Modric but younger"
    - "best defensive midfielder in 2026"

    Args:
        query_text:      Natural-language description of the player or style.
        tournament_year: Restrict to a specific WC year (e.g. 2026).
        position:        Filter by position string (e.g. "Midfielder", "Forward").
        nationality:     Filter by nationality (e.g. "France", "Brazil").
        limit:           Number of results to return (default 5, max 20).

    Returns:
        List of player tournament profiles ranked by similarity, each with:
        player_name, nationality, position, tournament_year, goals, matches_played,
        goals_per90, pass_completion_pct, dribble_success_pct, furthest_stage_reached,
        data_tier, and a vectorSearchScore.
    """
    try:
        logger.info(f"search_players: query='{query_text}', year={tournament_year}, pos={position}")
        limit = min(limit, 20)
        query_vector = _embed_query(query_text)

        vector_filter: dict = {}
        if tournament_year is not None:
            vector_filter["tournament_year"] = {"$eq": tournament_year}
        if nationality:
            # Exact match — agent should pass exact string from prior get_player_profile results
            vector_filter["nationality"] = {"$eq": nationality}

        pipeline: list[dict] = [
            {
                "$vectorSearch": {
                    "index": INDEX_NAME,
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": limit * 15,
                    "limit": limit * 3 if position else limit,
                    **({"filter": vector_filter} if vector_filter else {}),
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        # Position filter applied post-vector-search (regex, not filter field)
        if position:
            pipeline.append({
                "$match": {
                    "position": {"$regex": position, "$options": "i"},
                }
            })
            pipeline.append({"$limit": limit})

        pipeline.append({
            "$project": {
                "_id": 0,
                "embedding": 0,
                "embedding_text": 0,
            }
        })

        db = _get_db()
        results = list(db["player_tournament_profiles"].aggregate(pipeline))
        logger.info(f"✅ search_players returned {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"❌ search_players failed: {type(e).__name__}: {e}", exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2: get_player_profile
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_player_profile(
    player_name: str,
    tournament_year: Optional[int] = None,
) -> dict:
    """
    Exact or fuzzy lookup for a player's World Cup tournament profile(s).
    Also returns the player's master record (career stats, active_at_2026_wc).

    Use this for:
    - "Mbappé's 2018 World Cup stats"
    - "Griezmann's full World Cup record"
    - "Is Pedri in the 2026 squad?"
    - "What's Ronaldo's career World Cup goals?"

    Args:
        player_name:     Player name (accents optional, partial match supported).
        tournament_year: If given, return only that year's profile. Otherwise all.

    Returns:
        {
          "master": { player_id, nationality, positions, active_at_2026_wc,
                      career_wc_goals, career_wc_matches, tournaments_played, ... },
          "tournament_profiles": [ { full stats per WC year ... }, ... ]
        }
    """
    try:
        logger.info(f"get_player_profile: player='{player_name}', year={tournament_year}")
        db = _get_db()
        base_q = _name_query(player_name)

        # Tournament profiles
        prof_query: dict = dict(base_q)
        if tournament_year:
            prof_query = {"$and": [base_q, {"tournament_year": tournament_year}]}
        profiles = list(
            db["player_tournament_profiles"]
            .find(prof_query, {"embedding": 0, "embedding_text": 0})
            .sort("tournament_year", 1)
        )
        for p in profiles:
            p.pop("_id", None)

        # Master record
        master_doc = db["players_master"].find_one(
            base_q,
            {"_id": 0},
        )

        logger.info(f"✅ get_player_profile: found {len(profiles)} profiles, master={bool(master_doc)}")
        return {
            "master": master_doc or {},
            "tournament_profiles": profiles,
        }
    except Exception as e:
        logger.error(f"❌ get_player_profile failed: {type(e).__name__}: {e}", exc_info=True)
        return {"master": {}, "tournament_profiles": []}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3: get_match_timeline
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_match_timeline(
    player_name: str,
    tournament_year: int,
) -> list[dict]:
    """
    Returns match-by-match stats for a player in a specific World Cup tournament.
    Only available for WC 2018 and 2022 (StatsBomb full data). WC 2026 populates
    after matches are played and ingested.

    Use this for:
    - "How did Mbappé perform across all his 2022 matches?"
    - "Show me Modric's match-by-match goals and passes in 2018"
    - "Did De Bruyne play every match in 2022?"

    Args:
        player_name:     Player name (partial match supported).
        tournament_year: World Cup year (2018, 2022, or 2026).

    Returns:
        List of match records sorted by date, each with:
        match_date, competition_stage, home_team, away_team, result,
        goals, shots, passes, pass_completion_pct, dribbles, pressures,
        tackles, minutes_played.
    """
    db = _get_db()
    base_q = _name_query(player_name)
    q = {"$and": [base_q, {"tournament_year": tournament_year}]}
    docs = list(
        db["player_match_stats"]
        .find(q, {"_id": 0})
        .sort("match_date", 1)
    )
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4: get_team_players
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_team_players(
    nationality: str,
    tournament_year: Optional[int] = None,
    position: Optional[str] = None,
    active_2026_only: bool = False,
) -> list[dict]:
    """
    Returns all players for a national team in a specific World Cup, ranked by goals per 90.
    Can also list a team's current 2026 squad from players_master.

    Use this for:
    - "France's 2026 midfielders"
    - "Who are Brazil's forwards in 2022?"
    - "Who replaced Griezmann in France's 2026 squad?"
    - "Germany's full 2026 World Cup squad"

    Args:
        nationality:     Country name (e.g. "France", "Brazil", "Germany").
        tournament_year: WC year. If None, returns all appearances.
        position:        Filter by position (e.g. "Midfielder", "Forward", "Defender").
        active_2026_only: If True, only return players with active_at_2026_wc=True
                          (uses players_master, ignores tournament_year).

    Returns:
        List of player profiles sorted by goals_per90 descending (or master records
        if active_2026_only=True).
    """
    db = _get_db()

    nat_q = {"nationality": {"$regex": nationality, "$options": "i"}}

    if active_2026_only:
        master_query: dict = {**nat_q, "active_at_2026_wc": True}
        if position:
            master_query["positions_list"] = {"$regex": position, "$options": "i"}
        docs = list(db["players_master"].find(master_query, {"_id": 0, "embedding": 0}))
        return docs

    prof_query: dict = dict(nat_q)
    if tournament_year:
        prof_query["tournament_year"] = tournament_year
    if position:
        prof_query["position"] = {"$regex": position, "$options": "i"}

    docs = list(
        db["player_tournament_profiles"]
        .find(prof_query, {"_id": 0, "embedding": 0, "embedding_text": 0})
        .sort("goals_per90", -1)
    )
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Tool 5: resolve_player_position
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def resolve_player_position(
    player_name: str,
    nationality: str = "",
    persist: bool = False,
) -> dict:
    """
    Resolves a player's position when the database value is "Unknown" or missing.
    Queries football-data.org squad data and Wikipedia as fallback sources.

    Use this when:
    - A player profile shows position = "Unknown" or positions_list is empty
    - The agent needs a confirmed position to filter or compare players

    Args:
        player_name:  Full player name.
        nationality:  Player's nationality (helps disambiguation).
        persist:      If True, write the resolved position back to MongoDB
                      players_master and player_tournament_profiles (updates DB).

    Returns:
        {
          "position":   str | null,  # resolved position string or null if not found
          "source":     str,         # "fdo_squad" | "fdo_persons" | "wikipedia" | "not_found"
          "confidence": str,         # "high" | "medium" | "low"
        }
    """
    sys.path.insert(0, str(ROOT))
    from agent.position_resolver import resolve_position, resolve_and_persist

    if persist:
        db = _get_db()
        pm = db["players_master"]
        # Find player_id
        master = pm.find_one(
            {"player_name": {"$regex": player_name, "$options": "i"}},
            {"player_id": 1},
        )
        if master:
            result = resolve_and_persist(player_name, str(master["_id"]), db)
            return result

    return resolve_position(player_name, nationality)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ScoutIQ MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport mode (default: stdio for Agent Builder)",
    )
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8080)))
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.settings.port = args.port
        mcp.settings.host = args.host
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
