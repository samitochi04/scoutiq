# ScoutIQ ⚽
**AI Agent for Real-Time Football Scouting & Match Intelligence — 2026 World Cup**

> [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com) — **MongoDB Track**

ScoutIQ is a multi-step AI scouting agent that *acts*, not just answers. Given a query like *"Who plays like Iniesta in the 2026 World Cup?"* or *"Compare Mbappé's 2026 form to his 2018 peak"*, the agent executes a full reasoning loop: queries MongoDB Atlas Vector Search for historical player data, grounds itself in live 2026 match data, and returns a structured scouting report with a confidence score.

**Hosted app:** *(Cloud Run URL — added at submission)*
**Demo video:** *(YouTube — added at submission)*

### Links
- Hackathon: https://rapid-agent.devpost.com
- ScoutIQ MongoDB Atlas: https://cloud.mongodb.com/v2/6a1d7d2c514928562d58f94f#/overview
- ScoutIQ GCP project: https://console.cloud.google.com/agent-platform/overview?project=aideplus

---

## Quick Start

### Prerequisites
- Python 3.11+
- MongoDB Atlas account (free tier works)
- Google Cloud account with Vertex AI and Agent Builder APIs enabled

### Installation

```bash
git clone https://github.com/<your-handle>/scoutiq.git
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

### Run the web app (local)

```bash
streamlit run app/app.py
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM / Agent | Gemini 2.5 Flash via Google Cloud Agent Builder |
| Embeddings | Vertex AI `text-embedding-004` (768 dims) |
| Database | MongoDB Atlas — Vector Search + 4 collections |
| MCP Server | Python + FastAPI — 4 tools |
| Observability | Arize Phoenix — traces + groundedness score |
| Frontend | Streamlit on Google Cloud Run |

---

## Project Structure

```
scoutiq/
├── LICENSE                      MIT — OSI-approved, commercial use allowed
├── README.md                    This file
├── plan.md                      Full 11-day build plan (data science detail)
├── requirements.txt
├── .env.example                 Template — copy to .env, never commit .env
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
│   └── transform.py             Aggregates to tournament profiles, upserts (Day 2)
│
├── embed/                       Vertex AI embedding generation
│   └── embed.py                 Embeds player tournament profiles (Day 4)
│
├── mcp_server/                  MCP server — tools exposed to Agent Builder
│   ├── server.py                search_players, get_player_profile,
│   │                            get_match_timeline, get_team_players
│   └── Dockerfile
│
├── agent/
│   └── system_prompt.txt        Gemini system prompt (Day 7)
│
└── app/                         Streamlit web UI
    ├── app.py                   Main frontend (Day 9)
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

See [plan.md](plan.md) for full schema definitions, per-90 normalisation logic, and embedding text strategy.

---

## Data Coverage

| WC Years | Source | Tier | Stats available |
|---|---|---|---|
| 2018, 2022 | [StatsBomb open data](https://github.com/statsbomb/open-data) | `full` | shots, passes, dribbles, pressures, tackles |
| 1998–2014 | [Kaggle FIFA World Cup](https://www.kaggle.com/datasets/abecklas/fifa-world-cup) | `summary` | goals, assists, matches, position |
| 2026 (live) | StatsBomb live + football-data.org fallback | `live` | Updated within 48h of each match |

---

## Hackathon Compliance

> Rules summary — always check [rules.txt](rules.txt) for the authoritative text.

### Track & prize
- Submitted to the **MongoDB track** only.
- One project = one track. *"Each Submission must be unique and substantially different"* — the same project cannot be entered in multiple tracks.
- Deadline: **June 11, 2026 at 2:00 PM PT**

### Required technologies
- [x] Google Cloud **Agent Builder** — orchestration
- [x] **Gemini** — the AI model
- [x] **MongoDB MCP server** — partner integration (mandatory for MongoDB track)
- [x] Hosted on **Google Cloud Run** — public URL required for judging

### AI tools — strict rule
> *"Projects are required to utilize Google Cloud artificial intelligence tools... All other artificial intelligence tools are not permitted."*

**Only Google Cloud AI is used:**
- Gemini 2.5 Flash (LLM)
- Vertex AI `text-embedding-004` (embeddings)
- Agent Builder built-in Google Search grounding

**Not used:** OpenAI, Anthropic, Cohere, Hugging Face inference, or any non-Google AI service. Violating this rule = disqualification.

### Competing services rule
> *"The use of other services that directly compete with... the Partner whose track you've selected is not permitted."*

MongoDB track → no competing databases (Firebase, DynamoDB, PostgreSQL, etc.).
**GitHub is permitted** — GitHub competes with GitLab (a different partner track), not with MongoDB.

### Third-party data & APIs
- **StatsBomb open data** — licensed under [StatsBomb Open Data Agreement](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf)
- **Kaggle FIFA dataset** — CC0 public domain
- **football-data.org** — free tier, non-commercial license
- **Arize Phoenix** — Arize is a listed partner; their SDK is permitted in any track

### Open source requirement
Repository must be public with a detectable OSI-approved license visible in the GitHub About section. This repo uses **MIT** — commercial use permitted, as required by the rules.

### Submission checklist (before June 11)
- [ ] Hosted URL on Google Cloud Run
- [ ] Public GitHub repo — MIT license visible in About section
- [ ] Demo video ≤ 3 min — YouTube or Vimeo, in English
- [ ] Devpost form complete — MongoDB track selected
- [ ] Submit ≥ 2 hours before deadline

---

## License

[MIT](LICENSE) — OSI-approved, free for commercial use. 