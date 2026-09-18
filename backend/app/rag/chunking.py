"""Deterministic word-boundary chunking for extracted security documents."""

import hashlib
import re

from app.rag.schemas import DocumentChunk, KnowledgeDocument


def _overlap_units(units: list[str], overlap: int) -> list[str]:
    selected: list[str] = []
    size = 0
    for unit in reversed(units):
        if size + len(unit) > overlap and selected:
            break
        selected.insert(0, unit)
        size += len(unit)
    return selected


def chunk_document(document: KnowledgeDocument, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[DocumentChunk]:
    """Chunk text on whitespace boundaries while retaining a bounded word overlap."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size.")

    units = re.findall(r"\S+\s*", document.text.strip())
    if not units:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for unit in units:
        if current and current_size + len(unit) > chunk_size:
            chunks.append("".join(current).strip())
            current = _overlap_units(current, chunk_overlap)
            current_size = sum(len(item) for item in current)
        current.append(unit)
        current_size += len(unit)
    if current:
        chunks.append("".join(current).strip())

    return [
        DocumentChunk(
            chunk_id=hashlib.sha256(f"{document.document_id}:{index}:{text}".encode("utf-8")).hexdigest(),
            document_id=document.document_id,
            source=document.source,
            file_name=document.file_name,
            file_type=document.file_type,
            text=text,
            chunk_index=index,
            metadata=document.metadata.copy(),
        )
        for index, text in enumerate(chunks)
    ]
