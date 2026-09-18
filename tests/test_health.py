"""Tests for the Stage 1 backend health endpoint."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.main import app  # noqa: E402


def test_health_endpoint_returns_service_status() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-soc-rag-backend",
    }
