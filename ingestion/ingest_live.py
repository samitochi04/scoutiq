"""
ingest_live.py — Day 5
Ingest live 2026 WC data after each matchday.

Priority order:
  1. StatsBomb free data  (event-level rich stats, released ~24-48h after each match)
  2. football-data.org    (match scores + cumulative scorers, available immediately)

Run manually after each matchday:
    python ingestion/ingest_live.py

Or via Windows Task Scheduler / cron (runs every 4 hours during tournament):
    python ingestion/ingest_live.py --schedule
"""
import os
import re
import sys
import time
import math
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

MONGO_URI        = os.getenv("MONGODB_CLUSTER_CONNECTION")
FDO_API_KEY      = os.getenv("FOOTBALL_DATA_API_KEY")
GCP_PROJECT      = os.getenv("GCP_PROJECT_ID", "aideplus")
GCP_REGION       = os.getenv("GCP_REGION", "us-central1")
GOOGLE_CREDS     = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

FDO_BASE         = "https://api.football-data.org/v4"
FDO_HEADERS      = {"X-Auth-Token": FDO_API_KEY}
TOURNAMENT_YEAR  = 2026
EMBED_DIM        = 768
EMBED_BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    if not name:
        return ""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_str  = normalized.encode("ascii", "ignore").decode("ascii")
    slug       = re.sub(r"[^\w\s-]", "", ascii_str).strip().lower()
    return re.sub(r"[\s_]+", "-", slug)


def clean_nans(records: list[dict]) -> list[dict]:
    for doc in records:
        for k, v in list(doc.items()):
            if isinstance(v, float) and math.isnan(v):
                doc[k] = None
    return records


def find_existing_player_id(coll, simple_pid: str, nationality: str) -> str | None:
    """Resolve popular-name slug → real player_id in players_master (prefers docs with career data)."""
    tokens = [t for t in simple_pid.split("-") if len(t) > 1]
    if len(tokens) < 2:
        return simple_pid if coll.find_one({"player_id": simple_pid}, {"_id": 1}) else None
    pattern = ".*".join(re.escape(t) for t in tokens)
    query: dict = {"player_id": {"$regex": pattern, "$options": "i"}}
    if nationality:
        query["nationality"] = nationality
    projection = {"player_id": 1, "data_source": 1, "career_wc_goals": 1, "_id": 0}
    candidates = list(coll.find(query, projection))
    if not candidates and nationality:
        del query["nationality"]
        candidates = list(coll.find(query, projection))
    if not candidates:
        return None
    real = [c for c in candidates
            if c.get("data_source") in ("statsbomb", "kaggle") or "career_wc_goals" in c]
    pool = real if real else candidates
    return min(pool, key=lambda x: len(x["player_id"]))["player_id"]


def fdo_get(path: str, params: dict | None = None) -> dict:
    """GET football-data.org with basic rate-limit retry."""
    url = f"{FDO_BASE}{path}"
    for attempt in range(3):
        r = requests.get(url, headers=FDO_HEADERS, params=params, timeout=15)
        if r.status_code == 429:
            time.sleep(60)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed to fetch {url} after 3 attempts")


# ---------------------------------------------------------------------------
# StatsBomb path
# ---------------------------------------------------------------------------

def check_statsbomb_2026() -> int | None:
    """Return season_id if StatsBomb has 2026 WC data, else None."""
    try:
        from statsbombpy import sb
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            comps = sb.competitions()
        row = comps[(comps["competition_id"] == 43) & (comps["season_name"] == "2026")]
        if not row.empty:
            season_id = int(row.iloc[0]["season_id"])
            print(f"  StatsBomb 2026 WC found! season_id={season_id}")
            return season_id
    except Exception as e:
        print(f"  StatsBomb check failed: {e}")
    return None


def ingest_statsbomb_2026(season_id: int, db) -> None:
    """Full event-level ingestion from StatsBomb (same logic as extraction.py + transform.py)."""
    print("  StatsBomb ingestion: re-running extraction for 2026 ...")
    # Import and call extraction functions
    sys.path.insert(0, str(ROOT))
    try:
        from ingestion.extraction import extract_tournament  # type: ignore
        extract_tournament(competition_id=43, season_id=season_id, db=db)
    except ImportError:
        print("  WARNING: Could not import extraction module. Run extraction.py manually for 2026.")


# ---------------------------------------------------------------------------
# football-data.org path
# ---------------------------------------------------------------------------

