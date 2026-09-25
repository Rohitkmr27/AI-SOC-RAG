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


import pandas as pd
from app.alerts import api as alerts_api
from app.alerts.models import Alert
from app.alerts.service import create_alerts_from_predictions
from app.ids.feature_preparation import prepare_features
from app.ids.model import build_model_pipeline
from app.ids.validation import validate_and_clean_dataset


def get_mock_model():
    sample_data = pd.DataFrame({
        "Flow Duration": [1, 2, 3, 4],
        "Protocol": [6, 6, 17, 17],
        "Service": ["http", "http", "dns", "dns"],
        "Label": ["BENIGN", "DDoS", "PortScan", "BENIGN"]
    })
    cleaned, _ = validate_and_clean_dataset(sample_data)
    dataset = prepare_features(cleaned)
    model = build_model_pipeline(dataset.features)
    return model.fit(dataset.features, dataset.target)


def test_create_alerts_from_predictions_filters_benign_and_deduplicates(client: TestClient) -> None:
    # Use overridden DB session
    from app.database import get_db
    session = next(app.dependency_overrides[get_db]())

    batch_results = [
        {"row_index": 0, "prediction": "BENIGN", "confidence": 0.99, "severity": "Informational"},
        {"row_index": 1, "prediction": "DDoS", "confidence": 0.95, "severity": "High"},
        {"row_index": 2, "prediction": "PortScan", "confidence": 0.88, "severity": "Medium"},
    ]
    df = pd.DataFrame([
        {"Source IP": "192.168.1.10", "Destination IP": "10.0.0.1", "Source Port": 5000, "Destination Port": 80, "Protocol": "TCP"},
        {"Source IP": "192.168.1.10", "Destination IP": "10.0.0.1", "Source Port": 5001, "Destination Port": 80, "Protocol": "TCP"},
        {"Source IP": "192.168.1.10", "Destination IP": "10.0.0.1", "Source Port": 5002, "Destination Port": 80, "Protocol": "TCP"},
    ])

    new_alerts, dupes = create_alerts_from_predictions(session, batch_results, df)
    assert len(new_alerts) == 2  # BENIGN skipped
    assert dupes == 0
    assert new_alerts[0].attack_type == "DDoS"
    assert new_alerts[1].attack_type == "PortScan"

    # Second run with identical dataframe -> duplicates skipped
    new_alerts_2, dupes_2 = create_alerts_from_predictions(session, batch_results, df)
    assert len(new_alerts_2) == 0
    assert dupes_2 == 2


