"""Isolated SQLite tests for alert management; never use development PostgreSQL."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.alerts.models import Base
from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.database import get_db
from app.main import app

mock_analyst = User(
    id="00000000-0000-0000-0000-000000000001",
    username="test_analyst",
    role=UserRole.ANALYST,
    is_active=True,
)


@pytest.fixture
def client() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: mock_analyst
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


@pytest.fixture
def alert_payload() -> dict:
    return {
        "timestamp": datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc).isoformat(),
        "source_ip": "192.0.2.10",
        "destination_ip": "198.51.100.20",
        "source_port": 51515,
        "destination_port": 443,
        "protocol": "TCP",
        "attack_type": "PortScan",
        "confidence": 0.91,
        "severity": "Medium",
        "description": "Test fixture only; not an IDS evaluation record.",
    }


def test_alert_create_retrieve_update_and_filter(client: TestClient, alert_payload: dict) -> None:
    created = client.post("/alerts", json=alert_payload)
    assert created.status_code == 201
    alert = created.json()
    assert alert["status"] == "NEW"

    assert client.get(f"/alerts/{alert['id']}").json()["id"] == alert["id"]
    assert len(client.get("/alerts", params={"severity": "Medium", "status": "NEW"}).json()) == 1

    updated = client.patch(f"/alerts/{alert['id']}", json={"status": "TRIAGED", "severity": "High"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "TRIAGED"
    assert updated.json()["severity"] == "High"


def test_invalid_alert_and_missing_alert(client: TestClient, alert_payload: dict) -> None:
    alert_payload["source_ip"] = "not-an-ip"
    alert_payload["confidence"] = 1.2
    assert client.post("/alerts", json=alert_payload).status_code == 422
    assert client.get("/alerts/00000000-0000-0000-0000-000000000000").status_code == 404


def test_database_not_configured_returns_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: mock_analyst
    response = TestClient(app).get("/alerts")
    assert response.status_code == 503
    assert response.json()["detail"] == "Alert database is not configured."


