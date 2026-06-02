"""
enrich_positions.py — Day 5
Enriches player documents that have position = "Unknown" or no position.

Two strategies:
  1. football-data.org WC squad data     — covers all 48 x 26 = 1,248 active 2026 players
  2. Wikipedia REST API summary parsing  — fallback for historical players (Zidane, etc.)

Run once, then re-run whenever new squad data is available:
    python ingestion/enrich_positions.py
"""
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

MONGO_URI   = os.getenv("MONGODB_CLUSTER_CONNECTION")
FDO_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")
FDO_BASE    = "https://api.football-data.org/v4"
FDO_HEADERS = {"X-Auth-Token": FDO_API_KEY}
WIKI_BASE   = "https://en.wikipedia.org/api/rest_v1/page/summary"

# Position keywords to scan for in Wikipedia summaries (order matters — more specific first)
_WIKI_POSITION_PATTERNS: list[tuple[str, str]] = [
    (r"plays?\s+as\s+(?:a|an)?\s*([\w\s]+?)(?:\s+for|\s+and|\.|,)",              "extract"),
    (r"(?:is|was)\s+(?:a|an)\s+([\w\s]*?(?:goalkeeper|winger|striker|midfielder|"
     r"defender|forward|back|centre.back|full.back|sweeper)[\w\s]*?)(?:\.|,|\s+who)",
     "extract"),
    (r"(goalkeeper|winger|striker|attacking midfielder|central midfielder|"
     r"defensive midfielder|centre.back|right.back|left.back|centre.forward|"
     r"second striker|forward|midfielder|defender|fullback|sweeper)",              "extract"),
]

# Coarse FDO section → readable position
_FDO_SECTION_MAP = {
    "Goalkeeper": "Goalkeeper",
    "Defence":    "Defender",
    "Midfield":   "Midfielder",
    "Offence":    "Forward",
    "Offence":    "Forward",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    if not name:
        return ""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_str  = normalized.encode("ascii", "ignore").decode("ascii")
    slug       = re.sub(r"[^\w\s-]", "", ascii_str).strip().lower()
    return re.sub(r"[\s_]+", "-", slug)


def _name_similarity(a: str, b: str) -> float:
    """Rough token-overlap similarity for name matching."""
    a_tokens = set(slugify(a).split("-"))
    b_tokens = set(slugify(b).split("-"))
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))


# ---------------------------------------------------------------------------
# Strategy 1 — football-data.org squad enrichment (2026 active players)
# ---------------------------------------------------------------------------

