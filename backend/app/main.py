"""FastAPI application entry point for the Stage 1 backend."""

import logging
import os

from fastapi import FastAPI


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


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return a simple readiness confirmation for the backend service."""
    logger.debug("Health endpoint requested")
    return {"status": "ok", "service": "ai-soc-rag-backend"}
