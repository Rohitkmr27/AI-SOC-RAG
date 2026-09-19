"""Index Stage 4 JSONL chunks into a local persistent Qdrant collection."""

import argparse
import json
from pathlib import Path

from app.rag.config import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_PROCESSED_DIRECTORY,
    DEFAULT_VECTOR_STORE_DIRECTORY,
)
from app.rag.embeddings import EmbeddingService
from app.rag.schemas import DocumentChunk
from app.rag.vector_store import QdrantStore


def read_chunks(path: Path) -> list[DocumentChunk]:
    if not path.exists():
        raise FileNotFoundError(f"Chunk file does not exist: {path}")
    chunks: list[DocumentChunk] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                chunks.append(DocumentChunk.model_validate_json(line))
            except Exception as error:
                raise ValueError(f"Invalid chunk at line {line_number}: {error}") from error
    return chunks


def index_chunks(
    chunks_path: Path = DEFAULT_PROCESSED_DIRECTORY / "chunks.jsonl",
    vector_store_path: Path = DEFAULT_VECTOR_STORE_DIRECTORY,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> tuple[int, int]:
    chunks = read_chunks(chunks_path)
    embedder = EmbeddingService(model_name)
    store = QdrantStore(vector_store_path, collection_name)
    store.recreate_collection(embedder.dimension)
    if chunks:
        store.upsert(chunks, embedder.embed([chunk.text for chunk in chunks]))
    return len(chunks), embedder.dimension


def main() -> None:
    parser = argparse.ArgumentParser(description="Index local knowledge-base chunks in Qdrant.")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_PROCESSED_DIRECTORY / "chunks.jsonl")
    parser.add_argument("--vector-store", type=Path, default=DEFAULT_VECTOR_STORE_DIRECTORY)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    args = parser.parse_args()
    count, dimension = index_chunks(args.chunks, args.vector_store, args.collection, args.model)
    print(json.dumps({"chunks_indexed": count, "embedding_dimension": dimension, "collection": args.collection}))


if __name__ == "__main__":
    main()