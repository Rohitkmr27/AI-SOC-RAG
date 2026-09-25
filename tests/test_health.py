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


def test_root_endpoint_returns_service_info() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ai-soc-rag-backend"
    assert "docs" in data

