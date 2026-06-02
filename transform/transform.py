"""
transform.py — Day 2
Transforms players_raw.json into the 4-collection MongoDB schema and uploads to Atlas.
Collections: player_match_stats, player_tournament_profiles, players_master, matches
Run: python transform/transform.py
"""
import json, os, re, sys, math
from pathlib import Path
import pandas as pd # type: ignore
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING
from unidecode import unidecode
from statsbombpy import sb # type: ignore

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
MONGO_URI = os.getenv("MONGODB_CLUSTER_CONNECTION")
if not MONGO_URI:
    sys.exit("ERROR: MONGODB_CLUSTER_CONNECTION not set in .env")
RAW_FILE = ROOT / "players_raw.json"
if not RAW_FILE.exists():
    sys.exit("ERROR: players_raw.json not found. Run: python ingestion/extraction.py")


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
        f"  [{label}] total={len(ops)} upserted={result.upserted_count} modified={result.modified_count}"
    )


def extract_name(val, fallback_key="name") -> str:
    if isinstance(val, dict):
        return val.get(fallback_key) or val.get("name", str(val))
    return str(val) if val is not None else "Unknown"


print("=" * 60)
print("ScoutIQ Day 2 — Transform & Upload")
print("=" * 60)

# [1/7] Load raw data
print("\n[1/7] Loading players_raw.json ...")
with open(RAW_FILE) as f:
    raw = json.load(f)
df = pd.DataFrame(raw)
if "position" not in df.columns:
    print("  WARNING: 'position' missing. Re-run ingestion/extraction.py for accurate data.")
    df["position"] = "Unknown"
df["nationality"] = df["team"]
df["tournament_year"] = df["season"].astype(str).str.extract(r"(\d{4})")[0].astype(int)
df["tournament_label"] = "FIFA World Cup " + df["tournament_year"].astype(str)
df["player_id"] = df["player_name"].apply(slugify)
df["data_source"] = "statsbomb"
df["data_tier"] = "full"
df["match_date"] = pd.to_datetime(df["match_date"])
print(f"  {len(df):,} records loaded")

# [2/7] player_match_stats
print("\n[2/7] Building player_match_stats ...")
match_cols = [
    "player_id", "player_name", "nationality", "position", "team", "match_id",
    "match_date", "tournament_year", "tournament_label", "competition_stage",
    "home_team", "away_team", "goals", "shots", "shots_on_target", "passes",
    "passes_completed", "pass_completion_pct", "dribbles", "dribbles_completed",
    "pressures", "tackles", "minutes_played", "data_source", "data_tier",
]
avail = [c for c in match_cols if c in df.columns]
match_df = df[avail].copy()
match_df["match_date"] = match_df["match_date"].astype(str)
match_docs = clean_nans(match_df.to_dict("records"))
print(f"  {len(match_docs):,} documents prepared")

# [3/7] player_tournament_profiles
print("\n[3/7] Aggregating tournament profiles ...")
df_sorted = df.sort_values("match_date")
tp = df_sorted.groupby(
    ["player_id", "player_name", "nationality", "tournament_year", "tournament_label",
     "data_source", "data_tier"],
    as_index=False,
).agg(
    position=("position", "first"),
    matches_played=("match_id", "nunique"),
    minutes_played=("minutes_played", "sum"),
    goals=("goals", "sum"),
    shots=("shots", "sum"),
    shots_on_target=("shots_on_target", "sum"),
    passes=("passes", "sum"),
    passes_completed=("passes_completed", "sum"),
    dribbles_attempted=("dribbles", "sum"),
    dribbles_completed=("dribbles_completed", "sum"),
    pressures=("pressures", "sum"),
    tackles=("tackles", "sum"),
    furthest_stage=("competition_stage", "last"),
)
mp90 = tp["minutes_played"].where(tp["minutes_played"] > 0).div(90)
tp["goals_per90"] = (tp["goals"] / mp90).round(3)
tp["shots_per90"] = (tp["shots"] / mp90).round(3)
tp["passes_per90"] = (tp["passes"] / mp90).round(1)
tp["dribbles_per90"] = (tp["dribbles_attempted"] / mp90).round(2)
tp["pressures_per90"] = (tp["pressures"] / mp90).round(1)
tp["tackles_per90"] = (tp["tackles"] / mp90).round(2)
tp["pass_completion_pct"] = (
    tp["passes_completed"] / tp["passes"].where(tp["passes"] > 0) * 100
).round(1)
tp["dribble_success_pct"] = (
    tp["dribbles_completed"]
    / tp["dribbles_attempted"].where(tp["dribbles_attempted"] > 0)
    * 100
).round(1)
tp["shot_conversion_pct"] = (
    tp["goals"] / tp["shots"].where(tp["shots"] > 0) * 100
).round(1)


def build_embedding_text(row) -> str:
    return (
        f"{row['player_name']}, {row['position']}, {row['nationality']}, {row['tournament_label']}. "
        f"{row['matches_played']} matches, {row['minutes_played']} minutes played. "
        f"{row['goals']} goals ({(row['goals_per90'] or 0):.3f} per 90), {row['shots']} shots. "
        f"Pass completion {(row['pass_completion_pct'] or 0):.1f}% over {(row['passes_per90'] or 0):.1f} passes per 90. "
        f"Dribble success {(row['dribble_success_pct'] or 0):.1f}%, {(row['dribbles_per90'] or 0):.2f} attempts per 90. "
        f"{(row['pressures_per90'] or 0):.1f} pressures per 90, {(row['tackles_per90'] or 0):.2f} tackles per 90. "
        f"Team reached {row['furthest_stage']}."
    )


