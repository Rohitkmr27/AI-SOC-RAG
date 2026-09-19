"""Paths and defaults for knowledge-base ingestion and retrieval."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_BASE_DIRECTORY = PROJECT_ROOT / "data" / "knowledge_base"
DEFAULT_RAW_DIRECTORY = PROJECT_ROOT / "data" / "knowledge_base" / "raw"
DEFAULT_PROCESSED_DIRECTORY = PROJECT_ROOT / "data" / "knowledge_base" / "processed"
DEFAULT_VECTOR_STORE_DIRECTORY = PROJECT_ROOT / "data" / "knowledge_base" / "vector_store"
DEFAULT_SOURCE_MANIFEST = KNOWLEDGE_BASE_DIRECTORY / "source_manifest.json"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_COLLECTION_NAME = "security_knowledge_chunks"
SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}
DEFAULT_RAG_TOP_K = 5
DEFAULT_RAG_SCORE_THRESHOLD: float | None = None
DEFAULT_RAG_MAX_CONTEXT_CHARS = 12000
DEFAULT_LLM_MODEL = "gemini-2.5-flash"