def fetch_fdo_squads() -> dict[str, dict]:
    """
    Returns {slugified_name: {position, nationality, dob, fdo_id}} for all
    players in the 48 WC 2026 squad lists.
    """
    print("  Fetching squad data from football-data.org ...")
    try:
        r = requests.get(
            f"{FDO_BASE}/competitions/WC/teams",
            headers=FDO_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: Could not fetch FDO squads: {e}")
        return {}

    teams = r.json().get("teams", [])
    lookup: dict[str, dict] = {}

    for team in teams:
        nationality = team.get("name", "")
        for player in team.get("squad", []):
            raw_name = player.get("name", "")
            position = player.get("position", "Unknown")
            slug     = slugify(raw_name)
            lookup[slug] = {
                "fdo_id"     : player.get("id"),
                "name"       : raw_name,
                "position"   : position,
                "nationality": player.get("nationality") or nationality,
                "dob"        : player.get("dateOfBirth"),
            }

    print(f"  Loaded {len(lookup)} players from FDO squads ({len(teams)} teams)")
    return lookup


def enrich_from_fdo(pm, fdo_lookup: dict[str, dict]) -> int:
    """
    Update players_master documents for active 2026 players who lack a clean position.
    Uses token-overlap matching to handle name mismatches.
    Returns count of documents updated.
    """
    candidates = list(pm.find(
        {"active_at_2026_wc": True},
        {"player_id": 1, "player_name": 1, "nationality": 1, "positions_list": 1,
         "position_2026": 1, "_id": 0},
    ))

    ops    = []
    mapped = 0

    for doc in candidates:
        pid      = doc["player_id"]
        existing = (doc.get("positions_list") or []) + [doc.get("position_2026") or ""]
        existing = [p for p in existing if p and p.lower() != "unknown"]

        if existing:
            continue  # already has a real position

        # Try exact slug match
        fdo_entry = fdo_lookup.get(pid)

        # Try token-overlap if exact failed
        if not fdo_entry:
            best_score  = 0.0
            best_entry  = None
            player_name = doc.get("player_name") or pid
            for fslug, fdata in fdo_lookup.items():
                score = _name_similarity(player_name, fdata["name"])
                if score > best_score and score >= 0.6:
                    best_score = score
                    best_entry = fdata
            fdo_entry = best_entry

        if not fdo_entry:
            continue

        position = fdo_entry["position"]
        if not position or position == "Unknown":
            continue

        ops.append(UpdateOne(
            {"player_id": pid},
            {"$set": {
                "position_2026": position,
                "positions_list": [position],
            }},
        ))
        mapped += 1

    if ops:
        pm.bulk_write(ops, ordered=False)

    return mapped


# ---------------------------------------------------------------------------
# Strategy 2 — Wikipedia REST API (historical players)
# ---------------------------------------------------------------------------

def _parse_wikipedia_position(summary_text: str) -> str | None:
    """Extract football position from a Wikipedia page summary."""
    text = summary_text.lower()
    for pattern, _ in _WIKI_POSITION_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().title()
            # Normalise common variants
            norm = {
                "Centre Back": "Centre-Back",
                "Center Back": "Centre-Back",
                "Right Back":  "Right-Back",
                "Left Back":   "Left-Back",
                "Centreback":  "Centre-Back",
                "Attacking Mid": "Attacking Midfielder",
                "Defensive Mid": "Defensive Midfielder",
            }
            return norm.get(raw, raw)
    return None


def fetch_wikipedia_position(player_name: str, delay: float = 0.5) -> str | None:
    """
    Look up a player's position via the Wikipedia REST summary API.
    Returns a position string or None. Respects a courtesy delay between calls.
    """
    time.sleep(delay)

    # Try full name first, then simplified slug
    attempts = [player_name, player_name.split()[-1]]
    for query in attempts:
        wiki_title = query.replace(" ", "_")
        try:
            r = requests.get(
                f"{WIKI_BASE}/{wiki_title}",
                headers={"User-Agent": "ScoutIQ/1.0 (hackathon project)"},
                timeout=10,
            )
            if r.status_code != 200:
                continue
            data = r.json()
            if data.get("type") not in ("standard", None):
                continue
            desc = data.get("description", "")
            # Quick sanity check — must be a footballer page
            if not any(kw in desc.lower() for kw in ("football", "soccer", "footballer")):
                extract = data.get("extract", "")
                if not any(kw in extract.lower() for kw in ("football", "soccer")):
                    continue
            position = _parse_wikipedia_position(
                data.get("description", "") + " " + data.get("extract", "")
            )
            if position:
                return position
        except requests.RequestException:
            continue

    return None


def enrich_from_wikipedia(pm, limit: int = 200) -> int:
    """
    For historical players with Unknown/missing positions, attempt Wikipedia enrichment.
    Caps at `limit` calls to avoid rate-limiting. Returns count updated.
    """
    # Players without any real position data
    pipeline = [
        {"$match": {
            "active_at_2026_wc": {"$ne": True},
            "$or": [
                {"positions_list": {"$in": [None, [], ["Unknown"]]}},
                {"positions_list": {"$exists": False}},
            ],
        }},
        {"$project": {"player_id": 1, "player_name": 1, "nationality": 1, "_id": 0}},
        {"$limit": limit},
    ]
    candidates = list(pm.aggregate(pipeline))
    print(f"  {len(candidates)} historical players queued for Wikipedia enrichment ...")

    ops     = []
    updated = 0

    for doc in candidates:
        name     = doc.get("player_name") or doc["player_id"].replace("-", " ").title()
        position = fetch_wikipedia_position(name)
        if position:
            ops.append(UpdateOne(
                {"player_id": doc["player_id"]},
                {"$set": {"positions_list": [position]}},
            ))
            updated += 1

    if ops:
        pm.bulk_write(ops, ordered=False)

    return updated


# ---------------------------------------------------------------------------
# Strategy 3 — football-data.org /persons endpoint (by FDO ID)
# ---------------------------------------------------------------------------

def enrich_from_fdo_persons(pm, fdo_lookup: dict[str, dict]) -> int:
    """
    For 2026 players still missing positions after squad match,
    try fetching the individual /persons/{id} endpoint.
    """
    # Find 2026 players still missing positions
    candidates = list(pm.find(
        {
            "active_at_2026_wc": True,
            "positions_list": {"$in": [None, [], ["Unknown"]]},
        },
        {"player_id": 1, "player_name": 1, "_id": 0},
    ))

    if not candidates:
        return 0

    print(f"  {len(candidates)} active 2026 players still missing position — trying /persons ...")
    ops = []

    for doc in candidates:
        pid  = doc["player_id"]
        name = doc.get("player_name") or pid

        # Find FDO ID from our squad lookup
        fdo_entry = fdo_lookup.get(pid)
        if not fdo_entry:
            for fslug, fdata in fdo_lookup.items():
                if _name_similarity(name, fdata["name"]) >= 0.6:
                    fdo_entry = fdata
                    break

        if not fdo_entry or not fdo_entry.get("fdo_id"):
            continue

        try:
            r = requests.get(
                f"{FDO_BASE}/persons/{fdo_entry['fdo_id']}",
                headers=FDO_HEADERS,
                timeout=10,
            )
            if r.status_code != 200:
                continue
            person = r.json()
            section  = person.get("section", "")
            position = _FDO_SECTION_MAP.get(section, section)
            if position and position != "Unknown":
                ops.append(UpdateOne(
                    {"player_id": pid},
                    {"$set": {"positions_list": [position]}},
                ))
            time.sleep(0.2)  # respect rate limit
        except requests.RequestException:
            continue

    if ops:
        pm.bulk_write(ops, ordered=False)

    return len(ops)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not MONGO_URI:
        sys.exit("ERROR: MONGODB_CLUSTER_CONNECTION not set in .env")

    print("=" * 60)
    print("ScoutIQ — Position Enrichment")
    print("=" * 60)

    db = MongoClient(MONGO_URI)["scoutiq"]
    pm = db["players_master"]

    before = pm.count_documents({
        "$or": [
            {"positions_list": {"$in": [None, [], ["Unknown"]]}},
            {"positions_list": {"$exists": False}},
        ]
    })
    print(f"\nPlayers with unknown/missing position: {before}")

    # --- Strategy 1: FDO squad data (2026 active players) ---
    print("\n[1/3] football-data.org squad enrichment ...")
    fdo_lookup = fetch_fdo_squads()
    n1 = enrich_from_fdo(pm, fdo_lookup) if fdo_lookup else 0
    print(f"  Updated {n1} players from squad data")

    # --- Strategy 2: FDO /persons endpoint (remaining 2026 players) ---
    print("\n[2/3] football-data.org /persons enrichment ...")
    n2 = enrich_from_fdo_persons(pm, fdo_lookup) if fdo_lookup else 0
    print(f"  Updated {n2} players from /persons endpoint")

    # --- Strategy 3: Wikipedia (historical unknowns) ---
    print("\n[3/3] Wikipedia enrichment (historical players, up to 200) ...")
    n3 = enrich_from_wikipedia(pm, limit=200)
    print(f"  Updated {n3} players from Wikipedia")

    after = pm.count_documents({
        "$or": [
            {"positions_list": {"$in": [None, [], ["Unknown"]]}},
            {"positions_list": {"$exists": False}},
        ]
    })

    print("\n" + "=" * 60)
    print("Position enrichment complete")
    print("=" * 60)
    print(f"  Before:  {before} unknown positions")
    print(f"  Updated: {n1 + n2 + n3} players")
    print(f"  After:   {after} unknown positions remaining")
    print(f"  Note: Remaining unknowns are Kaggle-only players without Wikipedia pages")


if __name__ == "__main__":
    main()
