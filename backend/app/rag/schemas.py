"""Structured, vector-database-independent knowledge-base representations."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


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


class RAGRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="Cybersecurity question to answer.")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of chunks to retrieve.")
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0, description="Minimum similarity score.")

    @field_validator("query")
    @classmethod
    def validate_query_not_whitespace(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("query must be a non-empty string.")
        return value.strip()


class RAGSource(BaseModel):
    source: str
    file_name: str
    document_id: str
    chunk_id: str
    chunk_index: int
    score: float
    title: str | None = None


class RAGResponse(BaseModel):
    answer: str
    sources: list[RAGSource] = Field(default_factory=list)
