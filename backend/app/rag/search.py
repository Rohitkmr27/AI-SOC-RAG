"""Similarity search over the indexed local security knowledge base."""

import argparse
import json
from pathlib import Path
from typing import Any

from app.rag.config import DEFAULT_COLLECTION_NAME, DEFAULT_EMBEDDING_MODEL, DEFAULT_VECTOR_STORE_DIRECTORY
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import QdrantStore


def search_chunks(
    query: str,
    top_k: int = 5,
    score_threshold: float | None = None,
    vector_store_path: Path = DEFAULT_VECTOR_STORE_DIRECTORY,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> list[dict[str, Any]]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    if top_k <= 0:
        raise ValueError("top_k must be positive.")
    if score_threshold is not None and not 0 <= score_threshold <= 1:
        raise ValueError("score_threshold must be between 0 and 1.")
    store = QdrantStore(vector_store_path, collection_name)
    points = store.search(EmbeddingService(model_name).embed_query(query), top_k, score_threshold)
    return [{"score": point.score, **(point.payload or {})} for point in points]


def main() -> None:
    parser = argparse.ArgumentParser(description="Search indexed security knowledge chunks.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--score-threshold", type=float)
    parser.add_argument("--vector-store", type=Path, default=DEFAULT_VECTOR_STORE_DIRECTORY)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    args = parser.parse_args()
    print(json.dumps(search_chunks(args.query, args.top_k, args.score_threshold, args.vector_store, args.collection, args.model), indent=2))


if __name__ == "__main__":
    main()