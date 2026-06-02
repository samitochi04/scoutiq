"""
Ingests Kaggle FIFA World Cup data (1998–2014) into MongoDB.
Adds summary-tier tournament profiles for retired players (Iniesta, Zidane, etc.)
so vector similarity search works across generations.

Data files required (download from Kaggle and place in data/kaggle/):
  https://www.kaggle.com/datasets/abecklas/fifa-world-cup
  → data/kaggle/WorldCupPlayers.csv
  → data/kaggle/WorldCups.csv

"""
import json 
import os 
import re
import sys
import math
from pathlib import Path
import pandas as pd # type: ignore
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING
from unidecode import unidecode

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
MONGO_URI = os.getenv("MONGODB_CLUSTER_CONNECTION")
if not MONGO_URI:
    sys.exit("ERROR: MONGODB_CLUSTER_CONNECTION not set in .env")

KAGGLE_DIR = ROOT / "data" / "kaggle"
PLAYERS_CSV = KAGGLE_DIR / "WorldCupPlayers.csv"
MATCHES_CSV = KAGGLE_DIR / "WorldCupMatches.csv"
CUPS_CSV = KAGGLE_DIR / "WorldCups.csv"

# Only ingest these WC years (2018 + 2022 are already in full tier from StatsBomb)
HISTORICAL_YEARS = {1998, 2002, 2006, 2010, 2014}