tp["embedding_text"] = tp.apply(build_embedding_text, axis=1)
tp_docs = clean_nans(tp.to_dict("records"))
print(f"  {len(tp_docs):,} tournament profile documents prepared")

# [4/7] players_master
print("\n[4/7] Building players_master ...")
master = tp.groupby(["player_id", "player_name", "nationality"], as_index=False).agg(
    career_wc_goals=("goals", "sum"),
    career_wc_matches=("matches_played", "sum"),
    career_wc_minutes=("minutes_played", "sum"),
)
tournaments_map = (
    tp.groupby("player_id")["tournament_year"]
    .apply(lambda x: sorted(x.dropna().unique().tolist()))
    .reset_index()
    .rename(columns={"tournament_year": "tournaments_played"})
)
positions_map = (
    tp.groupby("player_id")["position"]
    .apply(lambda x: list(x.dropna().unique()))
    .reset_index()
    .rename(columns={"position": "positions_list"})
)
peak_tmp = tp.copy()
peak_tmp["goals_per90_filled"] = peak_tmp["goals_per90"].fillna(0)
peak_idx = (
    peak_tmp.loc[peak_tmp.groupby("player_id")["goals_per90_filled"].idxmax()][
        ["player_id", "tournament_year"]
    ].rename(columns={"tournament_year": "peak_tournament_year"})
)
master = (
    master.merge(tournaments_map, on="player_id", how="left")
    .merge(positions_map, on="player_id", how="left")
    .merge(peak_idx, on="player_id", how="left")
)
master["active_at_2026_wc"] = False
master["last_updated"] = pd.Timestamp.now().strftime("%Y-%m-%d")
master_docs = clean_nans(master.to_dict("records"))
print(f"  {len(master_docs):,} player master documents prepared")

# [5/7] matches
print("\n[5/7] Building matches collection ...")
matches_dfs = []
for cid, sid, yr in [(43, 3, 2018), (43, 106, 2022)]:
    m = sb.matches(competition_id=cid, season_id=sid)
    m["tournament_year"] = yr
    matches_dfs.append(m)
matches_df = pd.concat(matches_dfs, ignore_index=True)
matches_df["competition_stage"] = matches_df["competition_stage"].apply(
    lambda x: extract_name(x, "name") if not isinstance(x, str) else x
)
matches_df["home_team"] = matches_df["home_team"].apply(
    lambda x: extract_name(x, "home_team_name") if not isinstance(x, str) else x
)
matches_df["away_team"] = matches_df["away_team"].apply(
    lambda x: extract_name(x, "away_team_name") if not isinstance(x, str) else x
)
keep = [
    "match_id", "tournament_year", "match_date", "kick_off", "competition_stage",
    "match_week", "home_team", "away_team", "home_score", "away_score",
]
avail_m = [c for c in keep if c in matches_df.columns]
matches_out = matches_df[avail_m].copy()
matches_out["match_date"] = matches_out["match_date"].astype(str)
matches_out["winner"] = matches_out.apply(
    lambda r: r["home_team"]
    if r["home_score"] > r["away_score"]
    else (r["away_team"] if r["away_score"] > r["home_score"] else "Draw"),
    axis=1,
)
matches_docs = clean_nans(matches_out.to_dict("records"))
print(f"  {len(matches_docs):,} match documents prepared")

# [6/7] Upload to MongoDB Atlas
print("\n[6/7] Uploading to MongoDB Atlas ...")
client: MongoClient  = MongoClient(MONGO_URI)
db = client["scoutiq"]
bulk_upsert(db["player_match_stats"], match_docs, ["player_id", "match_id"], "player_match_stats")
bulk_upsert(db["player_tournament_profiles"], tp_docs, ["player_id", "tournament_year"], "player_tournament_profiles")
bulk_upsert(db["players_master"], master_docs, ["player_id"], "players_master")
bulk_upsert(db["matches"], matches_docs, ["match_id"], "matches")

# [7/7] Indexes
print("\n[7/7] Creating indexes ...")
db["player_match_stats"].create_index(
    [("player_id", ASCENDING), ("match_id", ASCENDING)], unique=True, background=True
)
db["player_match_stats"].create_index([("player_id", ASCENDING)], background=True)
db["player_match_stats"].create_index(
    [("nationality", ASCENDING), ("tournament_year", DESCENDING)], background=True
)
db["player_tournament_profiles"].create_index(
    [("player_id", ASCENDING), ("tournament_year", ASCENDING)], unique=True, background=True
)
db["player_tournament_profiles"].create_index([("player_name", ASCENDING)], background=True)
db["player_tournament_profiles"].create_index(
    [("nationality", ASCENDING), ("tournament_year", DESCENDING)], background=True
)
db["player_tournament_profiles"].create_index(
    [("position", ASCENDING), ("tournament_year", DESCENDING)], background=True
)
db["players_master"].create_index([("player_id", ASCENDING)], unique=True, background=True)
db["players_master"].create_index([("player_name", ASCENDING)], background=True)
db["players_master"].create_index([("nationality", ASCENDING)], background=True)
db["players_master"].create_index([("active_at_2026_wc", ASCENDING)], background=True)
db["matches"].create_index([("match_id", ASCENDING)], unique=True, background=True)
db["matches"].create_index([("tournament_year", ASCENDING)], background=True)
print("  All indexes created.")

print("\n" + "=" * 60)
print("Day 2 Complete — MongoDB Atlas Summary")
print("=" * 60)
for cname in ["player_match_stats", "player_tournament_profiles", "players_master", "matches"]:
    print(f"  {cname}: {db[cname].count_documents({}):,} docs")
print("\nNext: python embed/embed.py  (Day 4 — Vertex AI embeddings)")
