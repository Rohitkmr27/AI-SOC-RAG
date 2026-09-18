"""Paths and deterministic chunking defaults for knowledge-base ingestion."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_DIRECTORY = PROJECT_ROOT / "data" / "knowledge_base" / "raw"
DEFAULT_PROCESSED_DIRECTORY = PROJECT_ROOT / "data" / "knowledge_base" / "processed"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}
