"""
embed.py — Day 4
Generates Vertex AI text-embedding-004 embeddings (768-dim) for every
player_tournament_profiles document, bulk-writes them back to MongoDB,
and creates the Atlas Vector Search index.

Run: python embed/embed.py
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.operations import SearchIndexModel

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

MONGO_URI = os.getenv("MONGODB_CLUSTER_CONNECTION")
GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "aideplus")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
GOOGLE_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

BATCH_SIZE = 100
COLLECTION_NAME = "player_tournament_profiles"
INDEX_NAME = "player_embedding_index"
EMBED_DIM = 768


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_credentials() -> None:
    """Set GOOGLE_APPLICATION_CREDENTIALS to an absolute path."""
    if not GOOGLE_CREDS:
        return
    path = Path(GOOGLE_CREDS)
    if not path.is_absolute():
        path = ROOT / GOOGLE_CREDS.lstrip("./\\")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)


def embed_batch(
    model,  # TextEmbeddingModel
    texts: list[str],
    task: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Embed a single batch; uses TextEmbeddingInput for best-practice task hints."""
    from vertexai.language_models import TextEmbeddingInput  # local import — vertexai may not be installed

    inputs = [TextEmbeddingInput(t, task) for t in texts]
    results = model.get_embeddings(inputs, output_dimensionality=EMBED_DIM)
    return [r.values for r in results]


def create_vector_index(collection) -> None:
    """Create the Atlas Vector Search index (skips if it already exists)."""
    try:
        existing = {idx.get("name") for idx in collection.list_search_indexes()}
    except Exception:
        existing = set()

    if INDEX_NAME in existing:
        print(f"  Index '{INDEX_NAME}' already exists — skipping creation")
        return

    index_model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "numDimensions": EMBED_DIM,
                    "path": "embedding",
                    "similarity": "cosine",
                    "type": "vector",
                },
                {"path": "position", "type": "filter"},
                {"path": "tournament_year", "type": "filter"},
                {"path": "nationality", "type": "filter"},
            ]
        },
        name=INDEX_NAME,
        type="vectorSearch",
    )
    collection.create_search_index(model=index_model)
    print(f"  Created '{INDEX_NAME}' — Atlas is building it in the background (~1–2 min)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not MONGO_URI:
        sys.exit("ERROR: MONGODB_CLUSTER_CONNECTION not set in .env")

    # Set absolute credentials path before importing vertexai
    resolve_credentials()

    # --- Init Vertex AI ---
    print("=" * 60)
    print("ScoutIQ Day 4 — Vertex AI Embeddings")
    print("=" * 60)
    print(f"\nInitialising Vertex AI (project={GCP_PROJECT}, region={GCP_REGION}) ...")
    try:
        import vertexai
        from vertexai.language_models import TextEmbeddingModel
    except ImportError:
        sys.exit("ERROR: google-cloud-aiplatform not installed.\nRun: pip install google-cloud-aiplatform")

    vertexai.init(project=GCP_PROJECT, location=GCP_REGION)
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    print("  Model loaded: text-embedding-004 (768 dims)")

    # --- Connect to MongoDB ---
    db = MongoClient(MONGO_URI)["scoutiq"]
    col = db[COLLECTION_NAME]

    # --- Pull profiles that still need embeddings ---
    print(f"\nFetching profiles without embeddings ...")
    profiles = list(
        col.find({"embedding": {"$exists": False}}, {"_id": 1, "embedding_text": 1})
    )
    total_in_col = col.count_documents({})
    print(f"  {total_in_col:,} total profiles | {len(profiles):,} need embedding")

    if not profiles:
        print("  Nothing to embed — all profiles already have vectors.")
    else:
        texts = [p["embedding_text"] for p in profiles]
        ids = [p["_id"] for p in profiles]
        total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

        # --- Generate embeddings ---
        print(f"\nGenerating embeddings in {total_batches} batches of up to {BATCH_SIZE} ...")
        t0 = time.time()
        vectors: list[list[float]] = []

        for i in range(0, len(texts), BATCH_SIZE):
            batch_num = i // BATCH_SIZE + 1
            batch = texts[i : i + BATCH_SIZE]
            batch_vecs = embed_batch(model, batch)
            vectors.extend(batch_vecs)
            elapsed = time.time() - t0
            print(
                f"  [{batch_num:>3}/{total_batches}] {len(batch)} texts  "
                f"(cumulative: {len(vectors):,}  elapsed: {elapsed:.1f}s)"
            )

        # --- Bulk write back ---
        print(f"\nWriting {len(vectors):,} vectors to MongoDB ...")
        ops = [
            UpdateOne({"_id": ids[i]}, {"$set": {"embedding": vectors[i]}})
            for i in range(len(ids))
        ]
        result = col.bulk_write(ops, ordered=False)
        print(f"  Done — modified={result.modified_count}  ({time.time() - t0:.1f}s total)")

    # --- Create Atlas Vector Search index ---
    print(f"\nCreating Atlas Vector Search index '{INDEX_NAME}' ...")
    create_vector_index(col)

    # --- Summary ---
    embedded_count = col.count_documents({"embedding": {"$exists": True}})
    print("\n" + "=" * 60)
    print("Day 4 Complete")
    print("=" * 60)
    print(f"  Embedded: {embedded_count:,} / {total_in_col:,} profiles")
    print(f"  Index:    {INDEX_NAME}  (cosine, 768 dims)")
    print(f"  Filters:  position | tournament_year | nationality")
    print(
        "\nNext: python embed/test_search.py  "
        "(smoke-test vector search once the index is ACTIVE)"
    )


if __name__ == "__main__":
    main()