def ingest_fdo_matches(db) -> list[dict]:
    """Upsert FINISHED 2026 WC matches to `matches` collection. Returns finished match list."""
    print("  Fetching matches from football-data.org ...")
    data     = fdo_get("/competitions/WC/matches")
    matches  = data.get("matches", [])
    finished = [m for m in matches if m["status"] == "FINISHED"]
    print(f"  {len(matches)} total | {len(finished)} FINISHED")

    if not finished:
        return []

    ops = []
    for m in finished:
        doc = {
            "match_id"         : f"fdo_{m['id']}",
            "tournament_year"  : TOURNAMENT_YEAR,
            "date"             : m["utcDate"][:10],
            "home_team"        : m["homeTeam"]["name"],
            "away_team"        : m["awayTeam"]["name"],
            "home_score"       : (m.get("score") or {}).get("fullTime", {}).get("home"),
            "away_score"       : (m.get("score") or {}).get("fullTime", {}).get("away"),
            "stage"            : m.get("stage", ""),
            "group"            : m.get("group"),
            "matchday"         : m.get("matchday"),
            "data_tier"        : "live_summary",
            "last_updated"     : datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        ops.append(UpdateOne({"match_id": doc["match_id"]}, {"$set": doc}, upsert=True))

    if ops:
        res = db["matches"].bulk_write(ops, ordered=False)
        print(f"  [matches] upserted={res.upserted_count} modified={res.modified_count}")

    return finished


def build_live_embedding_text(doc: dict) -> str:
    """Build embedding_text for a live_summary profile (fewer stats than full-tier)."""
    goals   = doc.get("goals", 0) or 0
    assists = doc.get("assists", 0) or 0
    played  = doc.get("matches_played", 0) or 0
    stage   = doc.get("furthest_stage", "In progress")
    return (
        f"{doc.get('player_name', '')}, {doc.get('position', 'Unknown')}, "
        f"{doc.get('nationality', '')}, FIFA World Cup {TOURNAMENT_YEAR}. "
        f"{played} matches played. "
        f"{goals} goals, {assists} assists. "
        f"Team reached {stage}."
    )


def ingest_fdo_scorers(db) -> list[str]:
    """Pull cumulative scorers, upsert player_tournament_profiles. Returns updated player_ids."""
    print("  Fetching scorers from football-data.org ...")
    data    = fdo_get("/competitions/WC/scorers", params={"limit": 100})
    scorers = data.get("scorers", [])
    print(f"  {len(scorers)} scorers found")

    if not scorers:
        return []

    pm              = db["players_master"]
    updated_pids: list[str] = []
    ops             = []

    # Build standings map: team_name → furthest_stage
    stage_map = _build_stage_map(db)

    for entry in scorers:
        player      = entry.get("player", {})
        team        = entry.get("team", {})
        raw_name    = player.get("name", "")
        nationality = player.get("nationality", "")
        goals       = entry.get("goals", 0)
        assists     = entry.get("assists", 0)
        played      = entry.get("playedMatches", 0)
        penalties   = entry.get("penalties", 0)

        simple_pid  = slugify(raw_name)
        target_pid  = find_existing_player_id(pm, simple_pid, nationality) or simple_pid
        updated_pids.append(target_pid)

        # Position: try players_master first
        master_doc  = pm.find_one({"player_id": target_pid}, {"positions_list": 1, "position_2026": 1})
        position    = "Unknown"
        if master_doc:
            pos_list  = master_doc.get("positions_list") or []
            pos_2026  = master_doc.get("position_2026") or ""
            position  = pos_2026 or (pos_list[0] if pos_list else "Unknown")

        furthest_stage = stage_map.get(team.get("name", ""), "In progress")

        doc = {
            "player_id"        : target_pid,
            "player_name"      : raw_name,
            "nationality"      : nationality,
            "position"         : position,
            "tournament_year"  : TOURNAMENT_YEAR,
            "tournament_label" : f"FIFA World Cup {TOURNAMENT_YEAR}",
            "goals"            : goals,
            "assists"          : assists,
            "matches_played"   : played,
            "penalties"        : penalties,
            "furthest_stage"   : furthest_stage,
            "data_tier"        : "live_summary",
            "last_updated"     : datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        doc["embedding_text"] = build_live_embedding_text(doc)

        ops.append(UpdateOne(
            {"player_id": target_pid, "tournament_year": TOURNAMENT_YEAR},
            {"$set": doc},
            upsert=True,
        ))

    if ops:
        res = db["player_tournament_profiles"].bulk_write(ops, ordered=False)
        print(f"  [player_tournament_profiles] upserted={res.upserted_count} modified={res.modified_count}")

    return updated_pids


def _build_stage_map(db) -> dict[str, str]:
    """Build team_name → furthest_stage from matches collection (FINISHED matches)."""
    stage_order = [
        "Group Stage", "Round of 32", "Round of 16",
        "Quarter-finals", "Semi-finals", "3rd Place Final", "Final",
    ]
    stage_map: dict[str, str] = {}
    finished = list(db["matches"].find(
        {"tournament_year": TOURNAMENT_YEAR, "data_tier": "live_summary"},
        {"home_team": 1, "away_team": 1, "stage": 1, "_id": 0},
    ))
    for m in finished:
        raw_stage = m.get("stage", "GROUP_STAGE").replace("_", " ").title()
        # Normalize API stage names
        stage_map_api = {
            "Group Stage": "Group Stage", "Round Of 16": "Round of 16",
            "Quarter Final": "Quarter-finals", "Semi Final": "Semi-finals",
            "Third Place": "3rd Place Final", "Final": "Final",
        }
        stage = stage_map_api.get(raw_stage, raw_stage)
        for team in [m["home_team"], m["away_team"]]:
            current = stage_map.get(team)
            if current is None or stage_order.index(stage) > stage_order.index(current):
                stage_map[team] = stage
    return stage_map


def update_master_stats(updated_pids: list[str], db) -> None:
    """Re-aggregate career_wc_* in players_master for players with updated 2026 profiles."""
    if not updated_pids:
        return
    pm = db["players_master"]
    ops = []
    for pid in updated_pids:
        profiles = list(db["player_tournament_profiles"].find(
            {"player_id": pid},
            {"goals": 1, "matches_played": 1, "minutes_played": 1, "_id": 0},
        ))
        total_goals   = sum((p.get("goals") or 0) for p in profiles)
        total_matches = sum((p.get("matches_played") or 0) for p in profiles)
        total_minutes = sum((p.get("minutes_played") or 0) for p in profiles)
        ops.append(UpdateOne(
            {"player_id": pid},
            {"$set": {
                "career_wc_goals"  : total_goals,
                "career_wc_matches": total_matches,
                "career_wc_minutes": total_minutes,
                "last_updated"     : datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }},
        ))
    if ops:
        res = pm.bulk_write(ops, ordered=False)
        print(f"  [players_master] updated career stats for {res.modified_count} players")


# ---------------------------------------------------------------------------
# Re-embed updated 2026 profiles
# ---------------------------------------------------------------------------

def re_embed_profiles(updated_pids: list[str], db) -> None:
    """Regenerate embedding vectors for updated 2026 player profiles."""
    if not updated_pids:
        return

    # Resolve credentials
    creds_path = Path(GOOGLE_CREDS)
    if not creds_path.is_absolute():
        creds_path = ROOT / GOOGLE_CREDS.lstrip("./\\")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)

    try:
        import vertexai
        from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
    except ImportError:
        print("  [re-embed] skipped — google-cloud-aiplatform not installed")
        return

    vertexai.init(project=GCP_PROJECT, location=GCP_REGION)
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")

    profiles = list(db["player_tournament_profiles"].find(
        {"player_id": {"$in": updated_pids}, "tournament_year": TOURNAMENT_YEAR},
        {"_id": 1, "embedding_text": 1},
    ))
    if not profiles:
        return

    print(f"  Re-embedding {len(profiles)} updated 2026 profiles ...")
    ops = []
    for i in range(0, len(profiles), EMBED_BATCH_SIZE):
        batch = profiles[i : i + EMBED_BATCH_SIZE]
        inputs = [TextEmbeddingInput(p["embedding_text"], "RETRIEVAL_DOCUMENT") for p in batch]
        results = model.get_embeddings(inputs, output_dimensionality=EMBED_DIM)
        for p, r in zip(batch, results):
            ops.append(UpdateOne({"_id": p["_id"]}, {"$set": {"embedding": r.values}}))
    if ops:
        res = db["player_tournament_profiles"].bulk_write(ops, ordered=False)
        print(f"  [re-embed] {res.modified_count} profiles re-embedded")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not MONGO_URI:
        sys.exit("ERROR: MONGODB_CLUSTER_CONNECTION not set in .env")

    print("=" * 60)
    print(f"ScoutIQ Day 5 — Live 2026 Ingestion  ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print("=" * 60)

    db = MongoClient(MONGO_URI)["scoutiq"]

    # [1] Try StatsBomb first
    print("\n[1/4] Checking StatsBomb for 2026 WC data ...")
    season_id = check_statsbomb_2026()
    if season_id is not None:
        ingest_statsbomb_2026(season_id, db)
        print("\nStatsBomb ingestion complete. Skipping football-data.org fallback.")
        return

    print("  No StatsBomb 2026 data yet — using football-data.org fallback")

    # [2] football-data.org: matches
    print("\n[2/4] Ingesting match results ...")
    finished_matches = ingest_fdo_matches(db)
    if not finished_matches:
        print("  No finished matches yet — tournament hasn't started")

    # [3] football-data.org: scorers → player_tournament_profiles
    print("\n[3/4] Ingesting scorers (cumulative goals/assists) ...")
    updated_pids = ingest_fdo_scorers(db)
    if not updated_pids:
        print("  No scorers yet — no matches played")

    # [4] Re-aggregate players_master + re-embed
    print("\n[4/4] Updating players_master + re-embedding ...")
    if updated_pids:
        update_master_stats(updated_pids, db)
        re_embed_profiles(updated_pids, db)
    else:
        print("  Nothing to update")

    # Summary
    total_profiles = db["player_tournament_profiles"].count_documents(
        {"tournament_year": TOURNAMENT_YEAR}
    )
    total_matches  = db["matches"].count_documents({"tournament_year": TOURNAMENT_YEAR})
    print("\n" + "=" * 60)
    print(f"Live sync complete  ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print("=" * 60)
    print(f"  2026 player profiles: {total_profiles}")
    print(f"  2026 matches:         {total_matches}")
    print(f"  Next run: after next matchday — python ingestion/ingest_live.py")


if __name__ == "__main__":
    main()