# ---------------------------------------------------------------------------
# Manually curated style descriptors for historically significant players.
# Used to enrich embedding text for summary-tier records where event data is
# unavailable. Each entry is 1–2 sentences describing playing style.
# ---------------------------------------------------------------------------
KNOWN_STYLES: dict[str, str] = {
    # Spain
    "andres-iniesta": (
        "Deep-lying creative midfielder known for exceptional vision, calmness under pressure, "
        "and incisive through-balls. The engine of Spain's tiki-taka system."
    ),
    "xavi-hernandez": (
        "High-volume passer with elite positional awareness. Dictated tempo for Spain and "
        "Barcelona with short, precise combinations and relentless pressing."
    ),
    "david-villa": (
        "Clinical finisher who combined intelligent movement with powerful shooting from both "
        "feet. Spain's all-time leading scorer and a consistent World Cup performer."
    ),
    "fernando-torres": (
        "Explosive centre-forward with sharp acceleration and composed finishing. Devastatingly "
        "effective when in peak form, especially in large spaces behind high defensive lines."
    ),
    "sergio-ramos": (
        "Commanding centre-back and set-piece goal threat. Known for aggressive defending, "
        "leadership, and crucial goals at critical moments."
    ),
    # France
    "zinedine-zidane": (
        "One of the greatest midfielders of all time. Graceful, technically supreme, capable "
        "of operating as a deep playmaker or advanced creator. Exceptional in big-game moments."
    ),
    "thierry-henry": (
        "Lethal striker and one-time winger who combined pace, technique, and composure in "
        "front of goal. Dangerous from the left channel and as a centre-forward."
    ),
    "patrick-vieira": (
        "Box-to-box midfielder of immense physicality and technical quality. Dominated "
        "midfield battles with powerful carrying, tackling, and long-range passing."
    ),
    "lilian-thuram": (
        "Highly intelligent right-back and central defender, known for tactical discipline, "
        "strong aerial ability, and memorable attacking contributions in key moments."
    ),
    "kylian-mbappe": (
        "Generational forward with extraordinary pace, dribbling ability, and an eye for "
        "goal. Equally dangerous cutting in from the left or driving at defenders centrally."
    ),
    "antoine-griezmann": (
        "Technically refined forward who combines creative link-up play with clinical finishing. "
        "Excellent off the ball, pressing, and from set pieces."
    ),
    # Brazil
    "ronaldinho": (
        "Instinctive, joyful attacking midfielder who combined exceptional dribbling with "
        "creativity, flair, and an eye for spectacular goals and assists."
    ),
    "ronaldo-nazario": (
        "Arguably the greatest centre-forward ever — explosive pace, devastating finishing, "
        "and an ability to perform in the biggest matches."
    ),
    "rivaldo": (
        "Left-footed attacking midfielder with powerful shooting, exceptional dribbling, "
        "and the ability to unlock defences with vision and technical brilliance."
    ),
    "cafu": (
        "High-energy right-back known for relentless overlapping runs, attacking output, "
        "and defensive tenacity. The benchmark for the modern attacking full-back."
    ),
    "roberto-carlos": (
        "Explosive left-back with ferocious shot and extraordinary pace. Attacking threat "
        "down the left flank with both delivery and set-piece power."
    ),
    "kaka": (
        "Elegant, direct attacking midfielder with pace and vision. Effective through balls, "
        "long-range shooting, and intelligent movement between the lines."
    ),
    # Argentina
    "lionel-messi": (
        "Greatest player of all time. Exceptional dribbling, vision, passing, and finishing "
        "from anywhere on the pitch. Operates as a false nine or right forward."
    ),
    "gabriel-batistuta": (
        "Powerful, classical centre-forward famous for his ferocious shot and aerial threat. "
        "One of the most prolific World Cup strikers in history."
    ),
    "juan-roman-riquelme": (
        "Classic number 10 and deep playmaker. Unhurried, masterful with the ball, able to "
        "dictate the tempo and create chances with line-breaking passes."
    ),
    "jorge-valdano": (
        "Intelligent forward who combined technical quality with football intelligence. "
        "Memorable for his role alongside Maradona in the 1986 triumph."
    ),
    # Germany / West Germany
    "miroslav-klose": (
        "Record World Cup scorer (16 goals). Selfless, hardworking centre-forward with "
        "intelligent movement and clinical finishing, especially with headers."
    ),
    "michael-ballack": (
        "Complete box-to-box midfielder with powerful shooting, strong aerial presence, "
        "and the ability to arrive late into dangerous positions."
    ),
    "lothar-matthaus": (
        "Versatile midfielder and later sweeper-libero. Arguably Germany's greatest player — "
        "excellent technically, tactically aware, and a natural leader."
    ),
    "oliver-kahn": (
        "Commanding, aggressive goalkeeper with excellent reflexes and shot-stopping ability. "
        "Known for key saves in pressure moments and tournament-level performance."
    ),
    "philipp-lahm": (
        "Highly intelligent full-back capable of playing on either flank or in midfield. "
        "Excellent reading of the game, passing, and positional awareness."
    ),
    "thomas-muller": (
        "Space-interpreter and high-press specialist. Excellent movement between lines, "
        "intelligent runs, and a knack for decisive goals in major tournaments."
    ),
    # Portugal
    "cristiano-ronaldo": (
        "All-time top scorer in men's football. Devastating from the left, as a striker, "
        "or from set pieces. Exceptional pace, heading, and clinical finishing."
    ),
    "luis-figo": (
        "Technically brilliant right-winger with pace, dribbling, and precise crossing. "
        "Capable of taking on defenders and creating chances from wide areas."
    ),
    # Netherlands
    "ruud-van-nistelrooy": (
        "Pure penalty-area striker known for excellent movement, clinical finishing, "
        "and penalty-box intelligence."
    ),
    "arjen-robben": (
        "Wide forward famous for cutting inside from the right onto his left foot and "
        "delivering powerful, curling finishes. Quick and direct."
    ),
    "frank-de-boer": (
        "Elegant central defender with excellent passing ability from the back, positional "
        "discipline, and a key figure in Dutch defensive structure."
    ),
    "wesley-sneijder": (
        "Compact creative midfielder with exceptional passing range, vision, and the ability "
        "to deliver decisive balls and long-range goals in key moments."
    ),
    "virgil-van-dijk": (
        "Dominant centre-back combining aerial strength, composure on the ball, and the "
        "ability to play out from the back. A calming influence on any defence."
    ),
    # England
    "david-beckham": (
        "Right midfielder and specialist set-piece deliverer. Exceptional crossing, "
        "long-range shooting, and an ability to create from wide and deep positions."
    ),
    "steven-gerrard": (
        "Dynamic box-to-box midfielder combining powerful driving runs, long-range shooting, "
        "strong tackling, and inspirational leadership."
    ),
    "wayne-rooney": (
        "Energetic all-round forward capable of playing as a striker, shadow striker, or "
        "wide forward. Powerful shot, good in the air, and a creative link player."
    ),
    "harry-kane": (
        "Elite penalty-area striker with exceptional hold-up play, link-up ability, and "
        "clinical finishing. Also dangerous from deep positions and set pieces."
    ),
    # Italy
    "roberto-baggio": (
        "The Divine Ponytail — technically supreme attacking midfielder and striker. "
        "Brilliant dribbler and finisher with a flair for the spectacular."
    ),
    "gianluigi-buffon": (
        "World-class goalkeeper combining reflexes, positioning, and commanding presence. "
        "One of the safest pairs of hands in World Cup history."
    ),
    "andrea-pirlo": (
        "Deep-lying playmaker with extraordinary vision and passing range. Dictated tempo "
        "from deep with effortless ball control and a precise long pass."
    ),
    "francesco-totti": (
        "Technically gifted Roma icon who combined strength, dribbling, and creativity "
        "as a classic trequartista and later deep-lying forward."
    ),
    # Croatia
    "luka-modric": (
        "Elite all-round midfielder combining elite passing range, creative dribbling, "
        "energy, and defensive work. The complete modern midfielder."
    ),
    "davor-suker": (
        "Predatory striker and specialist finisher, top scorer at the 1998 World Cup. "
        "Clinical with either foot and dangerous in one-on-one situations."
    ),
    # Uruguay
    "diego-forlan": (
        "Tenacious and technically gifted striker known for spectacular long-range goals "
        "and a tireless, pressing-based work rate."
    ),
    "luis-suarez": (
        "Relentless, intelligent forward combining exceptional movement, pressing, link-up "
        "play, and clinical finishing from all positions."
    ),
    # Other notable players
    "samuel-etoo": (
        "Explosive striker with pace, power, and clinical finishing. One of Africa's "
        "greatest players and a consistent performer at club and international level."
    ),
    "didier-drogba": (
        "Physical, powerful centre-forward with exceptional strength, aerial ability, "
        "and big-game temperament. Dangerous from set pieces and in transition."
    ),
    "george-weah": (
        "Physically imposing, technically brilliant striker. First African player to win "
        "the Ballon d'Or, known for pace, power, and a powerful shot."
    ),
    "hidetoshi-nakata": (
        "Technically refined Japanese midfielder with excellent passing, vision, and "
        "the ability to operate effectively in European football systems."
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    name = unidecode(name)
    name = re.sub(r"[^a-z0-9\s-]", "", name.lower())
    return re.sub(r"\s+", "-", name.strip())


def clean_nans(records: list[dict]) -> list[dict]:
    for doc in records:
        for k, v in doc.items():
            if isinstance(v, float) and math.isnan(v):
                doc[k] = None
    return records


def bulk_upsert(collection, docs, key_fields, label):
    if not docs:
        print(f"  [SKIP] {label}: no documents")
        return
    ops = [
        UpdateOne({k: doc[k] for k in key_fields}, {"$set": doc}, upsert=True)
        for doc in docs
    ]
    result = collection.bulk_write(ops, ordered=False)
    print(
        f"  [{label}] total={len(ops)}"
        f" upserted={result.upserted_count}"
        f" modified={result.modified_count}"
    )


# ---------------------------------------------------------------------------
# Kaggle data normalisation
# ---------------------------------------------------------------------------

# StatsBomb uses full team names; Kaggle uses older/shorter names.
# Map Kaggle RoundID-era team names → consistent nationality strings.
TEAM_NAME_MAP: dict[str, str] = {
    # 3-letter FIFA codes → full English country names
    # (must match the names used in WorldCups.csv for furthest_stage lookups)
    "ALG": "Algeria",
    "ANG": "Angola",
    "ARG": "Argentina",
    "AUS": "Australia",
    "AUT": "Austria",
    "BEL": "Belgium",
    "BIH": "Bosnia and Herzegovina",
    "BRA": "Brazil",
    "BUL": "Bulgaria",
    "CHI": "Chile",
    "CHN": "China PR",
    "CIV": "Ivory Coast",
    "CMR": "Cameroon",
    "COL": "Colombia",
    "CRC": "Costa Rica",
    "CRO": "Croatia",
    "CZE": "Czech Republic",
    "DEN": "Denmark",
    "ECU": "Ecuador",
    "ENG": "England",
    "ESP": "Spain",
    "FRA": "France",
    "GER": "Germany",
    "GHA": "Ghana",
    "GRE": "Greece",
    "HON": "Honduras",
    "IRL": "Republic of Ireland",
    "IRN": "Iran",
    "ITA": "Italy",
    "JAM": "Jamaica",
    "JPN": "Japan",
    "KOR": "South Korea",
    "KSA": "Saudi Arabia",
    "MAR": "Morocco",
    "MEX": "Mexico",
    "NED": "Netherlands",
    "NGA": "Nigeria",
    "NOR": "Norway",
    "NZL": "New Zealand",
    "PAR": "Paraguay",
    "POL": "Poland",
    "POR": "Portugal",
    "PRK": "North Korea",
    "ROU": "Romania",
    "RSA": "South Africa",
    "RUS": "Russia",
    "SCG": "Serbia and Montenegro",
    "SCO": "Scotland",
    "SEN": "Senegal",
    "SRB": "Serbia",
    "SUI": "Switzerland",
    "SVK": "Slovakia",
    "SVN": "Slovenia",
    "SWE": "Sweden",
    "TOG": "Togo",
    "TRI": "Trinidad and Tobago",
    "TUN": "Tunisia",
    "TUR": "Turkey",
    "UKR": "Ukraine",
    "URU": "Uruguay",
    "USA": "United States",
    "YUG": "Yugoslavia",
    # Long-form names from WorldCups.csv that need normalisation
    "Korea Republic": "South Korea",
    "Korea DPR": "North Korea",
    "IR Iran": "Iran",
    "Côte d'Ivoire": "Ivory Coast",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
    "Trinidad and Tobago": "Trinidad and Tobago",
    "Czech Republic": "Czech Republic",
    "Germany FR": "Germany",  # pre-1990 West Germany label in WorldCups.csv
}

# Kaggle RoleName → normalised position
ROLE_MAP = {
    "Goalkeeper": "Goalkeeper",
    "GK": "Goalkeeper",
    "Defender": "Defender",
    "DF": "Defender",
    "Midfielder": "Midfielder",
    "MF": "Midfielder",
    "Forward": "Forward",
    "FW": "Forward",
    "Attacker": "Forward",
    # 'C' means captain armband, NOT a position — treat as outfield unknown
    "C": "Unknown",
}


def normalise_position(role: str) -> str:
    if pd.isna(role) or not role:
        return "Unknown"
    return ROLE_MAP.get(str(role).strip(), str(role).strip())


def normalise_team(team: str) -> str:
    if pd.isna(team) or not team:
        return "Unknown"
    return TEAM_NAME_MAP.get(str(team).strip(), str(team).strip())


def build_summary_embedding_text(row: dict) -> str:
    """Rich embedding text for summary-tier (Kaggle/historical) player records."""
    text = (
        f"{row['player_name']}, {row['position']}, {row['nationality']}, "
        f"FIFA World Cup {row['tournament_year']}. "
        f"{row['matches_played']} matches played"
    )
    if row.get("minutes_played"):
        text += f", {row['minutes_played']} minutes"
    text += f". {row['goals']} goals"
    if row.get("assists") is not None:
        text += f", {row['assists']} assists"
    text += f". Team reached {row['furthest_stage']}."
    # Append curated style descriptor if available for this player
    style = KNOWN_STYLES.get(row["player_id"])
    if style:
        text += f" {style}"
    return text


# ---------------------------------------------------------------------------
# Load and process Kaggle data
# ---------------------------------------------------------------------------

def load_kaggle_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load WorldCupPlayers.csv, WorldCupMatches.csv and WorldCups.csv from data/kaggle/."""
    missing = [p for p in (PLAYERS_CSV, MATCHES_CSV, CUPS_CSV) if not p.exists()]
    if missing:
        print("\nERROR: Kaggle CSV files not found:")
        for p in missing:
            print(f"  Missing: {p.name}")
        print("\nThe Kaggle zip contains 3 files — you need all of them:")
        print("  WorldCupPlayers.csv, WorldCupMatches.csv, WorldCups.csv")
        print("Download from: https://www.kaggle.com/datasets/abecklas/fifa-world-cup")
        print("Place all 3 CSVs in: data/kaggle/")
        sys.exit(1)

    players = pd.read_csv(PLAYERS_CSV, encoding="utf-8", on_bad_lines="skip")
    matches = pd.read_csv(MATCHES_CSV, encoding="utf-8", on_bad_lines="skip")
    cups = pd.read_csv(CUPS_CSV, encoding="utf-8", on_bad_lines="skip")
    print(f"  Loaded {len(players):,} player-match rows from WorldCupPlayers.csv")
    print(f"  Loaded {len(matches):,} match rows from WorldCupMatches.csv")
    print(f"  Loaded {len(cups):,} tournament rows from WorldCups.csv")
    return players, matches, cups


def build_furthest_stage_map(cups_df: pd.DataFrame) -> dict[tuple, str]:
    """Build {(team, year): furthest_stage} from WorldCups.csv.
    Kaggle WorldCups.csv has Winner, Runners-Up, Third, Fourth columns.
    We infer stage from those columns."""
    stage_map: dict[tuple, str] = {}
    for _, row in cups_df.iterrows():
        year_str = str(row.get("Year", "")).strip()
        if not year_str.isdigit():
            continue
        year = int(year_str)
        if year not in HISTORICAL_YEARS:
            continue
        winner = normalise_team(str(row.get("Winner", "")))
        runner = normalise_team(str(row.get("Runners-Up", "")))
        third = normalise_team(str(row.get("Third", "")))
        fourth = normalise_team(str(row.get("Fourth", "")))
        if winner:
            stage_map[(winner, year)] = "Final"
        if runner:
            stage_map[(runner, year)] = "Final"
        if third:
            stage_map[(third, year)] = "Third Place Play-off"
        if fourth:
            stage_map[(fourth, year)] = "Third Place Play-off"
    return stage_map


def process_kaggle_players(
    players_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    furthest_stage_map: dict,
) -> pd.DataFrame:
    """Aggregate Kaggle player data into one row per player per tournament.

    WorldCupPlayers.csv has one row per player per match but NO year column.
    We join on MatchID with WorldCupMatches.csv (which has Year) to get the year.
    """
    # Normalise column names
    players_df = players_df.copy()
    matches_df = matches_df.copy()
    players_df.columns = [c.strip() for c in players_df.columns]
    matches_df.columns = [c.strip() for c in matches_df.columns]

    # Build MatchID → Year lookup from WorldCupMatches.csv
    match_id_col = next((c for c in matches_df.columns if c.lower() == "matchid"), None)
    year_col = next((c for c in matches_df.columns if c.lower() == "year"), None)
    if match_id_col is None or year_col is None:
        print(f"  ERROR: WorldCupMatches.csv missing 'MatchID' or 'Year'. Columns: {list(matches_df.columns)}")
        return pd.DataFrame()
    match_year_map = (
        matches_df[[match_id_col, year_col]]
        .drop_duplicates(subset=[match_id_col])
        .rename(columns={match_id_col: "MatchID", year_col: "Year"})
    )
    match_year_map["MatchID"] = pd.to_numeric(match_year_map["MatchID"], errors="coerce")
    match_year_map["Year"] = pd.to_numeric(match_year_map["Year"], errors="coerce")
    match_year_map = match_year_map.dropna()

    # Normalise MatchID in players_df and join
    players_df["MatchID"] = pd.to_numeric(players_df["MatchID"], errors="coerce")
    players_df = players_df.merge(match_year_map, on="MatchID", how="left")

    players_df["Year"] = pd.to_numeric(players_df["Year"], errors="coerce")
    players_df = players_df.dropna(subset=["Year"])
    players_df["Year"] = players_df["Year"].astype(int)

    # Filter to historical years only
    players_df = players_df[players_df["Year"].isin(HISTORICAL_YEARS)].copy()
    if players_df.empty:
        print("  WARNING: no rows found for historical years after filtering.")
        return pd.DataFrame()

    # Normalise player name column
    name_col = next((c for c in players_df.columns if c.lower() in ("playername", "player_name", "player", "player name")), None)
    if name_col is None:
        print(f"  ERROR: Cannot find player name column. Columns: {list(players_df.columns)}")
        return pd.DataFrame()
    players_df = players_df.rename(columns={name_col: "player_name"})
    players_df["player_name"] = players_df["player_name"].astype(str).str.strip()

    # Normalise team column
    team_col = next((c for c in players_df.columns if c.lower() in ("team", "team_initials", "teamname", "team initials")), None)
    if team_col:
        players_df["nationality"] = players_df[team_col].apply(normalise_team)
    else:
        players_df["nationality"] = "Unknown"

    # Normalise position
    role_col = next((c for c in players_df.columns if c.lower() in ("rolename", "role", "position", "pos")), None)
    if role_col:
        players_df["position"] = players_df[role_col].apply(normalise_position)
    else:
        players_df["position"] = "Unknown"

    # Goals: parse from Event column (e.g. "G40' G87'" = 2 goals) if no Goals column
    goal_col = next((c for c in players_df.columns if c.lower() in ("goals", "goalsscored", "goal")), None)
    if goal_col:
        players_df["goals"] = pd.to_numeric(players_df[goal_col], errors="coerce").fillna(0).astype(int)
    elif "Event" in players_df.columns:
        players_df["goals"] = (
            players_df["Event"]
            .fillna("")
            .astype(str)
            .apply(lambda e: len(re.findall(r"G\d", e)))
        )
    else:
        players_df["goals"] = 0

    # Group by player + tournament
    agg = players_df.groupby(
        ["player_name", "nationality", "Year"],
        as_index=False
    ).agg(
        position=("position", "first"),
        matches_played=("player_name", "count"),
        goals=("goals", "sum"),
    )
    agg = agg.rename(columns={"Year": "tournament_year"})

    # Estimate minutes (no event data — use 90 * matches_played as ceiling)
    agg["minutes_played"] = agg["matches_played"] * 90

    # Assists not available in Kaggle dataset — set None
    agg["assists"] = None

    # Furthest stage
    agg["furthest_stage"] = agg.apply(
        lambda r: furthest_stage_map.get((r["nationality"], r["tournament_year"]), "Group Stage"),
        axis=1,
    )

    # IDs and labels
    agg["player_id"] = agg["player_name"].apply(slugify)
    agg["tournament_label"] = "FIFA World Cup " + agg["tournament_year"].astype(str)
    agg["data_source"] = "kaggle"
    agg["data_tier"] = "summary"

    # Per-90 stats (goals only for summary tier)
    mp90 = agg["minutes_played"].where(agg["minutes_played"] > 0).div(90)
    agg["goals_per90"] = (agg["goals"] / mp90).round(3)

    # Zero-fill derived stats not available in summary tier
    for col in [
        "shots", "shots_on_target", "passes", "passes_completed",
        "dribbles_attempted", "dribbles_completed", "pressures", "tackles",
        "shots_per90", "passes_per90", "dribbles_per90", "pressures_per90", "tackles_per90",
        "pass_completion_pct", "dribble_success_pct", "shot_conversion_pct",
    ]:
        agg[col] = None

    # Embedding text
    agg["embedding_text"] = agg.apply(
        lambda r: build_summary_embedding_text(r.to_dict()), axis=1
    )

    return agg


# ---------------------------------------------------------------------------
# 2026 squad data  (manually curated — update as squads are confirmed)
# ---------------------------------------------------------------------------

def load_squads_2026() -> list[dict]:
    """Load squads_2026.json if it exists, else return empty list."""
    path = ROOT / "data" / "squads_2026.json"
    if not path.exists():
        print("  squads_2026.json not found — skipping active_at_2026_wc update")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_existing_player_id(
    coll,
    simple_pid: str,
    nationality: str,
) -> str | None:
    """Find the real player_id in players_master for a squad player.

    Handles the common case where squads_2026.json uses a player's popular name
    (e.g. 'Kylian Mbappé' → 'kylian-mbappe') while StatsBomb stored the legal
    full name (e.g. 'kylian-mbappe-lottin'). Among all token-matching candidates,
    prefers docs with real data (data_source=statsbomb/kaggle) over bare stubs.

    Returns the found player_id, or None if no existing record matches.
    """
    tokens = [t for t in simple_pid.split("-") if len(t) > 1]
    if len(tokens) < 2:
        # Not enough tokens for regex — fall back to exact slug only
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

    # Prefer docs with real pipeline data (have career stats or explicit data_source)
    # over bare squad-stub docs (created by a previous incorrect run with no career data).
    real = [
        c for c in candidates
        if c.get("data_source") in ("statsbomb", "kaggle") or "career_wc_goals" in c
    ]
    pool = real if real else candidates
    # Among the preferred pool, pick the shortest player_id (fewest middle-name tokens)
    return min(pool, key=lambda x: len(x["player_id"]))["player_id"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

print("=" * 60)
print("ScoutIQ Day 3 — Historical WC Data (1998–2014)")
print("=" * 60)

# [1/5] Load Kaggle data
print("\n[1/5] Loading Kaggle CSV data ...")
players_df, matches_df, cups_df = load_kaggle_data()

# [2/5] Build furthest_stage lookup from WorldCups.csv
print("\n[2/5] Building furthest-stage map ...")
furthest_stage_map = build_furthest_stage_map(cups_df)
print(f"  {len(furthest_stage_map)} team-year stage entries built")

# [3/5] Process players → tournament profile rows
print("\n[3/5] Aggregating historical tournament profiles ...")
hist_df = process_kaggle_players(players_df, matches_df, furthest_stage_map)
if hist_df.empty:
    sys.exit("No historical rows processed — check CSV format.")
print(f"  {len(hist_df):,} historical tournament profiles built")
print(f"  Years covered: {sorted(hist_df['tournament_year'].unique())}")
print(f"  Unique players: {hist_df['player_id'].nunique():,}")

tp_docs = clean_nans(hist_df.to_dict("records"))

# [4/5] Upload to MongoDB Atlas
print("\n[4/5] Uploading to MongoDB Atlas ...")
client: MongoClient  = MongoClient(MONGO_URI)
db = client["scoutiq"]

# player_tournament_profiles — upsert on (player_id, tournament_year)
# Won't overwrite existing StatsBomb full-tier records for same key
# because upsert only sets fields via $set; if doc already exists with
# data_tier='full', this will update it. To avoid that, add a guard:
# only upsert if data_tier would not downgrade from 'full' to 'summary'.
existing_full = set(
    (d["player_id"], d["tournament_year"])
    for d in db["player_tournament_profiles"].find(
        {"data_tier": "full"}, {"player_id": 1, "tournament_year": 1, "_id": 0}
    )
)
new_docs = [
    d for d in tp_docs
    if (d["player_id"], d["tournament_year"]) not in existing_full
]
skipped = len(tp_docs) - len(new_docs)
print(f"  Skipping {skipped} records already in full tier (StatsBomb 2018/2022)")

bulk_upsert(
    db["player_tournament_profiles"], new_docs,
    ["player_id", "tournament_year"], "player_tournament_profiles"
)

# players_master — add or update career info for historical players
# Rename to career_wc_* for consistency with StatsBomb pipeline.
# Use $setOnInsert for career stats so we never overwrite StatsBomb full-tier data.
master_agg = hist_df.groupby(
    ["player_id", "player_name", "nationality"], as_index=False
).agg(
    career_wc_goals=("goals", "sum"),
    career_wc_matches=("matches_played", "sum"),
    career_wc_minutes=("minutes_played", "sum"),
    tournaments_played=("tournament_year", lambda x: sorted(x.dropna().unique().tolist())),
    positions_list=("position", lambda x: list(x.dropna().unique())),
)
master_agg["active_at_2026_wc"] = False
master_agg["data_source"] = "kaggle"
master_agg["last_updated"] = pd.Timestamp.now().strftime("%Y-%m-%d")
master_docs = clean_nans(master_agg.to_dict("records"))

# career stats only written on INSERT (new player); existing StatsBomb docs keep theirs
_CAREER_FIELDS = {"career_wc_goals", "career_wc_matches", "career_wc_minutes", "tournaments_played"}
_master_ops = []
for _doc in master_docs:
    _set_always = {k: v for k, v in _doc.items() if k not in _CAREER_FIELDS}
    _set_on_insert = {k: v for k, v in _doc.items() if k in _CAREER_FIELDS}
    _master_ops.append(UpdateOne(
        {"player_id": _doc["player_id"]},
        {"$set": _set_always, "$setOnInsert": _set_on_insert},
        upsert=True,
    ))
if _master_ops:
    _res = db["players_master"].bulk_write(_master_ops, ordered=False)
    print(
        f"  [players_master] total={len(_master_ops)}"
        f" upserted={_res.upserted_count}"
        f" modified={_res.modified_count}"
    )

# [5/5] Mark 2026 active players in players_master
print("\n[5/5] Updating active_at_2026_wc flags ...")
squads_2026 = load_squads_2026()
if squads_2026:
    pm = db["players_master"]

    # Step A: Reset ALL active flags → retired / dropped players automatically get False
    # (Griezmann retired 2024 — this ensures he gets False without manual cleanup)
    pm.update_many({}, {"$set": {"active_at_2026_wc": False}})
    print(f"  Reset active_at_2026_wc=False on all players")

    # Step B: Build {simple_pid: (real_pid, exists_in_db)} map for all squad players
    pid_resolve: dict[str, tuple[str, bool]] = {}
    for player in squads_2026:
        simple_pid = slugify(player.get("player_name", ""))
        if not simple_pid:
            continue
        found = find_existing_player_id(pm, simple_pid, player.get("nationality", ""))
        if found is not None:
            pid_resolve[simple_pid] = (found, True)
        else:
            pid_resolve[simple_pid] = (simple_pid, False)  # genuinely new player

    # Step C: Remove stale duplicate stub docs created by a previous incorrect run
    # These are simple-slug docs (e.g. 'kylian-mbappe') that were wrongly created
    # when the correct full-name doc ('kylian-mbappe-lottin') already existed.
    stale_pids = [
        spid for spid, (rpid, _) in pid_resolve.items()
        if rpid != spid  # a better real slug was found → simple slug doc is a stale stub
    ]
    if stale_pids:
        del_result = pm.delete_many({
            "player_id": {"$in": stale_pids},
            # Only delete stub docs — real historical players keep their record
            "career_wc_goals": {"$exists": False},
            "hist_wc_goals": {"$exists": False},
        })
        if del_result.deleted_count:
            print(f"  Removed {del_result.deleted_count} stale duplicate stub docs")

    # Step D: Set active_at_2026_wc=True on the correct document for each squad player
    active_ops = []
    for player in squads_2026:
        simple_pid = slugify(player.get("player_name", ""))
        if not simple_pid:
            continue
        nationality = player.get("nationality", "")
        target_pid, exists_in_db = pid_resolve.get(simple_pid, (simple_pid, False))
        update_fields = {
            "active_at_2026_wc": True,
            "jersey_number_2026": player.get("jersey_number"),
            "club_2026": player.get("club"),
            "position_2026": player.get("position"),  # separate field; keeps existing position
            "last_updated": pd.Timestamp.now().strftime("%Y-%m-%d"),
        }
        if not exists_in_db:
            # Genuinely new player (never appeared in any tracked WC) — create full record
            update_fields.update({
                "player_id": simple_pid,
                "player_name": player.get("player_name"),
                "nationality": nationality,
            })
        active_ops.append(
            UpdateOne({"player_id": target_pid}, {"$set": update_fields}, upsert=(not exists_in_db))
        )
    if active_ops:
        res = pm.bulk_write(active_ops, ordered=False)
        print(
            f"  2026 squad: {len(squads_2026)} players"
            f" | upserted={res.upserted_count} modified={res.modified_count}"
        )
else:
    print("  No squads_2026.json — run: python ingestion/build_squads_2026.py")

print("\n" + "=" * 60)
print("Day 3 Complete — MongoDB Atlas Summary")
print("=" * 60)
for cname in ["player_match_stats", "player_tournament_profiles", "players_master", "matches"]:
    print(f"  {cname}: {db[cname].count_documents({}):,} docs")
print("\nNext: python embed/embed.py  (Day 4 — Vertex AI embeddings)")
