"""
position_resolver.py — Agent Tool
Resolves a player's position when the database value is "Unknown" or missing.

Used by the ScoutIQ agent at query time. The agent should call this when it
encounters a player with no position data.

Priority:
  1. football-data.org squad data (WC 2026 players)
  2. football-data.org /persons endpoint (by FDO player ID)
  3. Wikipedia REST API (any player)

Usage (from agent code):
    from agent.position_resolver import resolve_position
    position = resolve_position("Zinedine Zidane", "France")
"""
import os
import re
import time
import unicodedata
from functools import lru_cache
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

FDO_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")
FDO_BASE    = "https://api.football-data.org/v4"
FDO_HEADERS = {"X-Auth-Token": FDO_API_KEY}
WIKI_BASE   = "https://en.wikipedia.org/api/rest_v1/page/summary"

_FDO_SECTION_MAP = {
    "Goalkeeper": "Goalkeeper",
    "Defence":    "Defender",
    "Midfield":   "Midfielder",
    "Offence":    "Forward",
}

_POSITION_PATTERNS = [
    # 1. Direct keyword match — most reliable, try first
    r"\b(goalkeeper|winger|right winger|left winger|striker|centre.forward|"
     r"centre forward|attacking midfielder|central midfielder|"
     r"defensive midfielder|right midfielder|left midfielder|"
     r"centre.back|centre back|right.back|right back|left.back|left back|"
     r"second striker|forward|midfielder|defender|fullback|sweeper)\b",
    # 2. "played/plays as [position]" — handles "played as an attacking midfielder"
    r"play(?:s|ed)?\s+as\s+(?:a|an\s+)?([\w\s]+?)(?:\s+for|\s+and|\.|,|$)",
    # 3. "is/was a [position]" — only for short positional phrases (max 3 words)
    r"(?:is|was)\s+(?:a|an)\s+((?:\w+\s){0,2}(?:goalkeeper|winger|striker|"
     r"midfielder|defender|forward|back|sweeper))",
]

_POSITION_NORM = {
    "Centre Back":     "Centre-Back",
    "Center Back":     "Centre-Back",
    "Right Back":      "Right-Back",
    "Left Back":       "Left-Back",
    "Attacking Mid":   "Attacking Midfielder",
    "Defensive Mid":   "Defensive Midfielder",
    "Centreback":      "Centre-Back",
}


def _slugify(name: str) -> str:
    if not name:
        return ""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_str  = normalized.encode("ascii", "ignore").decode("ascii")
    slug       = re.sub(r"[^\w\s-]", "", ascii_str).strip().lower()
    return re.sub(r"[\s_]+", "-", slug)


def _name_sim(a: str, b: str) -> float:
    a_t = set(_slugify(a).split("-"))
    b_t = set(_slugify(b).split("-"))
    if not a_t or not b_t:
        return 0.0
    return len(a_t & b_t) / max(len(a_t), len(b_t))


