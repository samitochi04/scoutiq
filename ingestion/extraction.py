"""
Fetches StatsBomb event + lineup data for all WC 2018 + 2022 matches.
Computes per-player stats including correct minutes_played and position.

Output: players_raw.json
"""
from statsbombpy import sb # type: ignore
import pandas as pd # type: ignore
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _extract_position(pos_data) -> str:
    """Extract primary position name from StatsBomb lineup positions field.

    Returns 'Substitute' for players who were listed in the squad but never
    entered the pitch (their positions list is empty in StatsBomb lineup data).
    """
    if isinstance(pos_data, list):
        if not pos_data:          # empty list = unused substitute, never entered
            return "Substitute"
        first = pos_data[0]
        if isinstance(first, dict):
            return first.get("position", "Unknown")
        return str(first)
    if isinstance(pos_data, str) and pos_data:
        return pos_data
    return "Unknown"


def _is_starter(pos_data) -> bool:
    """Return True if the player started (not a substitute).

    An empty positions list means the player was an unused substitute.
    """
    if isinstance(pos_data, list):
        if not pos_data:          # unused substitute — never on the pitch
            return False
        first = pos_data[0]
        if isinstance(first, dict):
            return first.get("start_reason", "Starting XI") != "Substitution"
    return True


def _extract_replacement_name(val) -> str | None:
    """Extract player name from substitution_replacement (dict or string)."""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, dict):
        return val.get("name")
    if isinstance(val, str) and val:
        return val
    return None


def _compute_minutes(events: pd.DataFrame, lineups: dict) -> dict:
    """Compute minutes played per player. Returns {player_name: int}."""
    max_minute = int(events["minute"].max()) if not events.empty else 90
    subs = events[events["type"] == "Substitution"]
    sub_off_min: dict[str, int] = {}
    sub_on_min: dict[str, int] = {}
    for _, row in subs.iterrows():
        off = row.get("player")
        on = _extract_replacement_name(row.get("substitution_replacement"))
        minute = int(row["minute"])
        if isinstance(off, str) and off:
            sub_off_min[off] = minute
        if on:
            sub_on_min[on] = minute
    minutes: dict[str, int] = {}
    for team_name, lineup_df in lineups.items():
        for _, p in lineup_df.iterrows():
            name = p["player_name"]
            starter = _is_starter(p.get("positions"))  # StatsBomb column is 'positions' (plural)
            if name in sub_on_min:
                on_min = sub_on_min[name]
                off_min = sub_off_min.get(name)
                minutes[name] = (off_min - on_min) if off_min is not None else max(0, max_minute - on_min)
            elif starter:
                off_min = sub_off_min.get(name)
                minutes[name] = off_min if off_min is not None else max_minute
            else:
                minutes[name] = 0
    return minutes


def get_player_stats(match_id: int) -> list[dict]:
    """Extract per-player stats for a single match."""
    events = sb.events(match_id=match_id)
    lineups = sb.lineups(match_id=match_id)

    position_map: dict[str, str] = {}
    for _team, lineup_df in lineups.items():
        for _, p in lineup_df.iterrows():
            position_map[p["player_name"]] = _extract_position(p.get("positions"))

    minutes_map = _compute_minutes(events, lineups)
    player_events = events.dropna(subset=["player"])

    stats: dict[str, dict] = {}
    for _, row in player_events.iterrows():
        player = row["player"]
        team = row["team"]
        if player not in stats:
            stats[player] = {
                "player_name": player,
                "team": team,
                "match_id": match_id,
                "position": position_map.get(player, "Unknown"),
                "goals": 0,
                "shots": 0,
                "shots_on_target": 0,
                "passes": 0,
                "passes_completed": 0,
                "dribbles": 0,
                "dribbles_completed": 0,
                "pressures": 0,
                "tackles": 0,
                "minutes_played": minutes_map.get(player, 0),
            }
        t = row["type"]
        if t == "Shot":
            stats[player]["shots"] += 1
            outcome = row.get("shot_outcome")
            if isinstance(outcome, dict):
                outcome = outcome.get("name", "")
            if outcome == "Goal":
                stats[player]["goals"] += 1
            if outcome in ("Goal", "Saved"):
                stats[player]["shots_on_target"] += 1
        elif t == "Pass":
            stats[player]["passes"] += 1
            pass_outcome = row.get("pass_outcome")
            if isinstance(pass_outcome, dict):
                pass_outcome = pass_outcome.get("name", "")
            if pass_outcome is None or (isinstance(pass_outcome, float) and pd.isna(pass_outcome)):
                stats[player]["passes_completed"] += 1
        elif t == "Dribble":
            stats[player]["dribbles"] += 1
            outcome = row.get("dribble_outcome")
            if isinstance(outcome, dict):
                outcome = outcome.get("name", "")
            if outcome == "Complete":
                stats[player]["dribbles_completed"] += 1
        elif t == "Pressure":
            stats[player]["pressures"] += 1
        elif t == "Tackle":
            stats[player]["tackles"] += 1

    for p in stats.values():
        p["pass_completion_pct"] = (
            round(p["passes_completed"] / p["passes"] * 100, 1) if p["passes"] > 0 else 0.0
        )
    return list(stats.values())


def build_dataset() -> list[dict]:
    """Process all WC 2018 + 2022 matches."""
    all_players: list[dict] = []
    matches_2018 = sb.matches(competition_id=43, season_id=3)
    matches_2022 = sb.matches(competition_id=43, season_id=106)
    all_matches = pd.concat([matches_2018, matches_2022], ignore_index=True)
    total = len(all_matches)
    for i, (_, match) in enumerate(all_matches.iterrows(), 1):
        mid = int(match["match_id"])
        season = str(match["season"])
        stage = match["competition_stage"]
        if isinstance(stage, dict):
            stage = stage.get("name", str(stage))
        home_team = match["home_team"]
        if isinstance(home_team, dict):
            home_team = home_team.get("home_team_name", str(home_team))
        away_team = match["away_team"]
        if isinstance(away_team, dict):
            away_team = away_team.get("away_team_name", str(away_team))
        print(f"[{i}/{total}] Match {mid}: {home_team} vs {away_team} ({stage}) ...")
        try:
            player_stats = get_player_stats(mid)
            for p in player_stats:
                p["season"] = season
                p["competition_stage"] = stage
                p["home_team"] = home_team
                p["away_team"] = away_team
                p["match_date"] = str(match["match_date"])
            all_players.extend(player_stats)
        except Exception as e:
            print(f"  Skipped match {mid}: {e}")
    return all_players


if __name__ == "__main__":
    players = build_dataset()
    print(f"\nTotal player-match records: {len(players)}")
    out = ROOT / "players_raw.json"
    with open(out, "w") as f:
        json.dump(players, f, indent=2)
    print(f"Saved to {out}")