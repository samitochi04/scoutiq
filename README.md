# ScoutIQ ⚽
**AI Agent for Real-Time Football Scouting & Match Intelligence 2026 World Cup**

ScoutIQ is a multi-step AI scouting agent that *acts*, not just answers. Given a query like *"Who plays like Iniesta in the 2026 World Cup?"* or *"Compare Mbappé's 2026 form to his 2018 peak"*, the agent executes a full reasoning loop: queries MongoDB Atlas Vector Search for historical player data, grounds itself in live 2026 match data, and returns a structured scouting report with a confidence score.

---

## Quick Start

### Prerequisites
- Python 3.11+
- MongoDB Atlas account (free tier works)
- Google Cloud account with Vertex AI and Agent Builder APIs enabled

### Installation

```bash
git clone https://github.com/samitochi04/scoutiq.git
cd scoutiq
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your MongoDB and GCP credentials
```
**OR**

```bash
# Using Docker
docker-compose up -d
```

### Run the data pipeline

```bash
# Step 1 — Extract 2018 + 2022 WC player stats from StatsBomb
python ingestion/extraction.py

# Step 2 — Transform raw data into 4-collection schema + upload to Atlas
python transform/transform.py

# Step 3 — Ingest historical WC data (1998–2014) from Kaggle
python ingestion/ingest_historical.py

# Step 4 — Generate Vertex AI embeddings for all tournament profiles
python embed/embed.py

# Step 5 — Ingest live 2026 data (run after each matchday)
python ingestion/ingest_live.py
```

### Run the MCP server (local)

```bash
cd mcp_server
uvicorn server:app --host 0.0.0.0 --port 8080
```
**Note:**
The project uses Google Agent Builder and MCP tools, so you'll need to configure a Google Cloud account and deploy the MCP server to Cloud Run.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM / Agent | Gemini 2.5 Flash via Google Cloud Agent Builder |
| Embeddings | Vertex AI `text-embedding-004` (768 dims) |
| Database | MongoDB Atlas - Vector Search + 4 collections |
| MCP Server | Python (Pymongo) + FastAPI - 4 tools |
| Frontend | React + Vite |

---

## Project Structure

```
scoutiq/
├── LICENSE                      MIT — OSI-approved,
├── README.md                    This file
├── requirements.txt
├── .env.example                 credentials
│
├── data/                        StatsBomb match lists (cached locally)
│   ├── 3.json                   2018 WC match metadata
│   └── 106.json                 2022 WC match metadata
│
├── ingestion/                   Data ingestion
│   ├── extraction.py            StatsBomb → players_raw.json (WC 2018 + 2022)
│   ├── ingest_historical.py     Kaggle WC 1998–2014 data (Day 3)
│   └── ingest_live.py           Live 2026 match ingestion (Day 5)
│
├── transform/                   Schema transformation + MongoDB upload
│   └── transform.py             Aggregates to tournament profiles
│
├── embed/                       Vertex AI embedding generation
│   └── embed.py                 Embeds player tournament profiles
│
├── mcp_server/                  MCP server - tools exposed to Agent Builder
│   ├── server.py                search_players, get_player_profile,
│   │                            get_match_timeline, get_team_players
│   
│
├── agent/
│   └── agent.py                 AI Agent
│
├── api.py                       backend (for frontend)
│
├── Dockerfile
├── docker-compose.yml 
│
└── app/                         web UI
    ├── vite.config.js           Main frontend
    └── Dockerfile
```

---

## MongoDB Schema (4 collections)

| Collection | Granularity | Purpose |
|---|---|---|
| `player_match_stats` | 1 doc per player per match | Timeline, form curves |
| `player_tournament_profiles` | 1 doc per player per WC + embedding | Vector search target |
| `players_master` | 1 doc per player (lifetime) | Career reference, `active_at_2026_wc` |
| `matches` | 1 doc per match | Match metadata |

See [project.md](project.md) for full schema definitions, per-90 normalisation logic, and embedding text strategy.

---

## Data Coverage

| WC Years | Source | Tier | Stats available |
|---|---|---|---|
| 2018, 2022 | [StatsBomb open data](https://github.com/statsbomb/open-data) | `full` | shots, passes, dribbles, pressures, tackles |
| 1998–2014 | [Kaggle FIFA World Cup](https://www.kaggle.com/datasets/abecklas/fifa-world-cup) | `summary` | goals, assists, matches, position |
| 2026 (live) | StatsBomb live + football-data.org fallback | `live` | Updated within 48h of each match |

---

## License

[MIT](LICENSE) — OSI-approved, free for commercial use. 