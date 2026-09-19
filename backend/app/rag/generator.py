"""Grounded RAG answer generation using semantic retrieval and an LLM."""

import logging
from pathlib import Path
from typing import Any

from app.rag.config import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_RAG_MAX_CONTEXT_CHARS,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
    DEFAULT_VECTOR_STORE_DIRECTORY,
)
from app.rag.llm import GeminiProvider, LLMProvider
from app.rag.schemas import RAGResponse, RAGSource
from app.rag.search import search_chunks

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a cybersecurity assistant for an AI-SOC system.\n"
    "Answer using only the supplied retrieved security knowledge.\n"
    "Do not invent facts or sources.\n"
    "If the supplied context does not contain enough information, explicitly say that the "
    "available knowledge base does not provide enough information.\n"
    "Clearly distinguish retrieved facts from uncertainty.\n"
    "Do not claim that an event occurred unless supported by the supplied context."
)

FALLBACK_EMPTY_ANSWER = "I could not find sufficient information in the security knowledge base to answer this question."


def construct_context(
    chunks: list[dict[str, Any]],
    max_chars: int = DEFAULT_RAG_MAX_CONTEXT_CHARS,
) -> tuple[str, list[dict[str, Any]]]:
    """Format retrieved chunk payloads into a bounded context string.

    Returns the formatted string and the list of chunks that fit within max_chars.
    """
    context_blocks: list[str] = []
    used_chunks: list[dict[str, Any]] = []
    current_length = 0

    for idx, chunk in enumerate(chunks, 1):
        source = chunk.get("source", "unknown")
        file_name = chunk.get("file_name", "unknown")
        title = chunk.get("title") or "N/A"
        chunk_id = chunk.get("chunk_id", "")
        content = (chunk.get("content") or "").strip()

        if not content:
            continue

        header = f"--- [Document {idx}] Source: {source} | File: {file_name} | Title: {title} | Chunk ID: {chunk_id} ---\n"
        block = f"{header}{content}\n\n"

        if current_length + len(block) > max_chars:
            # If nothing has been added yet, include a truncated block to preserve minimal context
            if not context_blocks:
                allowed_content_len = max_chars - len(header) - 5
                if allowed_content_len > 50:
                    context_blocks.append(f"{header}{content[:allowed_content_len]}...\n\n")
                    used_chunks.append(chunk)
            break

        context_blocks.append(block)
        used_chunks.append(chunk)
        current_length += len(block)

    return "".join(context_blocks).strip(), used_chunks


def build_user_prompt(query: str, context: str) -> str:
    """Build user prompt containing retrieved security context and the user question."""
    return (
        "Context from Security Knowledge Base:\n"
        f"{context}\n\n"
        f"Question: {query.strip()}\n\n"
        "Instructions: Answer the question using ONLY the security context provided above. "
        "Do not invent facts or sources. If the provided context is insufficient, explicitly state "
        "that the available knowledge base does not provide enough information."
    )


def build_sources_list(chunks: list[dict[str, Any]]) -> list[RAGSource]:
    """Convert raw chunk dictionaries into structured RAGSource models."""
    sources: list[RAGSource] = []
    for chunk in chunks:
        sources.append(
            RAGSource(
                source=chunk.get("source", "unknown"),
                file_name=chunk.get("file_name", "unknown"),
                document_id=chunk.get("document_id", ""),
                chunk_id=chunk.get("chunk_id", ""),
                chunk_index=chunk.get("chunk_index", 0),
                score=float(chunk.get("score", 0.0)),
                title=chunk.get("title"),
            )
        )
    return sources


def generate_rag_answer(
    query: str,
    top_k: int = DEFAULT_RAG_TOP_K,
    score_threshold: float | None = DEFAULT_RAG_SCORE_THRESHOLD,
    max_context_chars: int = DEFAULT_RAG_MAX_CONTEXT_CHARS,
    llm_client: LLMProvider | None = None,
    vector_store_path: Path = DEFAULT_VECTOR_STORE_DIRECTORY,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> RAGResponse:
    """Retrieve security context, build prompt, invoke LLM, and return grounded answer."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    if top_k <= 0:
        raise ValueError("top_k must be positive.")
    if score_threshold is not None and not 0.0 <= score_threshold <= 1.0:
        raise ValueError("score_threshold must be between 0.0 and 1.0.")
    if max_context_chars <= 0:
        raise ValueError("max_context_chars must be positive.")

    cleaned_query = query.strip()

    # Step 1: Semantic retrieval
    retrieved_chunks = search_chunks(
        query=cleaned_query,
        top_k=top_k,
        score_threshold=score_threshold,
        vector_store_path=vector_store_path,
        collection_name=collection_name,
        model_name=embedding_model_name,
    )

    # Step 2: Empty retrieval guard - do not call LLM
    if not retrieved_chunks:
        logger.info("No matching chunks retrieved for query; returning fallback answer without LLM.")
        return RAGResponse(
            answer=FALLBACK_EMPTY_ANSWER,
            sources=[],
        )

    # Step 3: Context construction
    context_str, used_chunks = construct_context(retrieved_chunks, max_chars=max_context_chars)
    if not context_str or not used_chunks:
        logger.info("Constructed context is empty; returning fallback answer without LLM.")
        return RAGResponse(
            answer=FALLBACK_EMPTY_ANSWER,
            sources=[],
        )

    # Step 4: Prompt construction
    prompt = build_user_prompt(cleaned_query, context_str)
    sources = build_sources_list(used_chunks)

    # Step 5: LLM Generation
    provider = llm_client or GeminiProvider()
    answer = provider.generate(prompt=prompt, system_instruction=SYSTEM_PROMPT)

    return RAGResponse(
        answer=answer,
        sources=sources,
    )