@lru_cache(maxsize=1)
def _get_fdo_squad_lookup() -> dict[str, dict]:
    """Cached fetch of all WC 2026 squad data from football-data.org."""
    try:
        r = requests.get(
            f"{FDO_BASE}/competitions/WC/teams",
            headers=FDO_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
    except requests.RequestException:
        return {}

    lookup: dict[str, dict] = {}
    for team in r.json().get("teams", []):
        for player in team.get("squad", []):
            raw_name = player.get("name", "")
            slug     = _slugify(raw_name)
            lookup[slug] = {
                "fdo_id"  : player.get("id"),
                "name"    : raw_name,
                "position": player.get("position", "Unknown"),
            }
    return lookup


def _parse_wiki_position(text: str) -> str | None:
    for i, pattern in enumerate(_POSITION_PATTERNS):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            # Pattern 0: the whole match is the position keyword
            # Patterns 1/2: group(1) captures the position phrase
            raw = (m.group(1) if m.lastindex else m.group(0)).strip().title()
            # Reject captures that are too long (>4 words = not a position)
            if len(raw.split()) > 4:
                continue
            return _POSITION_NORM.get(raw, raw)
    return None


def _from_fdo_squad(player_name: str) -> str | None:
    """Check football-data.org squad data for the player's position."""
    squad = _get_fdo_squad_lookup()
    if not squad:
        return None

    # Exact slug match
    entry = squad.get(_slugify(player_name))
    if not entry:
        # Token-overlap fallback
        best_score, best_entry = 0.0, None
        for fdata in squad.values():
            score = _name_sim(player_name, fdata["name"])
            if score > best_score and score >= 0.6:
                best_score, best_entry = score, fdata
        entry = best_entry

    if entry and entry.get("position") not in (None, "Unknown"):
        return entry["position"]
    return None


def _from_fdo_persons(player_name: str) -> str | None:
    """Look up a player via football-data.org /persons/{id} (requires knowing FDO ID)."""
    squad = _get_fdo_squad_lookup()
    fdo_entry = squad.get(_slugify(player_name))
    if not fdo_entry:
        for fdata in squad.values():
            if _name_sim(player_name, fdata["name"]) >= 0.6:
                fdo_entry = fdata
                break

    if not fdo_entry or not fdo_entry.get("fdo_id"):
        return None

    try:
        r = requests.get(
            f"{FDO_BASE}/persons/{fdo_entry['fdo_id']}",
            headers=FDO_HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            return None
        person  = r.json()
        section = person.get("section", "")
        return _FDO_SECTION_MAP.get(section) or section or None
    except requests.RequestException:
        return None


def _from_wikipedia(player_name: str) -> str | None:
    """Fetch Wikipedia summary and parse position from text."""
    attempts = [player_name, player_name.split()[-1]]
    for query in attempts:
        wiki_title = query.replace(" ", "_")
        try:
            r = requests.get(
                f"{WIKI_BASE}/{wiki_title}",
                headers={"User-Agent": "ScoutIQ/1.0 (hackathon)"},
                timeout=10,
            )
            if r.status_code != 200:
                continue
            data    = r.json()
            full    = (data.get("description", "") + " " + data.get("extract", "")).lower()
            if not any(kw in full for kw in ("football", "soccer", "footballer")):
                continue
            position = _parse_wiki_position(full)
            if position:
                return position
        except requests.RequestException:
            pass
        time.sleep(0.3)
    return None


def resolve_position(
    player_name: str,
    nationality: str = "",
    use_wikipedia: bool = True,
) -> dict:
    """
    Resolve a player's position using external sources.

    Returns:
        {
            "position": str | None,   # resolved position or None if not found
            "source":   str,          # "fdo_squad" | "fdo_persons" | "wikipedia" | "not_found"
            "confidence": "high" | "medium" | "low",
        }
    """
    # 1. FDO squad (high confidence — official squad data)
    pos = _from_fdo_squad(player_name)
    if pos:
        return {"position": pos, "source": "fdo_squad", "confidence": "high"}

    # 2. FDO /persons endpoint (medium confidence — coarse position category)
    pos = _from_fdo_persons(player_name)
    if pos:
        return {"position": pos, "source": "fdo_persons", "confidence": "medium"}

    # 3. Wikipedia (low-medium confidence — parsed from free text)
    if use_wikipedia:
        pos = _from_wikipedia(player_name)
        if pos:
            return {"position": pos, "source": "wikipedia", "confidence": "medium"}

    return {"position": None, "source": "not_found", "confidence": "low"}


def resolve_and_persist(player_name: str, player_id: str, db) -> str | None:
    """
    Resolve position and immediately write it back to players_master.
    Use this from the agent when you want to cache the result.

    Returns the resolved position string, or None.
    """
    result = resolve_position(player_name)
    position = result["position"]
    if position:
        db["players_master"].update_one(
            {"player_id": player_id},
            {"$addToSet": {"positions_list": position}},
        )
    return position
