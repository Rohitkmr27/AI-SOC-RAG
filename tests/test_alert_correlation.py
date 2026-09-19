"""Tests for Stage 7: Alert Correlation and Deterministic Risk Scoring."""

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.alerts.correlation import (
    calculate_deterministic_risk_score,
    correlate_alerts,
)
from app.alerts.models import AlertSeverity, Base
from app.alerts.schemas import CorrelationResponse, IncidentResponse
from app.database import get_db
from app.main import app


def make_alert(
    alert_id: uuid.UUID | None = None,
    minutes_offset: float = 0,
    source_ip: str = "192.0.2.10",
    destination_ip: str = "198.51.100.20",
    attack_type: str = "PortScan",
    severity: str | AlertSeverity = AlertSeverity.MEDIUM,
    confidence: float = 0.90,
    base_time: datetime | None = None,
) -> dict[str, Any]:
    t0 = base_time or datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    ts = t0 + timedelta(minutes=minutes_offset)
    return {
        "id": alert_id or uuid.uuid4(),
        "timestamp": ts,
        "source_ip": source_ip,
        "destination_ip": destination_ip,
        "source_port": 51515,
        "destination_port": 443,
        "protocol": "TCP",
        "attack_type": attack_type,
        "confidence": confidence,
        "severity": severity,
        "description": "Test alert for correlation.",
    }


# ==========================================
# 1. Core Correlation Engine Tests
# ==========================================

def test_no_alerts_returns_empty_incidents() -> None:
    incidents = correlate_alerts([])
    assert incidents == []


def test_single_alert_incident() -> None:
    alert = make_alert(severity=AlertSeverity.HIGH, confidence=0.8)
    incidents = correlate_alerts([alert])

    assert len(incidents) == 1
    inc = incidents[0]
    assert isinstance(inc, IncidentResponse)
    assert inc.alert_count == 1
    assert inc.source_ips == ["192.0.2.10"]
    assert inc.destination_ips == ["198.51.100.20"]
    assert inc.attack_types == ["PortScan"]
    assert inc.alert_ids == [alert["id"]]
    assert inc.risk_score > 0
    assert any("Base severity: High" in f for f in inc.risk_factors)


def test_correlation_same_source_ip_within_window() -> None:
    t0 = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    a1 = make_alert(minutes_offset=0, source_ip="192.0.2.10", destination_ip="198.51.100.1", attack_type="PortScan", base_time=t0)
    a2 = make_alert(minutes_offset=10, source_ip="192.0.2.10", destination_ip="198.51.100.2", attack_type="BruteForce", base_time=t0)

    incidents = correlate_alerts([a1, a2], correlation_window_minutes=15)

    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.alert_count == 2
    assert inc.source_ips == ["192.0.2.10"]
    assert sorted(inc.destination_ips) == ["198.51.100.1", "198.51.100.2"]
    assert sorted(inc.attack_types) == ["BruteForce", "PortScan"]
    assert len(inc.alert_ids) == 2


def test_correlation_same_destination_ip_within_window() -> None:
    t0 = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    a1 = make_alert(minutes_offset=0, source_ip="192.0.2.1", destination_ip="198.51.100.20", base_time=t0)
    a2 = make_alert(minutes_offset=5, source_ip="192.0.2.2", destination_ip="198.51.100.20", base_time=t0)

    incidents = correlate_alerts([a1, a2], correlation_window_minutes=15)

    assert len(incidents) == 1
    assert incidents[0].alert_count == 2
    assert sorted(incidents[0].source_ips) == ["192.0.2.1", "192.0.2.2"]
    assert incidents[0].destination_ips == ["198.51.100.20"]


def test_correlation_outside_window_splits_incidents() -> None:
    t0 = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    a1 = make_alert(minutes_offset=0, source_ip="192.0.2.10", base_time=t0)
    a2 = make_alert(minutes_offset=30, source_ip="192.0.2.10", base_time=t0)  # 30 min > 15 min

    incidents = correlate_alerts([a1, a2], correlation_window_minutes=15)

    assert len(incidents) == 2
    assert incidents[0].alert_count == 1
    assert incidents[1].alert_count == 1


def test_correlation_unrelated_ips_splits_incidents() -> None:
    t0 = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    a1 = make_alert(minutes_offset=0, source_ip="192.0.2.1", destination_ip="198.51.100.1", base_time=t0)
    a2 = make_alert(minutes_offset=2, source_ip="192.0.2.2", destination_ip="198.51.100.2", base_time=t0)

    incidents = correlate_alerts([a1, a2], correlation_window_minutes=15)

    assert len(incidents) == 2


# ==========================================
# 2. Risk Score Calculation Tests
# ==========================================

def test_risk_score_calculation_severity_weights() -> None:
    sevs = [
        (AlertSeverity.INFORMATIONAL, 10),
        (AlertSeverity.LOW, 25),
        (AlertSeverity.MEDIUM, 50),
        (AlertSeverity.HIGH, 75),
        (AlertSeverity.CRITICAL, 100),
    ]
    for sev_enum, expected_base in sevs:
        alert = make_alert(severity=sev_enum, confidence=0.0)
        score, factors = calculate_deterministic_risk_score([alert])
        assert score >= expected_base
        assert any(f"({expected_base} pts)" in f for f in factors)


