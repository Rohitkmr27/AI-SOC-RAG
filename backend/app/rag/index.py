"""Index Stage 4 JSONL chunks into a local persistent or Qdrant Cloud collection."""

import argparse
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

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
    batch_size: int = 100,
) -> tuple[int, int]:
    chunks = read_chunks(chunks_path)
    logger.info("Loaded %d chunks from %s", len(chunks), chunks_path)

    embedder = EmbeddingService(model_name)
    store = QdrantStore(vector_store_path, collection_name)
    store.recreate_collection(embedder.dimension)

    total_chunks = len(chunks)
    if total_chunks > 0:
        for i in range(0, total_chunks, batch_size):
            batch = chunks[i : i + batch_size]
            vectors = embedder.embed([chunk.text for chunk in batch])
            store.upsert(batch, vectors)
            logger.info("Indexed %d/%d chunks...", min(i + batch_size, total_chunks), total_chunks)

    return total_chunks, embedder.dimension


def main() -> None:
    load_dotenv()
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