def test_alerts_from_csv_endpoint_success_and_deduplication(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(alerts_api, "load_model", lambda _: get_mock_model())

    csv_content = (
        "Flow Duration,Protocol,Service,Source IP,Destination IP,Source Port,Destination Port\n"
        "1,6,http,192.168.1.50,10.0.0.5,4000,80\n"
        "2,6,http,192.168.1.50,10.0.0.5,4001,80\n"
        "3,17,dns,192.168.1.50,10.0.0.5,4002,53\n"
    )

    res = client.post("/alerts/from-csv", files={"file": ("attacks.csv", csv_content, "text/csv")})
    assert res.status_code == 201
    data = res.json()
    assert data["total_flows"] == 3
    assert data["attack_flows"] >= 1
    assert data["alerts_created"] >= 1
    assert len(data["alert_ids"]) == data["alerts_created"]

    # Verify GET /alerts and GET /alerts/correlations now return persisted records
    alerts_list = client.get("/alerts").json()
    assert len(alerts_list) >= 1

    corr_res = client.get("/alerts/correlations").json()
    assert corr_res["total_incidents"] >= 1

    # Upload same CSV again to verify deduplication
    res2 = client.post("/alerts/from-csv", files={"file": ("attacks.csv", csv_content, "text/csv")})
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["alerts_created"] == 0
    assert data2["duplicates_skipped"] == data["alerts_created"]


def test_alerts_from_csv_endpoint_empty_file(client: TestClient) -> None:
    res = client.post("/alerts/from-csv", files={"file": ("empty.csv", "", "text/csv")})
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_alerts_from_csv_endpoint_unauthenticated() -> None:
    app.dependency_overrides.clear()
    c = TestClient(app)
    res = c.post("/alerts/from-csv", files={"file": ("test.csv", "Flow Duration\n1\n", "text/csv")})
    assert res.status_code == 401


def test_mixed_flow_deduplication_and_filtering(client: TestClient) -> None:
    """Verify Task 2: Mixed-flow deduplication and BENIGN filtering."""
    from app.database import get_db
    session = next(app.dependency_overrides[get_db]())

    batch_results = [
        {"row_index": 0, "prediction": "BENIGN", "confidence": 0.99, "severity": "Informational"},
        {"row_index": 1, "prediction": "DDoS", "confidence": 0.96, "severity": "High"},
        {"row_index": 2, "prediction": "PortScan", "confidence": 0.85, "severity": "Medium"},
        {"row_index": 3, "prediction": "DDoS", "confidence": 0.96, "severity": "High"},  # Duplicate of row 1
    ]
    df = pd.DataFrame([
        {"Source IP": "192.168.1.10", "Destination IP": "10.0.0.1", "Source Port": 5000, "Destination Port": 80, "Protocol": "TCP"},
        {"Source IP": "192.168.1.10", "Destination IP": "10.0.0.1", "Source Port": 5001, "Destination Port": 80, "Protocol": "TCP"},
        {"Source IP": "192.168.1.10", "Destination IP": "10.0.0.1", "Source Port": 5002, "Destination Port": 80, "Protocol": "TCP"},
        {"Source IP": "192.168.1.10", "Destination IP": "10.0.0.1", "Source Port": 5001, "Destination Port": 80, "Protocol": "TCP"},
    ])

    new_alerts, dupes_skipped = create_alerts_from_predictions(session, batch_results, df)

    # Normal flow skipped, Attack A created, Attack B created, duplicate Attack A skipped
    assert len(new_alerts) == 2
    assert dupes_skipped == 1
    attack_types = [a.attack_type for a in new_alerts]
    assert "DDoS" in attack_types
    assert "PortScan" in attack_types


def test_database_persistence_transaction_and_columns(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """Verify Task 3: Query test DB directly after POST /alerts/from-csv and inspect columns."""
    monkeypatch.setattr(alerts_api, "load_model", lambda _: get_mock_model())

    csv_content = (
        "Flow Duration,Protocol,Service,Source IP,Destination IP,Source Port,Destination Port\n"
        "2,6,http,192.168.1.75,10.0.0.20,54321,80\n"
    )

    res = client.post("/alerts/from-csv", files={"file": ("sample.csv", csv_content, "text/csv")})
    assert res.status_code == 201

    from app.database import get_db
    session = next(app.dependency_overrides[get_db]())
    db_alerts = session.query(Alert).filter(Alert.source_ip == "192.168.1.75").all()

    assert len(db_alerts) == 1
    alert = db_alerts[0]
    assert alert.source_ip == "192.168.1.75"
    assert alert.destination_ip == "10.0.0.20"
    assert alert.source_port == 54321
    assert alert.destination_port == 80
    assert alert.protocol == "TCP"
    assert alert.attack_type == "DDoS"
    assert alert.confidence > 0.0
    assert alert.severity is not None
    assert alert.timestamp is not None


def test_existing_endpoints_retrieve_persisted_alerts(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """Verify Task 4: GET /alerts, GET /alerts/{id}, GET /alerts/correlations consume new alerts."""
    monkeypatch.setattr(alerts_api, "load_model", lambda _: get_mock_model())

    csv_content = (
        "Flow Duration,Protocol,Service,Source IP,Destination IP,Source Port,Destination Port\n"
        "2,6,http,192.168.1.88,10.0.0.30,45000,80\n"
    )

    res = client.post("/alerts/from-csv", files={"file": ("traffic.csv", csv_content, "text/csv")})
    assert res.status_code == 201
    created_id = res.json()["alert_ids"][0]

    # Test GET /alerts/{id}
    alert_detail = client.get(f"/alerts/{created_id}")
    assert alert_detail.status_code == 200
    assert alert_detail.json()["source_ip"] == "192.168.1.88"

    # Test GET /alerts
    alerts_list = client.get("/alerts").json()
    assert any(a["id"] == created_id for a in alerts_list)

    # Test GET /alerts/correlations
    corr_res = client.get("/alerts/correlations")
    assert corr_res.status_code == 200
    incidents = corr_res.json()["incidents"]
    assert len(incidents) >= 1
    inc_id = incidents[0]["incident_id"]

    # Test GET /alerts/correlations/{incident_id}
    inc_detail = client.get(f"/alerts/correlations/{inc_id}")
    assert inc_detail.status_code == 200
    assert inc_detail.json()["incident_id"] == inc_id


def test_rag_not_loaded_during_alert_creation(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """Verify Task 7: CSV -> IDS -> Alerts does NOT load SentenceTransformer, Qdrant, or Gemini modules."""
    monkeypatch.setattr(alerts_api, "load_model", lambda _: get_mock_model())

    # Check sys.modules before request
    assert "sentence_transformers" not in sys.modules
    assert "qdrant_client" not in sys.modules
    assert "google.generativeai" not in sys.modules

    csv_content = (
        "Flow Duration,Protocol,Service,Source IP,Destination IP,Source Port,Destination Port\n"
        "2,6,http,192.168.1.99,10.0.0.40,46000,80\n"
    )
    res = client.post("/alerts/from-csv", files={"file": ("flow.csv", csv_content, "text/csv")})
    assert res.status_code == 201

    # Check sys.modules after request
    assert "sentence_transformers" not in sys.modules
    assert "qdrant_client" not in sys.modules
    assert "google.generativeai" not in sys.modules




