# ScoutIQ — Complete Build Plan
**AI Agent for Real-Time Football Scouting & Match Intelligence**
*Google Cloud Rapid Agent Hackathon — MongoDB Track*

---

## Table of Contents
1. [Vision & Architecture](#vision)
2. [MongoDB Cluster Structure](#mongodb)
3. [Data Coverage Strategy](#data)
4. [Day-by-Day Build Plan](#days)

---

## 1. Vision & Architecture <a name="vision"></a>

ScoutIQ is a multi-step AI scouting agent that **acts**, not just answers. Given a query like:

- *"Who plays like Iniesta in the 2026 World Cup?"*
- *"Compare Mbappé's 2026 form to his 2018 peak"*
- *"Who has replaced Griezmann as France's creative midfielder in 2026?"*

The agent executes a reasoning loop:
1. Interprets the query → identifies referenced players, tournaments, roles
2. Calls MongoDB MCP tools → vector search + structured lookups
3. Calls web grounding → live 2026 form, news, squad updates
4. Synthesises → produces a structured scouting report with confidence score

**Stack:** Gemini 2.5 Flash → Agent Builder → MongoDB MCP Server → Atlas Vector Search → Cloud Run → Arize

---

## 2. MongoDB Cluster Structure <a name="mongodb"></a>

### Database: `scoutiq`

Four collections, each with a distinct role:

---

### Collection A: `player_match_stats`
**Granularity:** One document per player per match  
**Purpose:** Raw match-level stats for timeline analysis, form curves, match breakdowns

```json
{
  "_id": "ObjectId",
  "player_id": "kylian-mbappe",
  "player_name": "Kylian Mbappé",
  "nationality": "France",
  "position": "Forward",
  "match_id": 8650,
  "match_date": "2018-07-06",
  "tournament_year": 2018,
  "tournament_label": "FIFA World Cup 2018",
  "competition_stage": "Quarter-finals",
  "home_team": "France",
  "away_team": "Uruguay",
  "team": "France",
  "result": "Win",
  "goals": 1,
  "shots": 4,
  "shots_on_target": 2,
  "passes": 38,
  "passes_completed": 31,
  "pass_completion_pct": 81.6,
  "dribbles": 7,
  "dribbles_completed": 5,
  "pressures": 15,
  "tackles": 1,
  "minutes_played": 90,
  "data_source": "statsbomb",
  "data_tier": "full"
}
```

**Document counts per player (this collection):**
- Mbappé: ~11 docs for 2018 + ~7 for 2022 + live 2026 docs = ~25 total
- Griezmann: ~7 docs for 2018 + ~6 for 2022 (+ he played WC 2014: ~7) = ~20 total
- Iniesta: ~7 for 2006 + ~7 for 2010 + ~7 for 2014 = ~21 (summary-tier, see data sources)

This collection is **NOT embedded**. It is queried structurally by the agent's `get_match_timeline` tool.

---

### Collection B: `player_tournament_profiles`
**Granularity:** One document per player per World Cup  
**Purpose:** Aggregated tournament performance — the PRIMARY vector search collection

This is the answer to *"should Mbappé have 11 or 22 documents?"*:
- **In `player_match_stats`:** 11 docs (2018) + 7 docs (2022) = 18 match-level docs
- **In `player_tournament_profiles`:** 1 doc (2018) + 1 doc (2022) = **2 aggregated profile docs** — each carrying an embedding

The embedding is computed on a rich text summary of the player's *entire tournament performance*, not individual matches. This is what powers similarity search.

```json
{
  "_id": "ObjectId",
  "player_id": "kylian-mbappe",
  "player_name": "Kylian Mbappé",
  "nationality": "France",
  "position": "Forward",
  "date_of_birth": "1998-12-20",
  "tournament_year": 2018,
  "tournament_label": "FIFA World Cup 2018",
  "competition_id": 43,
  "season_id": 3,

  "matches_played": 6,
  "minutes_played": 540,

  "goals": 4,
  "shots": 20,
  "shots_on_target": 10,
  "shot_conversion_pct": 20.0,

  "passes": 270,
  "passes_completed": 225,
  "pass_completion_pct": 83.3,

  "dribbles_attempted": 45,
  "dribbles_completed": 30,
  "dribble_success_pct": 66.7,

  "pressures": 90,
  "tackles": 10,

  "goals_per90": 0.67,
  "shots_per90": 3.33,
  "passes_per90": 45.0,
  "dribbles_attempted_per90": 7.5,
  "pressures_per90": 15.0,

  "team_result": "World Champion",
  "furthest_stage_reached": "Final",

  "data_source": "statsbomb",
  "data_tier": "full",

  "embedding_text": "Kylian Mbappé, Forward, France, FIFA World Cup 2018. 4 goals in 6 matches (0.67 per 90). Shot conversion 20%. 83.3% pass completion over 45 passes per game. 66.7% dribble success rate, highly dynamic dribbler (7.5 attempts per 90). Active presser with 15 pressures per 90. Team reached the Final, won the tournament.",

  "embedding": [ 0.123, 0.456, ... ]
}
```

**Why per-90 stats?** Players who played 1 match vs 7 matches have incomparable raw totals. Per-90 normalises this so Iniesta (60 min in 1 match) can be fairly compared to Modric (7 full games).

**Indexes on this collection:**
```js
{ "player_name": 1 }
{ "nationality": 1 }
{ "position": 1 }
{ "tournament_year": 1 }
{ "player_id": 1, "tournament_year": 1 }  // unique compound
// Vector Search index on "embedding" field, 768 dims, cosine
```

---

### Collection C: `players_master`
**Granularity:** One document per player (lifetime)  
**Purpose:** Canonical player reference — links all tournaments, stores career arc, active status

```json
{
  "_id": "ObjectId",
  "player_id": "andres-iniesta",
  "player_name": "Andrés Iniesta",
  "nationality": "Spain",
  "positions": ["Central Midfield", "Attacking Midfield"],
  "date_of_birth": "1984-05-11",
  "active_at_2026_wc": false,
  "tournaments_played": [2006, 2010, 2014],
  "career_wc_goals": 2,
  "career_wc_assists": 6,
  "career_wc_matches": 17,
  "peak_tournament_year": 2010,
  "peak_tournament_label": "FIFA World Cup 2010",
  "style_tags": ["deep playmaker", "vision passer", "calm under pressure", "high pass completion", "low volume dribbler"],
  "notes": "Won 2010 World Cup with Spain. Famous for final-winning goal. Central cog of tiki-taka system.",
  "last_updated": "2026-06-01"
}
```

This collection is used when the agent needs to answer:
- *"Who is Iniesta?"* → look up master profile, find peak tournament year
- *"Did Griezmann play 2026?"* → check `active_at_2026_wc`
- *"Who are France's 2026 midfielders?"* → filter by `nationality=France`, `active_at_2026_wc=true`, `positions contains midfield`

---

### Collection D: `matches`
**Granularity:** One document per match  
**Purpose:** Match metadata (teams, score, stage, date) for contextual answers

```json
{
  "_id": "ObjectId",
  "match_id": 8650,
  "tournament_year": 2018,
  "match_date": "2018-07-06",
  "competition_stage": "Quarter-finals",
  "home_team": "Brazil",
  "away_team": "Belgium",
  "home_score": 1,
  "away_score": 2,
  "winner": "Belgium"
}
```

---

## 3. Data Coverage Strategy <a name="data"></a>

ScoutIQ needs three temporal layers to answer the full range of queries:

```
LAYER 1 ──────────── LAYER 2 ────────────── LAYER 3
1998–2014            2018 + 2022              2026 (live)
Historical context   Full event data          Real-time
(summary tier)       (full tier)              (streaming tier)
Kaggle/Wikipedia     StatsBomb open data      StatsBomb live + web grounding
```

### Layer 1 — Historical Context (WC 1998–2014)
**Source:** [Kaggle FIFA World Cup All-Time Stats](https://www.kaggle.com/datasets/abecklas/fifa-world-cup) + Wikipedia scraping for squad lists  
**Stats available:** goals, assists, matches, position, nationality, team result  
**Stats NOT available:** passes, dribbles, pressures, xG (no event-level data)  
**`data_tier` field:** `"summary"` — the embedding text is simpler but sufficient

**Why include this layer?**
- Enables *"who plays like Iniesta?"* — even with basic stats, the embedding captures goal/assist rate, position, pass style (inferred from Wikipedia text), tournament context
- Enables *"was Ronaldo ever in a World Cup?"* — basic factual lookups
- Enables career arc for master profiles

**Players covered:** Every player with >90 minutes in a WC 1998–2014 (approx. 500+ players)

**Embedding text example for Iniesta 2010:**
```
Andrés Iniesta, Central Midfielder, Spain, FIFA World Cup 2010. 
7 matches played, 1 goal (scored the winning goal in the final), 
2 assists. Team won the tournament. High pass volume, calm under 
pressure, key figure in Spain's tiki-taka system. Central creative 
hub, rarely dribbled but always found passing lanes.
```
(Text is augmented from Kaggle stats + Wikipedia role description)

---

### Layer 2 — Full Event Data (WC 2018 + 2022)
**Source:** StatsBomb open data via `statsbombpy`  
**Stats:** shots, passes, dribbles, pressures, tackles, xG (if available), exact match-level breakdown  
**`data_tier` field:** `"full"`  
**Coverage:**
- 2018 WC: 64 matches × ~22 players = ~1,400 player-match documents
- 2022 WC: 64 matches × ~22 players = ~1,400 player-match documents
- Tournament profiles: ~500 unique players × 1 doc per WC they appeared in

> ✅ **Day 1 (complete):** `players_raw.json` already contains match-level records for 2018+2022 (flat format, one doc per player per match). Day 2 will transform this into the two-collection schema.

---

### Layer 3 — Live 2026 Data
**Primary source:** StatsBomb releases event data within 24–48h of each match  
**Check:** `sb.competitions()` after each matchday to see if new season_id appears for 2026 WC  
**Fallback (if StatsBomb not yet available):** 
- [football-data.org](https://www.football-data.org/) free API (goals, lineups, results)
- ESPN API / web grounding via Agent Builder built-in tool

**2026 squad data (immediate need):**
- Source: Wikipedia / official FIFA squad pages (scrape or manual JSON)
- Used to answer *"who is France's midfielder in 2026?"* even before match data arrives
- Stored in `players_master` with `active_at_2026_wc: true`

---

### Player Selection Logic

| Player type | Include? | Why |
|---|---|---|
| Mbappé (2018, 2022, 2026) | ✅ Yes | Cross-WC comparison, live 2026 tracking |
| Griezmann (2014, 2018, 2022, not 2026) | ✅ Yes | "Who replaced him?" queries |
| Iniesta (2006, 2010, 2014) | ✅ Yes | Similarity reference ("plays like Iniesta") |
| Ronaldo C. (2006–2022) | ✅ Yes | All-time reference player |
| Zidane (1998, 2002, 2006) | ✅ Yes | Historical archetype for style matching |
| 2026 debutants | ✅ Yes | The users' primary use case |
| Players with <45 min total WC | ⚠️ Optional | Include but low embedding weight |

**Rule:** Include ALL players who appeared in at least one WC since 1998, regardless of retirement status. Historical players are the reference anchors for similarity search.

---

## 4. Day-by-Day Build Plan <a name="days"></a>

---

### Day 1 — Environment Setup + Data Extraction ✅ COMPLETE
**Outcome:** `players_raw.json` exists with per-match stats for 2018 + 2022 WC

What was done:
- StatsBomb 2018 (competition_id=43, season_id=3) and 2022 (season_id=106) extracted
- `players_raw.json`: one record per player per match — contains goals, shots, passes, dribbles, pressures, tackles, pass_completion_pct, season, competition_stage, home_team, away_team, match_date
- **Gap to fix in Day 2:** `minutes_played` is 0 for all records (not yet extracted from substitution events). Day 2 will fix this.

---

### Day 2 — Schema Design + MongoDB Upload

**Goal:** Transform `players_raw.json` into the proper 4-collection schema and upload to Atlas.

#### Step 1 — Fix minutes_played
The current extraction leaves `minutes_played: 0`. Fix by:
- Checking substitution events: a player who was subbed off at minute 67 played 67 minutes
- A starting player with no substitution played 90 (or 120 in extra time)
- Use StatsBomb's lineup + substitution events to compute this accurately

```python
# In extraction.py — add to get_player_stats():
# Pull substitution events
subs = events[events['type'] == 'Substitution']
lineups_data = sb.lineups(match_id=match_id)
# For each player: if in starting XI and not subbed = 90 min
# If subbed off: use the 'minute' of the substitution event
# If subbed on: 90 - minute_of_substitution
```

#### Step 2 — Enrich with position data
StatsBomb lineups include `position`. Pull from `sb.lineups(match_id)` and join on player_name to add `position` field to each record.

```python
# For each match, call sb.lineups(match_id=mid)
# lineups is a dict: {'TeamA': DataFrame, 'TeamB': DataFrame}
# Each DataFrame has columns: player_id, player_name, player_nickname, jersey_number, country, position
```

#### Step 3 — Aggregate to tournament profiles
From match-level records, group by `(player_name, season)` and aggregate:

```python
import pandas as pd

df = pd.read_json('players_raw.json')

# Fix: add nationality from team (for 2018/2022, team == nationality)
df['nationality'] = df['team']

# Aggregate per player per tournament
tournament_profiles = df.groupby(['player_name', 'nationality', 'season']).agg(
    position=('position', 'first'),
    matches_played=('match_id', 'nunique'),
    minutes_played=('minutes_played', 'sum'),
    goals=('goals', 'sum'),
    shots=('shots', 'sum'),
    shots_on_target=('shots_on_target', 'sum'),
    passes=('passes', 'sum'),
    passes_completed=('passes_completed', 'sum'),
    dribbles_attempted=('dribbles', 'sum'),
    dribbles_completed=('dribbles_completed', 'sum'),
    pressures=('pressures', 'sum'),
    tackles=('tackles', 'sum'),
    furthest_stage=('competition_stage', 'last'),  # last match = furthest stage
).reset_index()

# Compute per-90 stats (core for fair comparison)
mp90 = tournament_profiles['minutes_played'] / 90
tournament_profiles['goals_per90'] = (tournament_profiles['goals'] / mp90).round(3)
tournament_profiles['shots_per90'] = (tournament_profiles['shots'] / mp90).round(3)
tournament_profiles['passes_per90'] = (tournament_profiles['passes'] / mp90).round(1)
tournament_profiles['dribbles_per90'] = (tournament_profiles['dribbles_attempted'] / mp90).round(2)
tournament_profiles['pressures_per90'] = (tournament_profiles['pressures'] / mp90).round(1)
tournament_profiles['pass_completion_pct'] = (
    tournament_profiles['passes_completed'] / tournament_profiles['passes'] * 100
).round(1)
tournament_profiles['dribble_success_pct'] = (
    tournament_profiles['dribbles_completed'] / tournament_profiles['dribbles_attempted'] * 100
).round(1).fillna(0)

tournament_profiles['data_tier'] = 'full'
tournament_profiles['data_source'] = 'statsbomb'
tournament_profiles['tournament_label'] = 'FIFA World Cup ' + tournament_profiles['season'].astype(str)
tournament_profiles['player_id'] = tournament_profiles['player_name'].str.lower().str.replace(' ', '-').str.replace('[^a-z0-9-]', '', regex=True)
```

#### Step 4 — Build player_id slug
Consistent `player_id` across all collections (slug format):
- `"Kylian Mbappé"` → `"kylian-mbappe"`
- `"Andrés Iniesta"` → `"andres-iniesta"`

Use `unidecode` to strip accents before slugifying.

```bash
pip install unidecode pymongo python-dotenv
```

#### Step 5 — Build players_master
Aggregate from tournament_profiles to get career-level info, then manually mark `active_at_2026_wc` based on official 2026 squad lists (scrape Wikipedia or paste manually as JSON for the 32 teams).

#### Step 6 — Upload to MongoDB Atlas

```python
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
import os

load_dotenv()
client = MongoClient(os.getenv('MONGODB_CLUSTER_CONNECTION'))
db = client['scoutiq']

# Upsert player_tournament_profiles
profiles_col = db['player_tournament_profiles']
ops = [
    UpdateOne(
        {'player_id': p['player_id'], 'tournament_year': int(p['season'])},
        {'$set': p},
        upsert=True
    )
    for p in tournament_profiles_dicts
]
profiles_col.bulk_write(ops)

# Upsert player_match_stats (raw records from players_raw.json)
match_stats_col = db['player_match_stats']
# ... similar bulk upsert

# Upsert players_master
# ...

# Upsert matches
# ...
```

Use `upsert=True` on all writes so re-runs are idempotent (safe to re-run without duplicates).

#### Step 7 — Create Atlas indexes
In the Atlas UI or via `pymongo`:
```python
profiles_col.create_index([('player_id', 1)])
profiles_col.create_index([('player_name', 1)])
profiles_col.create_index([('nationality', 1), ('tournament_year', -1)])
profiles_col.create_index([('position', 1), ('tournament_year', -1)])
```

**End of Day 2 checkpoint:** `player_tournament_profiles` has ~500 documents with clean aggregated stats. `player_match_stats` has ~2800 documents. Basic Atlas `find()` queries return correct results.

---

### Day 3 — Historical WC Data (1998–2014) + Player Master

**Goal:** Add historical context for retired players (Iniesta, Zidane, etc.) so similarity search works across generations.

#### Step 1 — Download historical data
Primary source: [Kaggle FIFA World Cup dataset](https://www.kaggle.com/datasets/abecklas/fifa-world-cup)
- File: `WorldCupPlayers.csv` — contains player name, team, position, matches played per WC
- File: `WorldCups.csv` — tournament-level results

Supplementary: Scrape or manually compile player stats summaries from:
- https://www.worldfootball.net/
- https://en.wikipedia.org/wiki/FIFA_World_Cup (for squad lists)

Key stats to extract per player per WC (1998–2014):
- matches_played, minutes_played (if available, else estimate: starter=90/game)
- goals, assists (from Wikipedia/World Cup stats pages)
- position (from Kaggle `RoleName` field)

#### Step 2 — Normalise and insert as `data_tier: "summary"`
These records have no event-level stats (no passes, dribbles, pressures).
The embedding text will be enriched with qualitative descriptors drawn from known player archetypes.

```python
def build_summary_embedding_text(row):
    text = f"{row['player_name']}, {row['position']}, {row['nationality']}, "
    text += f"FIFA World Cup {row['tournament_year']}. "
    text += f"{row['matches_played']} matches played"
    if row.get('minutes_played'):
        text += f", {row['minutes_played']} minutes"
    text += f". {row['goals']} goals, {row.get('assists', 'unknown')} assists."
    text += f" Team reached {row['furthest_stage']}."
    # Add role descriptor from known player style tags if available
    if row['player_id'] in KNOWN_STYLES:
        text += f" {KNOWN_STYLES[row['player_id']]}"
    return text
```

`KNOWN_STYLES` is a manually curated dictionary for ~50 historically significant players (Iniesta, Zidane, Ronaldinho, Messi, Ronaldo, Ballack, Rooney, etc.) with a 1-2 sentence description of their playing style.

#### Step 3 — Build `players_master` for retired players
For each historical player, set `active_at_2026_wc: false`. For 2026 participants, set `true`.

#### Step 4 — Add 2026 squad data
Manually (or via scraping) create a JSON file `squads_2026.json`:
```json
[
  {"player_name": "Ousmane Dembélé", "nationality": "France", "position": "Right Wing", "active_at_2026_wc": true, "jersey_number": 11, "club": "PSG"},
  ...
]
```
Insert into `players_master` with `upsert` on `player_id`.

**End of Day 3 checkpoint:** `player_tournament_profiles` now has entries from 1998–2022. `players_master` has all ~2000 historical WC players. "Who played like Iniesta?" can now be answered (embeddings generated tomorrow).

---

### Day 4 — Embeddings + Vector Search Index

**Goal:** Generate Vertex AI embeddings for every document in `player_tournament_profiles` and build the Atlas Vector Search index.

#### Step 1 — Set up Vertex AI

```python
import vertexai
from vertexai.language_models import TextEmbeddingModel

vertexai.init(project="scoutiq-498113", location="us-central1")
model = TextEmbeddingModel.from_pretrained("text-embedding-004")
```

#### Step 2 — Generate embeddings in batch
Vertex AI `text-embedding-004` produces 768-dimensional vectors.

```python
def embed_batch(texts, batch_size=250):
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        results = model.get_embeddings(batch)
        embeddings.extend([r.values for r in results])
    return embeddings

# Pull all profiles without embeddings
profiles = list(db['player_tournament_profiles'].find(
    {'embedding': {'$exists': False}},
    {'_id': 1, 'embedding_text': 1}
))

texts = [p['embedding_text'] for p in profiles]
ids = [p['_id'] for p in profiles]
vectors = embed_batch(texts)

# Bulk write back
ops = [
    UpdateOne({'_id': ids[i]}, {'$set': {'embedding': vectors[i]}})
    for i in range(len(ids))
]
db['player_tournament_profiles'].bulk_write(ops)
```

Estimated cost: ~1000 profiles × 768 dims → negligible on Vertex AI free tier / micro billing.

#### Step 3 — Create Atlas Vector Search index
In MongoDB Atlas UI:
1. Navigate to Atlas Search → Create Search Index
2. Select: **Vector Search**
3. Collection: `scoutiq.player_tournament_profiles`
4. Index definition:
```json
{
  "fields": [
    {
      "numDimensions": 768,
      "path": "embedding",
      "similarity": "cosine",
      "type": "vector"
    },
    {
      "path": "position",
      "type": "filter"
    },
    {
      "path": "tournament_year",
      "type": "filter"
    },
    {
      "path": "nationality",
      "type": "filter"
    }
  ]
}
```

The `filter` fields allow hybrid queries like: *"Find players like Iniesta BUT only among 2026 midfielders"*.

#### Step 4 — Test vector search manually

```python
def search_similar_players(query_text, tournament_year=None, position=None, limit=5):
    query_embedding = model.get_embeddings([query_text])[0].values
    
    pipeline = [
        {
            "$vectorSearch": {
                "index": "player_embedding_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 150,
                "limit": limit,
                "filter": {k: v for k, v in {
                    "tournament_year": tournament_year,
                    "position": position
                }.items() if v is not None}
            }
        },
        {
            "$project": {
                "player_name": 1, "nationality": 1, "position": 1,
                "tournament_year": 1, "goals_per90": 1, "pass_completion_pct": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]
    return list(db['player_tournament_profiles'].aggregate(pipeline))

# Test 1: similarity query
results = search_similar_players("deep playmaker, excellent vision, high pass completion, calm under pressure")
# Expect: Iniesta, Xavi, Modric, Busquets, Kroos type players

# Test 2: constrained to 2026 players only
results = search_similar_players("fast pacey winger, strong dribbler, high shot volume", tournament_year=2026)
```

**End of Day 4 checkpoint:** Vector search returns sensible results. *"Fast left winger, strong dribbler"* returns Mbappé, Neymar, Salah-type profiles. The agent's core intelligence is live.

---

### Day 5 — Live 2026 Data Pipeline

**Goal:** Ingest live 2026 WC data as matches are played so the agent always has current information.

#### Step 1 — Check StatsBomb 2026 availability
```python
comps = sb.competitions()
wc_2026 = comps[(comps['competition_id'] == 43) & (comps['season_name'] == '2026')]
# If this returns a row: StatsBomb has 2026 data → use the season_id
```

StatsBomb typically releases free data within 24–48h of each match during major tournaments.

#### Step 2 — Live ingestion script `ingest_live.py`
Run this manually (or via Cloud Scheduler) after each matchday:

```python
def ingest_new_matches(competition_id=43, season_id=None):
    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    existing_ids = set(db['player_match_stats'].distinct('match_id'))
    new_matches = matches[~matches['match_id'].isin(existing_ids)]
    
    for _, match in new_matches.iterrows():
        player_stats = get_player_stats(match['match_id'])
        # Insert into player_match_stats
        # Re-aggregate player_tournament_profiles for 2026
        # Re-embed the updated 2026 tournament profile
        # Upsert to MongoDB
        print(f"Ingested match {match['match_id']}: {match['home_team']} vs {match['away_team']}")
```

#### Step 3 — Fallback: football-data.org API
If StatsBomb 2026 is not yet available:
```python
import requests

API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')  # free tier available
headers = {'X-Auth-Token': API_KEY}

# Get 2026 WC matches
r = requests.get('https://api.football-data.org/v4/competitions/WC/matches', headers=headers)
matches = r.json()['matches']
# Basic stats: goals, assists, cards — no event-level data
# Store as data_tier: "live_summary"
```

#### Step 4 — Agent Builder web grounding supplement
For the most current 2026 form (injuries, news, tactical changes), Agent Builder's built-in **Google Search grounding** is enabled. This covers what no database can: yesterday's injury report, a coach's press conference, etc.

**End of Day 5 checkpoint:** 2026 data flows into the database. Embeddings for 2026 players exist. The agent can answer questions about ongoing WC 2026 performance.

---

### Day 6 — MCP Server (MongoDB Tools)

**Goal:** Build the Python MCP server that exposes 4 MongoDB tools to the agent.

#### Tool 1: `search_players`
```python
@mcp_server.tool()
def search_players(query_text: str, tournament_year: int = None, 
                   position: str = None, nationality: str = None, 
                   limit: int = 5) -> list[dict]:
    """
    Semantic search for players matching a description or playing style.
    Embeds query_text and runs Atlas $vectorSearch.
    Use this for: "who plays like X", "find a fast winger", "similar to Iniesta"
    """
    embedding = embed(query_text)
    filters = {}
    if tournament_year: filters['tournament_year'] = tournament_year
    if position: filters['position'] = {'$regex': position, '$options': 'i'}
    if nationality: filters['nationality'] = nationality
    return run_vector_search(embedding, filters, limit)
```

#### Tool 2: `get_player_profile`
```python
@mcp_server.tool()
def get_player_profile(player_name: str, tournament_year: int = None) -> dict:
    """
    Exact lookup for a player's tournament profile.
    Returns stats for a specific WC year, or all years if no year given.
    Use this for: "Mbappé's 2018 stats", "Griezmann's World Cup record"
    """
    query = {'player_name': {'$regex': player_name, '$options': 'i'}}
    if tournament_year:
        query['tournament_year'] = tournament_year
    return list(db['player_tournament_profiles'].find(query, {'embedding': 0}))
```

#### Tool 3: `get_match_timeline`
```python
@mcp_server.tool()
def get_match_timeline(player_name: str, tournament_year: int) -> list[dict]:
    """
    Returns match-by-match breakdown for a player in a tournament.
    Use for: "how did Mbappé perform across all 2022 matches?", form analysis.
    """
    return list(db['player_match_stats'].find(
        {'player_name': {'$regex': player_name, '$options': 'i'}, 
         'tournament_year': tournament_year},
        {'_id': 0}
    ).sort('match_date', 1))
```

#### Tool 4: `get_team_players`
```python
@mcp_server.tool()
def get_team_players(nationality: str, tournament_year: int = None, 
                     position: str = None) -> list[dict]:
    """
    Returns all players for a team in a given WC.
    Use for: "France's 2026 midfielders", "who replaced Griezmann?"
    """
    query = {'nationality': {'$regex': nationality, '$options': 'i'}}
    if tournament_year:
        query['tournament_year'] = tournament_year
    if position:
        query['position'] = {'$regex': position, '$options': 'i'}
    return list(db['player_tournament_profiles'].find(query, {'embedding': 0}).sort('goals_per90', -1))
```

**End of Day 6 checkpoint:** MCP server runs locally on port 8080. All 4 tools tested with hardcoded inputs. Each returns correct MongoDB data.

---

### Day 7 — Agent Builder + Prompt Engineering

**Goal:** Wire the MCP server into Agent Builder and craft a system prompt that produces structured scouting reports.

#### Step 1 — Create agent in Agent Builder
1. Go to: https://console.cloud.google.com/agent-platform
2. Create new agent → select **Gemini 2.5 Flash**
3. Register MCP server as tool source (HTTP endpoint)
4. Enable **Google Search grounding** (the toggle in Agent Builder)

#### Step 2 — System prompt
```
You are ScoutIQ, an elite AI football scouting agent for the 2026 FIFA World Cup.
You have access to a database of player statistics from every World Cup since 1998 
and real-time 2026 match data.

When asked about players, you MUST use the provided tools to retrieve real data — 
never hallucinate statistics. Web grounding supplements live information only.

For every scouting query, produce a structured report:

## [Player Name] — Scouting Report
**Position:** [position]  **Nationality:** [nationality]  **WC:** [year(s)]

### Key Stats ([tournament_year])
| Metric | Value | Per 90 |
|--------|-------|--------|
| Goals  | ...   | ...    |
| Pass % | ...   | —      |
| Dribble success | ... | ... |

### Style Assessment
[2-3 sentences on playing style, strengths, weaknesses derived from stats]

### Historical Comparison
[If user asked "like X": name the closest matching player from your search results 
with similarity score, explain the statistical basis]

### Form Rating (1–10)
[Rate based on per-90 stats relative to position average across all WC data]

### Tactical Recommendation
[One actionable recommendation for a coach, scout, or fantasy manager]

### Confidence: [HIGH / MEDIUM / LOW]
[LOW if using summary-tier data or web grounding only; HIGH if full StatsBomb data]
```

#### Step 3 — Test queries
Run these 5 queries through the Agent Builder chat UI:
1. "Who plays like Andrés Iniesta in the 2026 World Cup?"
2. "Compare Mbappé's 2026 form to his 2018 World Cup stats"
3. "Who replaced Griezmann as France's creative midfielder in 2026?"
4. "Best forwards in the 2026 group stage by goals per 90"
5. "Tell me about Pedri's World Cup performance"

Verify: the agent calls MongoDB tools, not just hallucinating numbers.

**End of Day 7 checkpoint:** Agent produces structured reports from real data. Tool calls visible in trace log.

---

### Day 8 — Arize Integration (Observability)

**Goal:** Instrument every agent run with OpenTelemetry traces and Arize evaluators.

#### Step 1 — Install and configure Arize Phoenix
```bash
pip install arize-phoenix opentelemetry-sdk opentelemetry-exporter-otlp
```

```python
import phoenix as px
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# Initialize Phoenix tracer
px.launch_app()  # or connect to Arize cloud
provider = TracerProvider()
provider.add_span_exporter(OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces"))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("scoutiq-mcp")
```

#### Step 2 — Instrument MCP tool calls
```python
@mcp_server.tool()
def search_players(query_text: str, ...):
    with tracer.start_as_current_span("search_players") as span:
        span.set_attribute("query_text", query_text)
        span.set_attribute("tournament_year", str(tournament_year))
        results = run_vector_search(...)
        span.set_attribute("results_count", len(results))
        span.set_attribute("top_result", results[0]['player_name'] if results else "none")
        return results
```

#### Step 3 — Set up 2 Arize evaluators

**Evaluator 1: Retrieval Relevance**
- Question: "Are the MongoDB results relevant to the user's query?"
- Implementation: LLM-as-judge using Gemini Flash on `(query, retrieved_docs)` pair
- Output: score 0–1

**Evaluator 2: Groundedness**
- Question: "Is the scouting report supported by the retrieved documents?"
- Implementation: Check if every stat in the report appears in the retrieved data
- Output: score 0–1 → displayed as **Confidence badge** in UI

#### Step 4 — Expose confidence in API response
```python
# In agent wrapper:
response = agent.query(user_query)
groundedness_score = arize_evaluator.evaluate(response, retrieved_docs)
confidence = "HIGH" if groundedness_score > 0.8 else "MEDIUM" if groundedness_score > 0.5 else "LOW"
return {"report": response.text, "confidence": confidence, "trace_id": span.context.trace_id}
```

**End of Day 8 checkpoint:** Arize dashboard shows traces. Each report has a groundedness score. The `confidence` field is returned in the API response.

---

### Day 9 — Streamlit UI

**Goal:** Build a clean web UI that feels like a professional scouting tool.

#### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  ⚽ ScoutIQ          [2026 World Cup Intelligence]           │
├─────────────────────────────────────────────────────────────┤
│  🔍 [Ask ScoutIQ anything about 2026 WC players...]  [Ask]  │
├──────────────────────────┬──────────────────────────────────┤
│                          │  🔍 Agent Reasoning              │
│  ## Mbappé — Scouting    │  Step 1: search_players()       │
│  Report                  │  → 5 results returned            │
│                          │  Step 2: get_match_timeline()    │
│  [Structured report...]  │  → 7 match records              │
│                          │  Step 3: Web grounding           │
│  Confidence: HIGH ✅     │  → 2 news articles              │
│                          │                                  │
│  ── Similar Players ──   │  Confidence Score: 0.91         │
│  [Card] [Card] [Card]    │  [View full Arize trace →]      │
└──────────────────────────┴──────────────────────────────────┘
```

#### Similar Players section
Below every report, display 5 player cards returned by `search_players`:
```
┌─────────────────┐  ┌─────────────────┐
│ Vinícius Jr.    │  │ Ousmane Dembélé │
│ 🇧🇷 Forward    │  │ 🇫🇷 R. Wing     │
│ WC 2022         │  │ WC 2026         │
│ Similarity: 94% │  │ Similarity: 91% │
└─────────────────┘  └─────────────────┘
```

```bash
pip install streamlit
streamlit run app.py
```

**End of Day 9 checkpoint:** Web app runs locally. All 3 demo queries produce structured reports with similarity cards and Arize trace panel.

---

### Day 10 — Deploy to Cloud Run

**Goal:** Live public URL for submission.

#### Step 1 — Dockerfile for Streamlit app
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
```

#### Step 2 — Deploy MCP server as separate Cloud Run service
```bash
gcloud run deploy scoutiq-mcp \
  --source ./mcp_server \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars MONGODB_URI=$MONGODB_URI,VERTEX_PROJECT=scoutiq-498113
```

#### Step 3 — Deploy frontend
```bash
gcloud run deploy scoutiq-app \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars AGENT_BUILDER_URL=$AGENT_URL,ARIZE_API_KEY=$ARIZE_KEY
```

#### Step 4 — Security gate
Add a simple API key check to prevent public abuse:
```python
# In app.py — only show UI if URL contains ?access=<token>
# or use Cloud Run IAM + Identity-Aware Proxy for production
```

**End of Day 10 checkpoint:** Live URL works. Run 10 real queries end-to-end.

---

### Day 11 — Demo Video + Submission

**3-minute script:**
- 0:00–0:30 — Problem: coaches, journalists, and fans need instant insights during WC 2026
- 0:30–2:30 — Live demo (3 queries):
  1. *"Who plays like Iniesta in the 2026 World Cup?"* → show vector search hitting MongoDB, similarity cards
  2. *"Compare Mbappé's 2026 form to his 2018 peak"* → show cross-year structured comparison
  3. *"Best fantasy midfield picks for this week's knockouts"* → show web grounding + live data
  - During query 3: open the Arize trace panel — show the full reasoning chain + confidence score
- 2:30–3:00 — Impact close: 48 matches, 32 teams, 500+ players, billion viewers

**Submission checklist:**
- [ ] Hosted URL (Cloud Run)
- [ ] GitHub repo (public, MIT license, README with setup instructions)
- [ ] Demo video (~3 min, uploaded to YouTube or Devpost)
- [ ] Track selected: **MongoDB**
- [ ] Devpost form complete

---

## Summary: File Structure

```
scoutiq/
├── plan.md                    ← This file
├── README.md
├── .env                       ← MongoDB URI, Vertex project, API keys
├── requirements.txt
├── extraction.py              ← Day 1: StatsBomb → players_raw.json
├── transform.py               ← Day 2: players_raw.json → 4-collection schema
├── upload.py                  ← Day 2: bulk upsert to MongoDB Atlas
├── ingest_historical.py       ← Day 3: Kaggle 1998-2014 data
├── embed.py                   ← Day 4: Vertex AI embeddings → MongoDB
├── ingest_live.py             ← Day 5: live 2026 match data
├── mcp_server/
│   ├── server.py              ← Day 6: MCP tools (search, lookup, timeline)
│   ├── Dockerfile
│   └── requirements.txt
├── agent/
│   └── system_prompt.txt      ← Day 7: Gemini system prompt
├── app.py                     ← Day 9: Streamlit UI
├── Dockerfile                 ← Day 10: frontend container
├── data/
│   ├── 3.json                 ← 2018 WC match list
│   └── 106.json               ← 2022 WC match list
└── players_raw.json           ← Day 1 output (match-level, flat)
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| WC coverage | 1998–2026 | Full historical context enables style comparison across generations |
| Granularity for vector search | Per-tournament (not per-match) | A player's tournament profile captures style; match-level is too noisy |
| Stats normalisation | Per-90-minute | Ensures fair comparison between players with 1 vs 7 matches |
| Embedding text | Free-text summary | Richer than raw numbers alone; captures position, role, team context |
| Historical data tier | `"summary"` flag | Honest about data quality; agent warns user when using lower-fidelity data |
| Retired players included | Yes | They are the reference anchors for similarity search |
| Two partner tracks | MongoDB + Arize | MongoDB = data backbone; Arize = observability/confidence score; both judged separately = two prize opportunities |
