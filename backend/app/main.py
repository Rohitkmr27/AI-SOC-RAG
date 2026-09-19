"""FastAPI application entry point for the Stage 1 backend."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.alerts.api import router as alerts_router
from app.auth.api import router as auth_router
from app.ids.api import router as ids_router
from app.rag.api import router as rag_router


def configure_logging() -> None:
    """Configure application logging from the environment when needed."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="AI-SOC-RAG Backend", version="0.1.0")

# Security Hardening: Environment-configurable CORS allowed origins
raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ids_router)
app.include_router(alerts_router)
app.include_router(rag_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return a simple readiness confirmation for the backend service."""
    logger.debug("Health endpoint requested")
    return {"status": "ok", "service": "ai-soc-rag-backend"}
