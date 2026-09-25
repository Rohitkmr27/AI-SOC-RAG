"""Offline build script to index preprocessed knowledge base chunks into a lightweight SQLite FTS5 database."""

import json
import logging
import sqlite3
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag.config import DEFAULT_FTS_DATABASE_PATH, DEFAULT_PROCESSED_DIRECTORY

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def build_fts_index(
    chunks_jsonl_path: Path = DEFAULT_PROCESSED_DIRECTORY / "chunks.jsonl",
    db_path: Path = DEFAULT_FTS_DATABASE_PATH,
) -> tuple[int, int, int, float]:
    """Build SQLite FTS5 database from chunks.jsonl.

    Returns (chunks_read, chunks_indexed, chunks_skipped, db_size_mb).
    """
    if not chunks_jsonl_path.exists():
        raise FileNotFoundError(f"Processed chunks file not found: {chunks_jsonl_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing DB if present for deterministic clean build
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create storage table and FTS5 virtual table
    cursor.execute(
        """
        CREATE TABLE knowledge_chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT,
            source TEXT,
            file_name TEXT,
            file_type TEXT,
            chunk_index INTEGER,
            title TEXT,
            content TEXT,
            metadata_json TEXT
        );
        """
    )

    cursor.execute(
        """
        CREATE VIRTUAL TABLE knowledge_fts USING fts5(
            chunk_id UNINDEXED,
            title,
            source,
            file_name,
            content,
            tokenize = 'porter unicode61'
        );
        """
    )

    chunks_read = 0
    chunks_indexed = 0
    chunks_skipped = 0

    with open(chunks_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue

            chunks_read += 1
            try:
                data = json.loads(line_str)
                chunk_id = str(data.get("chunk_id", "")).strip()
                content = str(data.get("text", "")).strip()

                if not chunk_id or not content:
                    chunks_skipped += 1
                    continue

                document_id = str(data.get("document_id", "")).strip()
                source = str(data.get("source", "")).strip()
                file_name = str(data.get("file_name", "")).strip()
                file_type = str(data.get("file_type", "")).strip()
                chunk_index = int(data.get("chunk_index", 0))
                metadata = data.get("metadata", {}) or {}
                title = str(metadata.get("title", "") or file_name).strip()
                metadata_json = json.dumps(metadata)

                cursor.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id, document_id, source, file_name, file_type,
                        chunk_index, title, content, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
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
                    ),
                )

                cursor.execute(
                    """
                    INSERT INTO knowledge_fts (chunk_id, title, source, file_name, content)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (chunk_id, title, source, file_name, content),
                )

                chunks_indexed += 1
            except Exception as exc:
                logger.warning("Skipping malformed chunk line %d: %s", chunks_read, exc)
                chunks_skipped += 1

    conn.commit()
    conn.close()

    db_size_mb = db_path.stat().st_size / (1024 * 1024)

    logger.info("FTS5 Knowledge Index successfully built!")
    logger.info("Chunks read: %d", chunks_read)
    logger.info("Chunks indexed: %d", chunks_indexed)
    logger.info("Chunks skipped: %d", chunks_skipped)
    logger.info("Database path: %s", db_path)
    logger.info("Database size: %.2f MB", db_size_mb)

    return chunks_read, chunks_indexed, chunks_skipped, db_size_mb


if __name__ == "__main__":
    build_fts_index()
