# ScoutIQ Implementation Guide

**AI Agent for Real-Time Football Scouting & Match Intelligence (2026 World Cup)**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Technology Stack](#technology-stack)
4. [Data Pipeline](#data-pipeline)
5. [MongoDB Schema](#mongodb-schema)
6. [Agent System](#agent-system)
7. [Backend API](#backend-api)
8. [Frontend Application](#frontend-application)
9. [Running Locally](#running-locally)
10. [Deployment](#deployment)

---

## Executive Summary

ScoutIQ is a **multi-step AI scouting agent** that transforms natural language football queries into structured, data-backed scouting reports. Unlike traditional chatbots, ScoutIQ:

- **Acts, doesn't just answer:** Executes multi-step reasoning using MongoDB tools and web search
- **Data-first approach:** Never hallucinates statistics; grounds all claims in real data
- **Confidence scoring:** Marks certainty levels (HIGH/MEDIUM/LOW) based on data sources
- **Real-time capability:** Ingests live 2026 World Cup match data after each matchday

**Example Queries:**
- *"Who plays like Iniesta in the 2026 World Cup?"* → Vector similarity search + report
- *"Compare Mbappé's 2026 form to his 2018 peak"* → Multi-tournament analysis
- *"Who replaced Griezmann as France's creative midfielder?"* → Team roster + style matching

---

## Architecture Overview

### High-Level Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER (React Frontend)                          │
│                       (Cookies for session storage)                      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                         POST /api/chat (SSE)
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                      FastAPI Backend (api.py)                           │
│                   - CORS enabled for React frontend                     │
│                   - Bridges frontend to Agent Builder                   │
│                   - Streams SSE events (thinking, tokens, done)         │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                       Initialize from agent.py
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│              Google ADK Agent Runner (agent.py)                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ root_agent: gemini-2.5-flash                                    │  │
│  │ - Instruction: Elite football scouting directives              │  │
│  │ - Tools: MCP (MongoDB), Google Search, URL Context            │  │
│  │ - Sub-agents: Google Search Agent, URL Context Agent          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────┬──────────────────────┬──────────────────────┬───────────────────┘
         │                      │                      │
    MCP Tools              Google Search           URL Context
         │                      │                      │
         ▼                      ▼                      ▼
    MongoDB                 Google Web         Wikipedia/News Sites
    (Vector Search +
     structured queries)
     
┌────────────────────────────────────────────────────────────────────────┐
│                     MongoDB Atlas (scoutiq database)                   │
│ ┌──────────────────┬──────────────────┬──────────────┬──────────────┐ │
│ │ player_match     │ player_tournament│ players_     │   matches    │ │
│ │    _stats        │    _profiles     │  master      │              │ │
│ │                  │                  │              │              │ │
│ │ Per-match stats  │ Tournament agg.  │ Lifetime ref │ Metadata     │ │
│ │ (timeline)       │ + embeddings     │ + active     │              │ │
│ │                  │ (VECTOR INDEX)   │ status       │              │ │
│ └──────────────────┴──────────────────┴──────────────┴──────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

### System Components

| Component | Role | Technology |
|-----------|------|-----------|
| **Frontend** | User interface, query input, report rendering | React 19 + Vite + Marked |
| **Backend API** | Bridges frontend to agent, streams responses | FastAPI + SSE |
| **Agent** | Multi-step reasoning, tool orchestration | Google ADK + Gemini 2.5 Flash |
| **MCP Server** | MongoDB tools exposing vector search & structured queries | FastMCP + PyMongo |
| **MongoDB Atlas** | Data persistence with vector search indexing | 4 collections, 768-dim embeddings |
| **Data Pipeline** | ETL for 1998–2026 World Cup data | Python scripts (extraction, transform, embed, ingest) |

---

## Technology Stack

### Frontend
- **React 19** — UI components with hooks
- **Vite** — Fast build & dev server
- **Marked** — Markdown rendering for agent reports
- **html2canvas + jsPDF** — PDF export for scouting reports
- **Cookies API** — Client-side conversation persistence (no auth required)

### Backend
- **FastAPI** — REST API with SSE streaming
- **Google ADK** — Agent orchestration framework
- **Gemini 2.5 Flash** — LLM backbone (thinks fast, accurate reasoning)
- **Vertex AI** — Text embeddings (768-dim `text-embedding-004`)
- **PyMongo** — MongoDB client
- **FastMCP** — Model Context Protocol server for tools

### Data & Infrastructure
- **MongoDB Atlas** — 4-collection schema with vector search index
- **StatsBomb** — Event-level 2018 & 2022 World Cup data
- **Kaggle** — Historical 1998–2014 World Cup data
- **football-data.org** — Live 2026 match data
- **Google Cloud** — Vertex AI, Agent Builder, Cloud Run deployment
- **Docker** — Containerization for local & cloud deployment

---

## Data Pipeline

### Overview: From Raw Data to Vector Search

```
PHASE 1: RAW DATA COLLECTION
├─ StatsBomb API (2018 + 2022)
│  └─ Events, lineups, match metadata → players_raw.json
├─ Kaggle CSV (1998–2014)
│  └─ Player names, goals, positions
└─ football-data.org API (2026 live)
   └─ Match scores, squad updates after each matchday

PHASE 2: TRANSFORMATION & SCHEMA
├─ players_raw.json → Normalized per-match stats
├─ Aggregation: Match stats → Tournament profiles
├─ Enrichment: Position resolution, style descriptors
└─ Output: 4 MongoDB collections ready for indexing

PHASE 3: EMBEDDING & INDEXING
├─ Generate embedding text per tournament profile
├─ Call Vertex AI text-embedding-004 in batches
├─ Write embeddings back to MongoDB
└─ Create Atlas Vector Search index (768-dim cosine)

PHASE 4: LIVE INGESTION (Post-matchday)
├─ Poll StatsBomb for new 2026 events
├─ Fall back to football-data.org for immediate updates
├─ Compute per-player stats for live matches
├─ Re-embed affected 2026 profiles
└─ Maintain real-time scouting accuracy
```

### Data Files & Scripts

| Script | Input | Output | Purpose |
|--------|-------|--------|---------|
| `ingestion/extraction.py` | StatsBomb API | `players_raw.json` | Extract 2018 + 2022 stats |
| `transform/transform.py` | `players_raw.json` | MongoDB 4 collections | Normalize & aggregate |
| `ingestion/ingest_historical.py` | `data/kaggle/*.csv` | MongoDB historical tiers | Add 1998–2014 context |
| `embed/embed.py` | MongoDB profiles | Embeddings written back | Generate & store vectors |
| `ingestion/ingest_live.py` | StatsBomb + football-data.org | MongoDB 2026 profiles | Real-time 2026 updates |

---

## MongoDB Schema

### Collection 1: `player_match_stats`

**Granularity:** One document per player per match  
**Purpose:** Raw match-level stats for timeline analysis and form curves  
**Indexes:** `{player_id, tournament_year}`, `{match_date}`, `{nationality}`

```json
{
  "_id": ObjectId,
  "player_id": "cristiano-ronaldo",
  "player_name": "Cristiano Ronaldo",
  "nationality": "Portugal",
  "position": "Forward",
  "team": "Portugal",
  
  "match_id": 3739514,
  "match_date": "2022-11-28",
  "tournament_year": 2022,
  "tournament_label": "FIFA World Cup 2022",
  "competition_stage": "Group Stage",
  "home_team": "Portugal",
  "away_team": "Uruguay",
  
  "goals": 2,
  "shots": 5,
  "shots_on_target": 3,
  "passes": 42,
  "passes_completed": 35,
  "pass_completion_pct": 83.3,
  "dribbles": 4,
  "dribbles_completed": 2,
  "pressures": 12,
  "tackles": 1,
  "minutes_played": 87,
  
  "data_source": "statsbomb",
  "data_tier": "full"
}
```

**Use case:** `get_match_timeline(player_name, tournament_year)` → fetches all match docs → builds form curve

---

### Collection 2: `player_tournament_profiles`

**Granularity:** One document per player per World Cup  
**Purpose:** Aggregated tournament performance with vector embeddings  
**Indexes:** `{player_id, tournament_year}` (unique), `{position}`, `{nationality}`, `{tournament_year}`  
**Special Index:** Atlas Vector Search on `embedding` (768-dim, cosine similarity)

```json
{
  "_id": ObjectId,
  "player_id": "cristiano-ronaldo",
  "player_name": "Cristiano Ronaldo",
  "nationality": "Portugal",
  "position": "Forward",
  "tournament_year": 2022,
  "tournament_label": "FIFA World Cup 2022",
  
  "data_source": "statsbomb",
  "data_tier": "full",
  
  "matches_played": 6,
  "minutes_played": 432,
  "furthest_stage": "Quarter-Finals",
  
  "goals": 3,
  "shots": 15,
  "shots_on_target": 8,
  "passes": 287,
  "passes_completed": 236,
  "pass_completion_pct": 82.2,
  "dribbles_attempted": 16,
  "dribbles_completed": 8,
  "dribble_success_pct": 50.0,
  "pressures": 78,
  "tackles": 6,
  
  "goals_per90": 0.625,
  "shots_per90": 3.125,
  "passes_per90": 59.7,
  "dribbles_per90": 3.33,
  "pressures_per90": 16.25,
  "tackles_per90": 1.25,
  "shot_conversion_pct": 20.0,
  
  "embedding_text": "Cristiano Ronaldo, Portugal Forward. 2022 World Cup: 3 goals in 6 matches (0.625/90)...",
  "embedding": [0.123, 0.456, ..., 0.789],  // 768-dim vector
  
  "created_at": "2022-12-31",
  "updated_at": "2026-06-07"
}
```

**Vector Search Usage:** `search_players("clinical finisher with 6+ pressures per 90", tournament_year=2022)` → returns top 5 similar profiles by cosine distance

---

### Collection 3: `players_master`

**Granularity:** One document per player (lifetime)  
**Purpose:** Canonical player reference across all tournaments  
**Indexes:** `{player_id}` (unique), `{nationality}`, `{positions}`, `{active_at_2026_wc}`

```json
{
  "_id": ObjectId,
  "player_id": "cristiano-ronaldo",
  "player_name": "Cristiano Ronaldo",
  "nationality": "Portugal",
  "positions": ["Forward"],
  
  "data_sources": ["statsbomb", "kaggle"],
  "tournaments_played": [2006, 2010, 2014, 2018, 2022],
  "peak_tournament": 2017,  // inferred; not a WC year, but highest form
  
  "career_wc_goals": 12,
  "career_wc_matches": 30,
  "career_wc_goals_per90": 0.41,
  
  "active_at_2026_wc": false,  // Updated after squad announcements
  "last_tournament_played": 2022,
  "last_updated": "2026-06-07"
}
```

**Queries:**
- *"Did player X play in 2026?"* → Check `active_at_2026_wc`
- *"Who is France's most clinical midfielder in 2026?"* → Filter: `nationality=France`, `active_at_2026_wc=true`, `positions contains Midfielder` → sort by `goals_per90`

---

### Collection 4: `matches`

**Granularity:** One document per match  
**Purpose:** Match metadata for context and aggregation  
**Indexes:** `{tournament_year, competition_stage}`, `{date}`

```json
{
  "_id": ObjectId,
  "match_id": 3739514,
  "date": "2022-11-28",
  "tournament_year": 2022,
  "tournament_label": "FIFA World Cup 2022",
  "competition_stage": "Group Stage",
  
  "home_team": "Portugal",
  "away_team": "Uruguay",
  "home_score": 2,
  "away_score": 0,
  "winner": "Portugal",
  "attendance": 88092,
  
  "venue": "Lusail Stadium",
  "city": "Lusail",
  "country": "Qatar",
  
  "data_source": "statsbomb"
}
```

---

### Schema Relationships Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        players_master (1 doc/player)                │
│                                                                     │
│  player_id ◄──────────────────────────────────────────┐            │
│  player_name                                           │            │
│  nationality                                           │            │
│  active_at_2026_wc                                     │            │
│  career_wc_goals                                       │            │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ (1:many)
                              │ player_id
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
   ┌───────────────────────────┐  ┌───────────────────────────┐
   │ player_tournament_        │  │ player_match_stats        │
   │ profiles                  │  │ (1 doc/player/match)      │
   │ (1 doc/player/WC)         │  │                           │
   │                           │  │ Used for timeline &       │
   │ + EMBEDDINGS (768-dim)    │  │ form curve analysis       │
   │ + Per-90 stats            │  │                           │
   │ + Playing style text      │  │ Raw event-level stats     │
   └───────────────────────────┘  └───────────────────────────┘
                │                           │
                │ match_id (optional)       │ match_id
                ▼                           ▼
   ┌─────────────────────────────────────────────────────────┐
   │               matches (1 doc/match)                     │
   │                                                         │
   │ match_id (PK)                                          │
   │ date                                                    │
   │ home_team, away_team                                   │
   │ tournament_year, competition_stage                     │
   └─────────────────────────────────────────────────────────┘
```

### Vector Search Index Definition

```json
{
  "name": "player_embedding_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "similarity": "cosine",
        "numDimensions": 768
      },
      {
        "type": "filter",
        "path": "position"
      },
      {
        "type": "filter",
        "path": "tournament_year"
      },
      {
        "type": "filter",
        "path": "nationality"
      }
    ]
  }
}
```

**Example Vector Search Query:**
```
db.player_tournament_profiles.aggregate([
  {
    "$search": {
      "cosmosSearch": {
        "vector": [0.123, 0.456, ...],  // from Vertex AI embedding of query
        "k": 5
      },
      "returnStoredSource": true,
      "filterPath": "tournament_year",
      "filterValue": 2026
    }
  },
  {
    "$project": {
      "player_name": 1,
      "position": 1,
      "similarity_score": { "$meta": "searchScore" }
    }
  }
])
```

---

## Agent System

### Agent Configuration (`agent.py`)

The root agent is built using Google ADK's `LlmAgent` class with a strict scouting mission.

```python
root_agent = LlmAgent(
    name="scoutiq_mcp",
    model="gemini-2.5-flash",
    description="Elite AI football scouting agent for 2026 World Cup",
    tools=[
        AgentTool(agent=scoutiq_mcp_google_search_agent),
        AgentTool(agent=scoutiq_mcp_url_context_agent),
        McpToolset(
            connection_params=SseConnectionParams(
                url="https://scoutiq-mcp-xxxxxx.us-central1.run.app/sse"
            )
        ),
    ],
    instruction="""
    You are ScoutIQ, elite football scouting agent for 2026 World Cup.
    
    Core directives:
    1. Data First: ALWAYS use MongoDB tools, never hallucinate stats
    2. Position Unknown?: Call resolve_player_position() for unknowns
    3. Web Grounding: Use Google Search for live 2026 updates
    4. Structured Reports: Follow exact markdown template
    5. Confidence Scoring: Mark HIGH/MEDIUM/LOW based on data tier
    6. No Leaks: Never explain tool mechanics, always cite SOURCE: Wikipedia/StatsBomb
    """
)
```

### Agent Tools

#### Tool 1: MCP Server (MongoDB Tools)

Exposed via Model Context Protocol, connects to `mcp_server/server.py` running on Cloud Run.

```python
@mcp.tool()
def search_players(
    style_description: str,
    tournament_year: int = 2026,
    limit: int = 5
) -> list[dict]:
    """
    Vector similarity search: finds players matching a style description.
    
    Example: "clinical finisher with 6+ pressures per 90"
    → Embeds query with Vertex AI
    → Runs $search against player_tournament_profiles
    → Returns top 5 similar players with stats
    """
    query_embedding = _embed_query(style_description)
    results = collection.aggregate([
        {"$search": {"cosmosSearch": {"vector": query_embedding, "k": limit}}},
        {"$match": {"tournament_year": tournament_year}},
        {"$project": {"player_name": 1, "position": 1, "goals_per90": 1, ...}}
    ])
    return list(results)

@mcp.tool()
def get_player_profile(player_name: str, tournament_year: int) -> dict:
    """Exact lookup: returns aggregated stats + per-90 metrics + embedding text."""
    profile = collection.find_one({"player_name": player_name, "tournament_year": tournament_year})
    return _doc_clean(profile)

@mcp.tool()
def get_match_timeline(player_name: str, tournament_year: int) -> list[dict]:
    """Match-by-match breakdown: for form curve & tactical evolution analysis."""
    matches = list(
        collection.find(
            {"player_name": player_name, "tournament_year": tournament_year},
            sort=[("match_date", 1)]
        )
    )
    return matches

@mcp.tool()
def get_team_players(nationality: str, tournament_year: int, position: str = None) -> list[dict]:
    """Roster lookup: find all players for a nation in a given WC."""
    query = {"nationality": nationality, "tournament_year": tournament_year}
    if position:
        query["position"] = position
    return list(collection.find(query))

@mcp.tool()
def resolve_player_position(player_name: str) -> dict:
    """Position resolution: looks up position from football-data.org + Wikipedia."""
    # Tries multiple sources to resolve "Unknown" positions
    return {"player_name": player_name, "position": "resolved_position"}
```

#### Tool 2: Google Search Agent

Sub-agent specialized in web search for live 2026 updates.

```python
scoutiq_mcp_google_search_agent = LlmAgent(
    name="scoutiq_mcp_google_search_agent",
    model="gemini-2.5-flash",
    tools=[GoogleSearchTool()],
    instruction="Use GoogleSearchTool to find current info on injuries, squad changes, form."
)
```

#### Tool 3: URL Context Agent

Sub-agent for fetching Wikipedia/news articles.

```python
scoutiq_mcp_url_context_agent = LlmAgent(
    name="scoutiq_mcp_url_context_agent",
    model="gemini-2.5-flash",
    tools=[url_context],
    instruction="Use UrlContextTool to retrieve detailed content from web pages."
)
```

### Agent Execution Flow

```
User Query: "Who plays like Iniesta in 2026?"
     │
     ▼
┌────────────────────────────────────────┐
│ APIFrontend sends to /api/chat         │
│ { query, mode, session_id }            │
└────────────┬──────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ api.py: _get_agent_and_runner()        │
│ - Imports root_agent from agent.py     │
│ - Creates ADK Runner instance          │
│ - Initializes InMemorySessionService   │
└────────────┬──────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ runner.run_async(message)              │
│ - Sends query to Gemini 2.5 Flash      │
│ - Streams events back to API           │
└────────────┬──────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ Agent Reasoning Loop:                  │
│                                        │
│ 1. Interpret: "find Iniesta-like"      │
│    → Plan: need style descriptors      │
│                                        │
│ 2. Call Tool: search_players(          │
│      "creative playmaker, vision"      │
│    ) → vector search                   │
│                                        │
│ 3. Tool Response: Top 5 similar        │
│    → Yields SSE event: type=similar    │
│                                        │
│ 4. Synthesize: Write report            │
│    → Streams tokens (type=token)       │
│                                        │
│ 5. Final: Send confidence score        │
│    → Yields type=done                  │
└────────────┬──────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ api.py: stream_agent_response()        │
│ - Intercepts events from runner        │
│ - Converts to SSE format               │
│ - Sends to React frontend              │
└────────────┬──────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ Frontend (React):                      │
│ - useAgent hook receives SSE           │
│ - Updates loading state                │
│ - Renders thinking steps               │
│ - Displays similar players             │
│ - Renders final report (markdown)      │
│ - Saves to cookie-based history        │
└────────────────────────────────────────┘
```

### Report Template (Generated by Agent)

Every agent response follows this structure (enforced in instruction):

```markdown
## [Player Name] — Scouting Report

**Position:** [position] | **Nationality:** [nationality] | **Active 2026:** [yes/no]

### Key Tournament Stats
| Metric | Value | Per 90 |
|--------|-------|--------|
| Matches Played | X | — |
| Goals | X | X.XX |
| Pass Completion % | X% | — |
| Dribbles Completed | X | X.XX |
| Pressures | X | X.XX |

### Playing Style
[2–3 sentences from per-90 stats]

### Historical Arc
[Multi-tournament evolution if available]

### Similarity Matches (if search query)
1. **[Player]** — [Nationality], [Position] — Similarity: 94%
2. [...]

### Form Rating: [1–10]

### Tactical Recommendation
[One actionable insight for coaches/scouts]

### Confidence: [🟢 HIGH | 🟡 MEDIUM | 🔴 LOW]
```

---

## Backend API

### FastAPI Setup (`api.py`)

```python
app = FastAPI(title="ScoutIQ API", version="1.0.0")

# CORS for React frontend
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# Credential resolution (supports both file path + base64 for Cloud Run)
_creds_b64 = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "")
if _creds_b64:
    # Decode from Coolify secrets
    creds_json = base64.b64decode(_creds_b64)
    Path("/tmp/gcp_credentials.json").write_text(creds_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/gcp_credentials.json"
```

### Endpoints

#### `POST /api/chat`

**Request:**
```json
{
  "query": "Who plays like Iniesta in 2026?",
  "mode": "Full Report",
  "session_id": "12345-67890"
}
```

**Response:** Server-Sent Events (SSE) stream

```
data: {"type": "thinking", "step": "Searching player database...", "tool": "search_players", "status": "running"}

data: {"type": "thinking", "step": "Searching player database...", "tool": "search_players", "status": "done", "result_count": 5}

data: {"type": "similar", "players": [{"player_name": "...", "position": "...", ...}, ...]}

data: {"type": "token", "content": "## Iniesta-Like Players in 2026\n\n"}

data: {"type": "token", "content": "Based on vector similarity and playing style..."}

data: {"type": "done", "confidence": "HIGH", "report": "...full markdown report..."}

data: [DONE]
```

#### `GET /api/health`

Simple health check for Kubernetes probes.

```json
{"status": "ok", "service": "ScoutIQ API"}
```

#### `GET /` (Production)

Serves the built React app from `app/dist/` (mounted as static files).

### Streaming Architecture

```python
async def stream_agent_response(query, mode, session_id) -> AsyncGenerator[str, None]:
    # Initialize ADK runner from agent.py
    runner, session_service, agent = _get_agent_and_runner()
    
    # Create message
    message = genai_types.Content(role="user", parts=[genai_types.Part(text=query)])
    
    # Stream events from runner
    async for event in runner.run_async(...):
        # Extract function calls (tool invocations)
        if hasattr(event, 'content'):
            for part in event.content.parts:
                if hasattr(part, 'function_call'):
                    # Emit: {"type": "thinking", "status": "running"}
                    yield sse_event({"type": "thinking", ...})
                
                if hasattr(part, 'function_response'):
                    # Emit: {"type": "thinking", "status": "done"}
                    yield sse_event({"type": "thinking", ...})
                
                if hasattr(part, 'text') and event.author == runner.agent.name:
                    # Emit: {"type": "token", "content": "..."}
                    yield sse_event({"type": "token", ...})
    
    # Final report
    yield sse_event({"type": "done", "confidence": "HIGH", "report": "..."})
    yield sse_done()
```

---

## Frontend Application

### Architecture

```
app/ (React + Vite)
├── src/
│   ├── App.jsx              (Main orchestrator)
│   ├── App.css
│   │
│   ├── components/
│   │   ├── QueryHome.jsx       (Homepage, query input)
│   │   ├── ChatView.jsx        (Chat display, streaming report)
│   │   ├── HistoryView.jsx     (Saved conversations)
│   │   ├── About.jsx           (Project info)
│   │   ├── Sidebar.jsx         (Navigation)
│   │   ├── MobileBottomNav.jsx (Mobile nav)
│   │   ├── LoadingIndicator.jsx (Animated spinner)
│   │   ├── ScoutingReport.jsx  (Markdown report renderer)
│   │   └── SimilarPlayers.jsx  (Player cards)
│   │
│   ├── hooks/
│   │   ├── useAgent.js      (Agent SSE streaming)
│   │   └── useConversations.js (Cookie-based history)
│   │
│   ├── utils/
│   │   └── pdfGenerator.js  (html2canvas + jsPDF export)
│   │
│   └── styles/
│       └── tokens.css       (Design system variables)
│
├── index.html
├── vite.config.js
└── package.json
```

### Key Features

#### 1. Query Interface (`QueryHome`)
- Text input for natural language queries
- Mode selector (Full Report / Comparison / Recent Form)
- Submit button with loading state
- Responsive grid layout

#### 2. Chat Interface (`ChatView`)
- Displays user messages and agent thinking steps
- Real-time streaming: shows "Searching...", "Fetching profile...", etc.
- Similar players section (player cards with stats)
- Markdown-rendered scouting report
- PDF export button
- New chat / cancel query options

#### 3. Streaming Visualization (`LoadingIndicator`)
- Animated "Scouting..." spinner during agent reasoning
- Shows current tool being used
- Smooth transitions between thinking steps

#### 4. Report Rendering (`ScoutingReport`)
- Markdown → HTML using `marked` library
- Tables for tournament stats
- Confidence badge (🟢 HIGH / 🟡 MEDIUM / 🔴 LOW)
- Player card links

#### 5. Conversation History (`HistoryView`)
- Saves to browser cookies (no server-side auth)
- Each conversation: timestamp, query, mode, full response
- Delete single or clear all
- Click to replay conversation

#### 6. Agent Integration (`useAgent` hook)

```javascript
// Streaming from /api/chat endpoint
const response = await fetch(`${API_URL}/api/chat`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query, mode, session_id }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (!done) {
  const { value, done: finished } = await reader.read();
  const chunk = decoder.decode(value);
  
  // Parse SSE: "data: {...}\n\n"
  const lines = chunk.split("\n");
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const event = JSON.parse(line.substring(6));
      
      if (event.type === "thinking") {
        // Update loading state with tool name
        setReasoningSteps(prev => [...prev, event]);
      }
      if (event.type === "token") {
        // Append to streamed report
        setStreamedReport(prev => prev + event.content);
      }
      if (event.type === "similar") {
        // Display similar players
        setSimilarPlayers(event.players);
      }
      if (event.type === "done") {
        // Final report + confidence
        setReasoningSteps([]);
        setIsLoading(false);
      }
    }
  }
}
```

#### 7. Conversation Storage (`useConversations` hook)

```javascript
// Cookie-based (browser localStorage alternative)
const conversations = JSON.parse(
  document.cookie.match(/scoutiq_conversations=([^;]*)/)?.[1] || "[]"
);

// Add conversation
conversations.push({
  id: generateId(),
  timestamp: new Date().toISOString(),
  query: "Who plays like Iniesta in 2026?",
  mode: "Full Report",
  response: {
    report: "...full markdown...",
    reasoning_steps: [...],
    similar_players: [...],
    confidence: "HIGH",
  },
});

// Save to cookie
document.cookie = `scoutiq_conversations=${JSON.stringify(conversations)}; max-age=${60*60*24*365}`;
```

### Design System

**tokens.css** defines:
- Color palette: `--color-bg-page`, `--color-text-body`, `--color-text-accent`, etc.
- Typography: `--font-primary` (Inter), line heights, font sizes
- Spacing: `--space-xs`, `--space-sm`, `--space-md`, etc.
- Shadows: `--shadow-sm`, `--shadow-md`
- Transitions: Smooth 200–300ms for interactions

**CSS Features:**
- Smooth button click animations (scale + shadow)
- Loading spinner (rotating loader icon)
- Responsive grid (mobile sidebar collapses)
- Markdown table styling
- Confidence badge colors (green/yellow/red)
- PDF export button styling

---

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+ (for npm)
- MongoDB Atlas account (free tier OK)
- Google Cloud account (GCP) with:
  - Vertex AI API enabled
  - Service account key (for local dev)

### Step 1: Clone & Setup Environment

```bash
git clone https://github.com/samitochi04/scoutiq.git
cd scoutiq

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate (Windows)

# Install Python dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### Step 2: Configure `.env`

```bash
# MongoDB
MONGODB_CLUSTER_CONNECTION=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority

# Google Cloud
GCP_PROJECT_ID=your-gcp-project
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Optional: football-data.org for live 2026 data
FOOTBALL_DATA_API_KEY=your-api-key
```

### Step 3: Run Data Pipeline (One-time Setup)

```bash
# 1. Extract 2018 + 2022 data from StatsBomb
python ingestion/extraction.py

# 2. Transform into 4-collection schema
python transform/transform.py

# 3. Ingest historical 1998–2014 data (requires data/kaggle/*.csv)
python ingestion/ingest_historical.py

# 4. Generate embeddings (calls Vertex AI)
python embed/embed.py

# 5. (Optional) Ingest live 2026 data
python ingestion/ingest_live.py
```

### Step 4: Start MCP Server

```bash
# Terminal 1: MCP server (exposes MongoDB tools)
python -m uvicorn mcp_server.asgi:app --host 0.0.0.0 --port 8080
```

### Step 5: Start Backend API

```bash
# Terminal 2: FastAPI backend
python -m uvicorn api:app --host 0.0.0.0 --port 8001 --reload
```

### Step 6: Start Frontend

```bash
# Terminal 3: React + Vite dev server
cd app
npm install
npm run dev
```

### Step 7: Open Browser

Navigate to `http://localhost:5173` (Vite default port)

---

### Local Development Notes

1. **Hot reload:** Frontend: Vite auto-reloads; Backend: `--reload` flag
2. **Debugging:** Check browser console for frontend errors, terminal output for API errors
3. **CORS:** Already enabled in api.py for `http://localhost:*`
4. **Session storage:** Conversations saved to browser cookies; no server-side DB
5. **Logs:** API logs show agent tool calls, stream events, errors

---

## Deployment

### Production Architecture

```
┌─────────────────┐
│  Cloud CDN      │
│  (React build)  │
└────────┬────────┘
         │
┌────────▼────────────────────────────┐
│  Cloud Load Balancer                │
│  (SSL/TLS termination)              │
└────────┬────────────────────────────┘
         │
    ┌────┴────┐
    │          │
    ▼          ▼
┌────────────────────┐  ┌────────────────────┐
│  Cloud Run         │  │  Cloud Run         │
│  (API Container)   │  │  (MCP Server)      │
│  - api.py          │  │  - mcp_server/     │
│  - agent.py        │  │  - server.py       │
│  - 2–4 replicas    │  │  - 1–2 replicas    │
└────────┬───────────┘  └────────┬───────────┘
         │                       │
         └───────────┬───────────┘
                     │
              ┌──────▼──────────┐
              │ MongoDB Atlas   │
              │ (scoutiq DB)    │
              │ 4 collections   │
              │ Vector Search   │
              │ Index           │
              └─────────────────┘
```

### Docker Deployment

**Root `Dockerfile` (Backend API):**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY api.py agent/ embed/ ingestion/ transform/ .
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`app/Dockerfile` (Frontend):**
```dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine
EXPOSE 3000
COPY --from=build /app/dist /app/dist
CMD ["npx", "serve", "-s", "/app/dist", "-l", "3000"]
```

**`docker-compose.yml`:**
```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      MONGODB_CLUSTER_CONNECTION: ${MONGODB_CLUSTER_CONNECTION}
      GCP_PROJECT_ID: ${GCP_PROJECT_ID}
      GOOGLE_APPLICATION_CREDENTIALS: /tmp/gcp_credentials.json
  
  frontend:
    build: ./app
    ports:
      - "3000:3000"
    depends_on:
      - api
```

### Cloud Run Deployment

```bash
# Deploy API
gcloud run deploy scoutiq-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars MONGODB_CLUSTER_CONNECTION=${MONGODB_CLUSTER_CONNECTION},GCP_PROJECT_ID=aideplus

# Deploy MCP Server
gcloud run deploy scoutiq-mcp \
  --source . \
  --entry-point mcp_server.asgi:app \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Environment Variables (Cloud Run)

Store sensitive values in Coolify secrets or GCP Secret Manager:

```
GCP_SERVICE_ACCOUNT_JSON=<base64-encoded JSON>
MONGODB_CLUSTER_CONNECTION=<connection string>
GCP_PROJECT_ID=aideplus
GCP_REGION=us-central1
FOOTBALL_DATA_API_KEY=<api key>
```

---

## Key Design Decisions

### Why This Architecture?

| Decision | Rationale |
|----------|-----------|
| **Agent-centric** | Enables multi-step reasoning, tool composition, confidence scoring |
| **MongoDB Vector Search** | Native cosine similarity for 768-dim embeddings; no external index |
| **Per-90 normalization** | Allows fair comparison of players with different tournament minutes |
| **Cookie-based sessions** | No server-side auth needed; users own their conversation history |
| **SSE streaming** | Real-time visibility into agent thinking; better UX than blocking API call |
| **MCP tools** | Standardized tool interface; easy to add new data sources |
| **Separate collections** | Match-level (timeline) vs. aggregated (search) → different access patterns |

### Data Tier Strategy

- **Full (StatsBomb 2018 + 2022):** Event-level stats → highest confidence
- **Medium (football-data.org 2026):** Match scores + aggregates → medium confidence
- **Summary (Kaggle 1998–2014):** Total goals + positions → low confidence

Agent marks confidence based on which tier the player's data comes from.

### Embedding Strategy

Embeddings capture *playing style* from per-90 stats:
- Clinical finisher → high goals_per90, shot_conversion_pct
- Creative midfielder → high pass_completion_pct, low pressures (playmaking vs. chasing)
- Defensive midfielder → high tackles, pressures

Vector search finds similar *styles*, not just similar names.

---

## Troubleshooting

### Agent initialization fails

**Error:** `Failed to import agent.py`

**Solution:**
1. Ensure `agent/agent.py` exists and is importable
2. Check `GOOGLE_APPLICATION_CREDENTIALS` is set
3. Verify `google-adk` is installed: `pip install google-adk`

### MongoDB connection fails

**Error:** `MONGODB_CLUSTER_CONNECTION not set`

**Solution:** Add to `.env`:
```
MONGODB_CLUSTER_CONNECTION=mongodb+srv://user:pass@cluster.xyz.mongodb.net/scoutiq?retryWrites=true&w=majority
```

### Frontend can't reach API

**Error:** CORS error or `fetch failed`

**Solution:**
1. Check API is running: `curl http://localhost:8001/api/health`
2. Check `VITE_API_URL` in frontend `.env.development`:
   ```
   VITE_API_URL=http://localhost:8001
   ```
3. Verify CORS is enabled in `api.py` (it is by default)

### Vector search returns no results

**Error:** No players found matching query

**Possible causes:**
1. Embeddings not generated: Run `python embed/embed.py`
2. Vector search index not created: Check MongoDB Atlas → Collections → Indexes
3. Empty profiles collection: Run full data pipeline

---

## Next Steps & Future Improvements

- [ ] Real-time 2026 match data ingestion (after tournament starts)
- [ ] Fantasy football integration (value predictions)
- [ ] Transfer market gossip grounding (news search)
- [ ] Multi-language support (agent speaks multiple languages)
- [ ] Advanced analytics: Expected Goals (xG), pressure maps
- [ ] Authentication & team workspaces (for professional scouts)
- [ ] A/B testing agent prompts for better recommendations

---

## License

MIT — Free for commercial use. See [LICENSE](LICENSE).

---

**Questions?** Check [README.md](README.md) for quick start, or review [plan.md](test_to_understand_code/plan.md) for vision.
