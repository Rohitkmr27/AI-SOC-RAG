import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.alerts.api import router as alerts_router
from app.auth.api import router as auth_router
from app.config import (
    SensitiveDataFilter,
    get_cors_allowed_origins,
    get_log_level,
    validate_production_configuration,
)
from app.ids.api import router as ids_router
from app.rag.api import router as rag_router


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware adding standard security hardening HTTP headers to response headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


def configure_logging() -> None:
    """Configure application logging with sensitive data masking."""
    log_level = get_log_level()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]


configure_logging()
validate_production_configuration()
logger = logging.getLogger(__name__)

app = FastAPI(title="AI-SOC-RAG Backend", version="0.1.0")

app.add_middleware(SecurityHeadersMiddleware)

# Security Hardening: Environment-validated CORS allowed origins
allowed_origins = get_cors_allowed_origins()

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


@app.get("/")
async def root() -> dict[str, str]:
    """Return basic info and documentation path for root GET requests."""
    return {
        "status": "ok",
        "service": "ai-soc-rag-backend",
        "message": "AI-SOC-RAG Backend API is running.",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
@app.get("/api/health")
@app.get("/api/v1/health")
@app.get("/api/v1/system-status")
async def health_check() -> dict[str, str]:
    """Return a simple readiness confirmation for the backend service."""
    logger.debug("Health endpoint requested")
    return {"status": "ok", "service": "ai-soc-rag-backend"}


