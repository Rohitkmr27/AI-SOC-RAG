"""Structured, vector-database-independent knowledge-base representations."""

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    document_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: str
    file_name: str
    file_type: str
    text: str = Field(min_length=1)
    metadata: dict[str, Any]


class DocumentChunk(BaseModel):
    chunk_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    document_id: str
    source: str
    file_name: str
    file_type: str
    text: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    metadata: dict[str, Any]


class IngestionError(BaseModel):
    source: str
    message: str


class LoadResult(BaseModel):
    documents: list[KnowledgeDocument] = Field(default_factory=list)
    errors: list[IngestionError] = Field(default_factory=list)
