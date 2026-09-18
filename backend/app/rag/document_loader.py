"""Discover, extract, chunk, and persist local knowledge-base documents."""

import argparse
import hashlib
import json
import logging
from pathlib import Path

from pypdf import PdfReader

from app.rag.chunking import chunk_document
from app.rag.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, DEFAULT_PROCESSED_DIRECTORY, DEFAULT_RAW_DIRECTORY, SUPPORTED_SUFFIXES
from app.rag.schemas import IngestionError, KnowledgeDocument, LoadResult

logger = logging.getLogger(__name__)


def _extract_text(path: Path) -> str:
    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def load_documents(raw_directory: Path) -> LoadResult:
    """Load supported documents individually; unreadable files are recorded, not fatal."""
    result = LoadResult()
    if not raw_directory.exists():
        result.errors.append(IngestionError(source=str(raw_directory), message="Raw directory does not exist."))
        return result
    for path in sorted(item for item in raw_directory.rglob("*") if item.is_file()):
        source = path.relative_to(raw_directory).as_posix()
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            result.errors.append(IngestionError(source=source, message="Unsupported file type."))
            continue
        try:
            text = _extract_text(path).strip()
            if not text:
                raise ValueError("Document contains no extractable text.")
            document_id = hashlib.sha256(f"{source}\0{text}".encode("utf-8")).hexdigest()
            result.documents.append(KnowledgeDocument(
                document_id=document_id,
                source=source,
                file_name=path.name,
                file_type=path.suffix.lower().lstrip("."),
                text=text,
                metadata={"relative_path": source, "file_size_bytes": path.stat().st_size},
            ))
        except Exception as error:  # A single bad source must not abort ingestion.
            logger.warning("Unable to ingest %s: %s", source, error)
            result.errors.append(IngestionError(source=source, message=str(error)))
    return result


def write_chunks(raw_directory: Path, output_path: Path, chunk_size: int, chunk_overlap: int) -> tuple[int, int]:
    """Write deterministic JSONL chunks and return document/error counts."""
    result = load_documents(raw_directory)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        for document in result.documents:
            for chunk in chunk_document(document, chunk_size, chunk_overlap):
                stream.write(chunk.model_dump_json() + "\n")
    return len(result.documents), len(result.errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest local knowledge-base documents into JSONL chunks.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_RAW_DIRECTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_PROCESSED_DIRECTORY / "chunks.jsonl")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    args = parser.parse_args()
    documents, errors = write_chunks(args.input_dir, args.output, args.chunk_size, args.chunk_overlap)
    print(json.dumps({"documents_loaded": documents, "documents_skipped": errors, "output": str(args.output)}))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
