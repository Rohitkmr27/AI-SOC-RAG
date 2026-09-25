"""Lightweight SQLite FTS5 lexical retrieval over security knowledge base chunks.

Replaces heavy PyTorch and SentenceTransformer dependencies with zero-overhead SQLite FTS5 BM25 search.
"""

import argparse
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from app.rag.config import DEFAULT_FTS_DATABASE_PATH, DEFAULT_RAG_TOP_K

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he",
    "in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "were", "will",
    "with", "or", "this", "but", "they", "have", "had", "what", "when", "where",
    "who", "which", "why", "how", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "can", "just", "should", "now"
}


def _clean_and_tokenize(query: str) -> list[str]:
    """Extract clean alphanumeric search terms while preserving cybersecurity terminology."""
    raw_tokens = re.findall(r"[A-Za-z0-9_\-\.\:]+", query.lower())
    clean_tokens = []
    for tok in raw_tokens:
        cleaned = tok.strip(".:-")
        if cleaned and len(cleaned) >= 2 and cleaned not in STOPWORDS:
            clean_tokens.append(cleaned)
    return clean_tokens


def search_chunks(
    query: str,
    top_k: int = DEFAULT_RAG_TOP_K,
    score_threshold: float | None = None,
    db_path: Path = DEFAULT_FTS_DATABASE_PATH,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Search knowledge base chunks using SQLite FTS5 BM25 ranking.

    Compatible interface signature. Ignores unused legacy vector store parameters.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    if top_k <= 0:
        raise ValueError("top_k must be positive.")
    if score_threshold is not None and not 0.0 <= score_threshold <= 1.0:
        raise ValueError("score_threshold must be between 0 and 1.")

    if not db_path.exists():
        logger.warning("SQLite FTS database not found at %s. Returning empty context.", db_path)
        return []

    tokens = _clean_and_tokenize(query)
    if not tokens:
        # Fallback to raw string query if tokenization strips everything
        tokens = [query.strip()]

    # Construct FTS5 match query using OR for maximum coverage
    # e.g. "ddos" OR "tcp" OR "mitigation"*
    fts_terms = [f'"{tok}"*' if not tok.isdigit() else f'"{tok}"' for tok in tokens]
    fts_query = " OR ".join(fts_terms)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        sql = """
            SELECT
                kc.chunk_id,
                kc.document_id,
                kc.source,
                kc.file_name,
                kc.file_type,
                kc.chunk_index,
                kc.title,
                kc.content,
                kc.metadata_json,
                bm25(knowledge_fts) AS bm25_rank
            FROM knowledge_fts
            JOIN knowledge_chunks kc ON knowledge_fts.chunk_id = kc.chunk_id
            WHERE knowledge_fts MATCH ?
            ORDER BY bm25_rank ASC
            LIMIT ?;
        """

        cursor.execute(sql, (fts_query, top_k * 2))
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError as exc:
        logger.warning("FTS search operational error (%s) for query: %s", exc, fts_query)
        return []

    results: list[dict[str, Any]] = []
    for row in rows:
        (
            chunk_id,
            document_id,
            source,
            file_name,
            file_type,
            chunk_index,
            title,
            content,
            metadata_json,
            bm25_rank,
        ) = row

        try:
            metadata = json.loads(metadata_json) if metadata_json else {}
        except Exception:
            metadata = {}

        # Convert SQLite FTS5 bm25 rank (negative float, lower is better match) to 0.0-1.0 score
        raw_abs = abs(float(bm25_rank))
        score = round(1.0 / (1.0 + (raw_abs * 0.1)), 4)

        if score_threshold is not None and score < score_threshold:
            continue

        results.append({
            "chunk_id": chunk_id,
            "document_id": document_id,
            "source": source,
            "file_name": file_name,
            "file_type": file_type,
            "chunk_index": chunk_index,
            "title": title,
            "content": content,
            "metadata": metadata,
            "score": score,
        })

        if len(results) >= top_k:
            break

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Search indexed security knowledge chunks via FTS5.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--score-threshold", type=float)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_FTS_DATABASE_PATH)
    args = parser.parse_args()
    print(json.dumps(search_chunks(args.query, args.top_k, args.score_threshold, args.db_path), indent=2))


if __name__ == "__main__":
    main()