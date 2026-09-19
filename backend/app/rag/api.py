"""FastAPI endpoints for RAG query and answer generation."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.rag.generator import generate_rag_answer
from app.rag.llm import GeminiProvider, LLMProvider
from app.rag.schemas import RAGRequest, RAGResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(get_current_user)])


def get_llm_provider() -> LLMProvider:
    """Dependency provider for the LLM client, allowing clean mocking in tests."""
    return GeminiProvider()


@router.post("/query", response_model=RAGResponse)
def query_rag(
    request: RAGRequest,
    llm: LLMProvider = Depends(get_llm_provider),
) -> RAGResponse:
    """Answer a cybersecurity question using retrieved context and grounded generation."""
    try:
        return generate_rag_answer(
            query=request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            llm_client=llm,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except RuntimeError as exc:
        logger.error("RAG generation unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Generation service unavailable: {exc}",
        )
