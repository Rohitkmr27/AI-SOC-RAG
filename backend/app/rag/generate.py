"""Command-line interface for RAG answer generation."""

import argparse
import json
import sys
from pathlib import Path

from app.rag.config import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_RAG_MAX_CONTEXT_CHARS,
    DEFAULT_RAG_TOP_K,
    DEFAULT_VECTOR_STORE_DIRECTORY,
)
from app.rag.generator import generate_rag_answer
from app.rag.llm import GeminiProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate grounded cybersecurity answers using RAG.")
    parser.add_argument("query", help="Cybersecurity question to answer")
    parser.add_argument("--top-k", type=int, default=DEFAULT_RAG_TOP_K, help="Number of chunks to retrieve (default: 5)")
    parser.add_argument("--score-threshold", type=float, default=None, help="Minimum similarity score threshold")
    parser.add_argument("--max-context-chars", type=int, default=DEFAULT_RAG_MAX_CONTEXT_CHARS, help="Max context size in characters")
    parser.add_argument("--model", default=None, help="Gemini model name override (defaults to GEMINI_MODEL or gemini-2.5-flash)")
    parser.add_argument("--vector-store", type=Path, default=DEFAULT_VECTOR_STORE_DIRECTORY, help="Path to vector store")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME, help="Qdrant collection name")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="Embedding model name")
    parser.add_argument("--json", action="store_true", help="Output response as formatted JSON")

    args = parser.parse_args(argv)

    try:
        llm = GeminiProvider(model_name=args.model)
        response = generate_rag_answer(
            query=args.query,
            top_k=args.top_k,
            score_threshold=args.score_threshold,
            max_context_chars=args.max_context_chars,
            llm_client=llm,
            vector_store_path=args.vector_store,
            collection_name=args.collection,
            embedding_model_name=args.embedding_model,
        )
    except ValueError as exc:
        sys.stderr.write(f"Invalid input: {exc}\n")
        return 2
    except RuntimeError as exc:
        sys.stderr.write(f"Generation error: {exc}\n")
        return 1

    if args.json:
        print(response.model_dump_json(indent=2))
        return 0

    print("==================================================")
    print("ANSWER:")
    print("==================================================")
    print(response.answer)
    print()

    if response.sources:
        print("==================================================")
        print("RETRIEVED SOURCES:")
        print("==================================================")
        for idx, src in enumerate(response.sources, 1):
            title_part = f" | Title: {src.title}" if src.title else ""
            print(f"[{idx}] Score: {src.score:.4f} | Source: {src.source}{title_part}")
            print(f"    File: {src.file_name} | Chunk ID: {src.chunk_id}")
    else:
        print("No sources cited (fallback answer).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
