"""
test_search.py — Day 4 smoke tests
Runs vector search queries against the Atlas Vector Search index to verify
the embedding pipeline is working correctly.

IMPORTANT: Run this AFTER the Atlas index status shows ACTIVE (usually 1–2 min
           after embed.py completes).

Run: python embed/test_search.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

MONGO_URI = os.getenv("MONGODB_CLUSTER_CONNECTION")
GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "aideplus")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
GOOGLE_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

INDEX_NAME = "player_embedding_index"
EMBED_DIM = 768


def resolve_credentials() -> None:
    if not GOOGLE_CREDS:
        return
    path = Path(GOOGLE_CREDS)
    if not path.is_absolute():
        path = ROOT / GOOGLE_CREDS.lstrip("./\\")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)


def get_query_embedding(model, text: str) -> list[float]:
    from vertexai.language_models import TextEmbeddingInput
    result = model.get_embeddings([TextEmbeddingInput(text, "RETRIEVAL_QUERY")], output_dimensionality=EMBED_DIM)
    return result[0].values


def search_similar_players(
    col,
    model,
    query_text: str,
    tournament_year: int | None = None,
    position: str | None = None,
    nationality: str | None = None,
    limit: int = 5,
) -> list[dict]:
    query_vec = get_query_embedding(model, query_text)

    filter_doc: dict = {}
    if tournament_year is not None:
        filter_doc["tournament_year"] = tournament_year
    if position is not None:
        filter_doc["position"] = position
    if nationality is not None:
        filter_doc["nationality"] = nationality

    vector_search: dict = {
        "index": INDEX_NAME,
        "path": "embedding",
        "queryVector": query_vec,
        "numCandidates": 150,
        "limit": limit,
    }
    if filter_doc:
        vector_search["filter"] = filter_doc

    pipeline = [
        {"$vectorSearch": vector_search},
        {
            "$project": {
                "_id": 0,
                "player_name": 1,
                "nationality": 1,
                "position": 1,
                "tournament_year": 1,
                "goals": 1,
                "goals_per90": 1,
                "pass_completion_pct": 1,
                "dribbles_per90": 1,
                "furthest_stage": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(col.aggregate(pipeline))


def print_results(results: list[dict], query: str) -> None:
    print(f"\n  Query: \"{query}\"")
    print(f"  {'Player':<35} {'Nat':<6} {'Pos':<28} {'Year':<6} {'Score':.5}")
    print("  " + "-" * 90)
    for r in results:
        print(
            f"  {r.get('player_name', '?'):<35} "
            f"{r.get('nationality', '?'):<6} "
            f"{r.get('position', '?'):<28} "
            f"{r.get('tournament_year', '?'):<6} "
            f"{r.get('score', 0):.4f}"
        )


def main() -> None:
    if not MONGO_URI:
        sys.exit("ERROR: MONGODB_CLUSTER_CONNECTION not set in .env")

    resolve_credentials()

    print("=" * 60)
    print("ScoutIQ Day 4 — Vector Search Smoke Tests")
    print("=" * 60)

    try:
        import vertexai
        from vertexai.language_models import TextEmbeddingModel
    except ImportError:
        sys.exit("ERROR: google-cloud-aiplatform not installed.")

    print(f"\nLoading model (project={GCP_PROJECT}) ...")
    vertexai.init(project=GCP_PROJECT, location=GCP_REGION)
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    print("  Model ready")

    db = MongoClient(MONGO_URI)["scoutiq"]
    col = db["player_tournament_profiles"]

    # --- Test 1: classic playmaker archetype (all years) ---
    results = search_similar_players(
        col, model,
        "deep playmaker, excellent vision, high pass completion, calm under pressure",
    )
    print_results(results, "deep playmaker, excellent vision, high pass completion")

    # --- Test 2: fast pacey winger (all years) ---
    results = search_similar_players(
        col, model,
        "fast pacey winger, strong dribbler, high shot volume",
    )
    print_results(results, "fast pacey winger, strong dribbler, high shot volume")

    # --- Test 3: winger filtered to 2022 ---
    results = search_similar_players(
        col, model,
        "fast pacey winger, strong dribbler, high shot volume",
        tournament_year=2022,
    )
    print_results(results, "fast pacey winger (2022 only)")

    # --- Test 4: dominant striker ---
    results = search_similar_players(
        col, model,
        "dominant striker, aerial ability, holds up play, clinical finisher",
    )
    print_results(results, "dominant striker, aerial ability")

    # --- Test 5: high-pressing defensive midfielder ---
    results = search_similar_players(
        col, model,
        "high pressing defensive midfielder, strong tackle rate, ball recovery",
    )
    print_results(results, "high pressing defensive midfielder")

    print("\n" + "=" * 60)
    print("Smoke tests complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