def test_risk_score_confidence_contribution() -> None:
    alert_low_conf = make_alert(severity=AlertSeverity.LOW, confidence=0.0)
    score_low, _ = calculate_deterministic_risk_score([alert_low_conf])

    alert_high_conf = make_alert(severity=AlertSeverity.LOW, confidence=1.0)
    score_high, _ = calculate_deterministic_risk_score([alert_high_conf])

    assert score_high - score_low == 15, "1.0 confidence adds exactly 15 points over 0.0 confidence"


def test_multiple_attack_types_increases_risk_score() -> None:
    t0 = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    a1 = make_alert(minutes_offset=0, attack_type="PortScan", base_time=t0)
    a2 = make_alert(minutes_offset=1, attack_type="BruteForce", base_time=t0)
    a3 = make_alert(minutes_offset=2, attack_type="DoS", base_time=t0)

    score, factors = calculate_deterministic_risk_score([a1, a2, a3])

    assert any("Multiple distinct attack types observed (3 types:" in f for f in factors)
    assert score > 50


def test_risk_score_clamping_at_100() -> None:
    t0 = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    alerts = [
        make_alert(minutes_offset=i * 0.1, severity=AlertSeverity.CRITICAL, confidence=1.0, attack_type=f"Attack{i}", base_time=t0)
        for i in range(10)
    ]
    score, factors = calculate_deterministic_risk_score(alerts)

    assert score == 100, "Risk score must be capped at 100"


# ==========================================
# 3. Determinism & Tie-Breaking Tests
# ==========================================

def test_deterministic_ordering_and_tie_breaking() -> None:
    t0 = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    id1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id2 = uuid.UUID("00000000-0000-0000-0000-000000000002")

    a1 = make_alert(alert_id=id2, minutes_offset=0, base_time=t0)
    a2 = make_alert(alert_id=id1, minutes_offset=0, base_time=t0)

    incidents1 = correlate_alerts([a1, a2])
    incidents2 = correlate_alerts([a2, a1])

    # Incident ID and alert ordering must be identical regardless of input list order
    assert incidents1[0].incident_id == incidents2[0].incident_id
    assert incidents1[0].alert_ids == [id1, id2]
    assert incidents2[0].alert_ids == [id1, id2]


# ==========================================
# 4. API Integration Tests
# ==========================================

@pytest.fixture
def sqlite_client() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_api_get_correlations_empty(sqlite_client: TestClient) -> None:
    res = sqlite_client.get("/alerts/correlations")
    assert res.status_code == 200
    data = res.json()
    assert data["incidents"] == []
    assert data["total_incidents"] == 0
    assert data["total_correlated_alerts"] == 0


def test_api_get_correlations_with_alerts(sqlite_client: TestClient) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    # Post 2 correlated alerts
    sqlite_client.post("/alerts", json={
        "timestamp": now_iso,
        "source_ip": "192.0.2.55",
        "destination_ip": "198.51.100.88",
        "source_port": 50000,
        "destination_port": 80,
        "protocol": "TCP",
        "attack_type": "PortScan",
        "confidence": 0.85,
        "severity": "Medium",
        "description": "Scan alert 1",
    })
    sqlite_client.post("/alerts", json={
        "timestamp": now_iso,
        "source_ip": "192.0.2.55",
        "destination_ip": "198.51.100.89",
        "source_port": 50001,
        "destination_port": 443,
        "protocol": "TCP",
        "attack_type": "BruteForce",
        "confidence": 0.95,
        "severity": "High",
        "description": "Brute force alert 2",
    })

    res = sqlite_client.get("/alerts/correlations?lookback_minutes=60")
    assert res.status_code == 200
    data = res.json()
    assert data["total_incidents"] == 1
    assert data["total_correlated_alerts"] == 2
    inc = data["incidents"][0]
    assert inc["alert_count"] == 2
    assert inc["source_ips"] == ["192.0.2.55"]
    assert sorted(inc["attack_types"]) == ["BruteForce", "PortScan"]

    # Verify GET /alerts/correlations/{incident_id}
    inc_id = inc["incident_id"]
    get_inc_res = sqlite_client.get(f"/alerts/correlations/{inc_id}")
    assert get_inc_res.status_code == 200
    assert get_inc_res.json()["incident_id"] == inc_id


def test_api_get_correlations_filters_minimum_risk_score(sqlite_client: TestClient) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    # Post low severity alert
    sqlite_client.post("/alerts", json={
        "timestamp": now_iso,
        "source_ip": "192.0.2.100",
        "destination_ip": "198.51.100.100",
        "source_port": 1234,
        "destination_port": 80,
        "protocol": "TCP",
        "attack_type": "InfoProbe",
        "confidence": 0.1,
        "severity": "Informational",
        "description": "Low severity probe",
    })

    # High min risk score filter should exclude this low-risk incident
    res = sqlite_client.get("/alerts/correlations?minimum_risk_score=90")
    assert res.status_code == 200
    assert res.json()["total_incidents"] == 0


def test_api_get_correlations_invalid_params(sqlite_client: TestClient) -> None:
    res1 = sqlite_client.get("/alerts/correlations?lookback_minutes=0")
    assert res1.status_code == 422

    res2 = sqlite_client.get("/alerts/correlations?minimum_risk_score=150")
    assert res2.status_code == 422


def test_api_get_one_incident_not_found(sqlite_client: TestClient) -> None:
    random_id = str(uuid.uuid4())
    res = sqlite_client.get(f"/alerts/correlations/{random_id}")
    assert res.status_code == 404
    assert res.json()["detail"] == "Incident not found."
