"""Tests for Stage 8: AI SOC Incident Investigation Engine & Endpoint."""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.alerts.models import AlertSeverity, AlertStatus, Base
from app.alerts.schemas import AlertResponse, IncidentInvestigation, IncidentInvestigationResponse, IncidentResponse
from app.database import get_db
from app.main import app
from app.rag.api import get_llm_provider
from app.rag.incident_investigation import (
    FALLBACK_INVESTIGATION_SUMMARY,
    INCIDENT_INVESTIGATOR_SYSTEM_PROMPT,
    build_incident_investigation_prompt,
    build_incident_retrieval_query,
    investigate_incident,
    parse_investigation_response,
)
from app.rag.llm import GeminiProvider, LLMProvider


class MockInvestigationLLM(LLMProvider):
    """Mock LLM that returns pre-configured JSON incident investigation report."""

    def __init__(self, response_data: dict[str, Any] | str | None = None) -> None:
        if response_data is None:
            self.response_text = json.dumps({
                "executive_summary": "Correlated incident involving repeated PortScan and SSH-Bruteforce attempts from 192.0.2.10.",
                "observed_evidence": [
                    "2 correlated alerts from source IP 192.0.2.10",
                    "PortScan targeting port 443 and SSH-Bruteforce targeting port 22",
                ],
                "threat_context": [
                    "Reconnaissance scanning followed by brute force credential guessing",
                    "MITRE ATT&CK T1110: Brute Force",
                ],
                "investigation_priorities": [
                    "Check SSH authentication logs for successful logons from 192.0.2.10.",
                    "Verify if source IP is listed on threat intelligence blocklists.",
                ],
                "recommended_actions": [
                    "Inspect packet captures for host 198.51.100.20",
                    "Verify if SSH service responded with failed authentication attempts.",
                ],
                "mitigations": [
                    "Temporarily drop all inbound traffic from source IP 192.0.2.10 at perimeter firewall.",
                    "Enforce rate-limiting and fail2ban rules on SSH endpoint.",
                ],
                "mitre_context": [
                    "MITRE ATT&CK T1110: Brute Force",
                ],
                "limitations": [
                    "Advisory decision support based on available alert data.",
                ],
            })
        elif isinstance(response_data, dict):
            self.response_text = json.dumps(response_data)
        else:
            self.response_text = response_data

        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "system_instruction": system_instruction})
        return self.response_text


def make_test_alert_obj(
    attack_type: str = "PortScan",
    source_ip: str = "192.0.2.10",
    dest_ip: str = "198.51.100.20",
    dest_port: int = 443,
    severity: AlertSeverity = AlertSeverity.MEDIUM,
) -> AlertResponse:
    return AlertResponse(
        id=uuid.uuid4(),
        timestamp=datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc),
        source_ip=source_ip,
        destination_ip=dest_ip,
        source_port=51515,
        destination_port=dest_port,
        protocol="TCP",
        attack_type=attack_type,
        confidence=0.88,
        severity=severity,
        status=AlertStatus.NEW,
        description=f"Test alert for {attack_type}",
        created_at=datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc),
    )


def make_test_incident(
    alerts: list[AlertResponse] | None = None,
    risk_score: int = 85,
) -> IncidentResponse:
    if alerts is None:
        alerts = [
            make_test_alert_obj("PortScan", dest_port=443, severity=AlertSeverity.MEDIUM),
            make_test_alert_obj("SSH-Bruteforce", dest_port=22, severity=AlertSeverity.HIGH),
        ]
    start_time = min(a.timestamp for a in alerts)
    end_time = max(a.timestamp for a in alerts)

    inc = IncidentResponse(
        incident_id=uuid.uuid4(),
        alert_count=len(alerts),
        first_seen=start_time,
        last_seen=end_time,
        source_ips=sorted(list({str(a.source_ip) for a in alerts})),
        destination_ips=sorted(list({str(a.destination_ip) for a in alerts})),
        attack_types=sorted(list({a.attack_type for a in alerts})),
        risk_score=risk_score,
        risk_factors=["Base severity: High (75 pts)", "Multiple distinct attack types observed"],
        alert_ids=[a.id for a in alerts],
    )
    object.__setattr__(inc, "alerts", alerts)
    return inc


def make_test_chunk(
    chunk_id: str = "chunk_t1110",
    score: float = 0.92,
    content: str = "Adversaries may use brute force techniques to gain access to accounts (T1110).",
    title: str = "Brute Force",
) -> dict[str, Any]:
    return {
        "score": score,
        "document_id": "doc_bf",
        "chunk_id": chunk_id,
        "source": "mitre/parsed/techniques-attack-pattern--t1110.md",
        "file_name": "t1110.md",
        "file_type": "md",
        "content": content,
        "chunk_index": 1,
        "title": title,
        "metadata": {"relative_path": "mitre/parsed/t1110.md"},
    }


# ==========================================
# 1. Query & Prompt Construction Tests
# ==========================================

def test_build_incident_retrieval_query() -> None:
    incident = make_test_incident()
    query = build_incident_retrieval_query(incident)

    assert "PortScan" in query
    assert "SSH-Bruteforce" in query
    assert "22" in query or "443" in query or "TCP" in query
    assert "investigation detection mitigation incident response" in query


def test_build_incident_investigation_prompt_includes_grounding() -> None:
    incident = make_test_incident()
    context = "Adversaries use SSH brute force (T1110) after initial port scanning (T1046)."
    prompt = build_incident_investigation_prompt(incident, context)

    assert "192.0.2.10" in prompt
    assert "PortScan" in prompt
    assert "SSH-Bruteforce" in prompt
    assert "85 / 100" in prompt
    assert context in prompt

    # System prompt requirements
    assert "AI assistant supporting a Security Operations Center analyst" in INCIDENT_INVESTIGATOR_SYSTEM_PROMPT
    assert "The deterministic risk score is supplied by the system and must not be changed by the LLM." in INCIDENT_INVESTIGATOR_SYSTEM_PROMPT
    assert "Do not invent evidence." in INCIDENT_INVESTIGATOR_SYSTEM_PROMPT
    assert "Do not invent MITRE ATT&CK technique IDs." in INCIDENT_INVESTIGATOR_SYSTEM_PROMPT


# ==========================================
# 2. Parsing & Malformed LLM Response Tests
# ==========================================

def test_parse_investigation_response_valid_json() -> None:
    incident = make_test_incident()
    raw = json.dumps({
        "executive_summary": "Overview text",
        "observed_evidence": ["Evidence 1"],
        "threat_context": ["Root cause text"],
        "investigation_priorities": ["Chain step 1"],
        "recommended_actions": ["Next step 1"],
        "mitigations": ["Containment 1"],
        "mitre_context": ["T1110"],
        "limitations": ["Low FP risk"],
    })
    report = parse_investigation_response(raw, incident)

    assert report.executive_summary == "Overview text"
    assert report.observed_evidence == ["Evidence 1"]
    assert report.threat_context == ["Root cause text"]
    assert report.mitigations == ["Containment 1"]
    assert report.mitre_context == ["T1110"]


def test_parse_investigation_response_markdown_codeblock() -> None:
    incident = make_test_incident()
    raw = "```json\n" + json.dumps({
        "executive_summary": "Codeblock overview",
        "threat_context": ["Codeblock root cause"],
    }) + "\n```"
    report = parse_investigation_response(raw, incident)

    assert report.executive_summary == "Codeblock overview"
    assert report.threat_context == ["Codeblock root cause"]


def test_parse_investigation_response_plain_text_fallback() -> None:
    incident = make_test_incident()
    raw_text = "Plain text analyst investigation report without JSON structure."
    report = parse_investigation_response(raw_text, incident)

    assert isinstance(report, IncidentInvestigation)
    assert "Plain text analyst investigation report" in report.executive_summary
    assert len(report.recommended_actions) > 0


# ==========================================
# 3. Investigation Function Unit Tests
# ==========================================

def test_investigate_incident_success(monkeypatch: pytest.MonkeyPatch) -> None:
    test_chunk = make_test_chunk()
    monkeypatch.setattr("app.rag.incident_investigation.search_chunks", lambda **kwargs: [test_chunk])

    mock_llm = MockInvestigationLLM()
    incident = make_test_incident()

    investigation, sources = investigate_incident(incident, llm_client=mock_llm, top_k=5)

    assert "Correlated incident involving repeated PortScan" in investigation.executive_summary
    assert len(investigation.investigation_priorities) == 2
    assert len(investigation.mitigations) == 2
    assert len(sources) == 1
    assert sources[0].chunk_id == "chunk_t1110"
    assert sources[0].score == pytest.approx(0.92)

    # Immutability check on original incident
    assert incident.risk_score == 85
    assert incident.alert_count == 2

    # Verify system instruction passed to LLM
    assert len(mock_llm.calls) == 1
    assert mock_llm.calls[0]["system_instruction"] == INCIDENT_INVESTIGATOR_SYSTEM_PROMPT


def test_investigate_incident_empty_retrieval_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.rag.incident_investigation.search_chunks", lambda **kwargs: [])
    mock_llm = MockInvestigationLLM()
    incident = make_test_incident()

    investigation, sources = investigate_incident(incident, llm_client=mock_llm)

    assert investigation.executive_summary == FALLBACK_INVESTIGATION_SUMMARY
    assert sources == []
    assert len(mock_llm.calls) == 0, "LLM must NOT be invoked when retrieval yields 0 chunks"


def test_investigate_incident_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    test_chunk = make_test_chunk()
    monkeypatch.setattr("app.rag.incident_investigation.search_chunks", lambda **kwargs: [test_chunk])
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    incident = make_test_incident()
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        investigate_incident(incident, llm_client=GeminiProvider(api_key=None))


def test_investigate_incident_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    test_chunk = make_test_chunk()
    monkeypatch.setattr("app.rag.incident_investigation.search_chunks", lambda **kwargs: [test_chunk])

    class FailingLLM(LLMProvider):
        def generate(self, prompt: str, system_instruction: str | None = None) -> str:
            raise RuntimeError("Gemini API connection error")

    incident = make_test_incident()
    with pytest.raises(RuntimeError, match="Gemini API connection error"):
        investigate_incident(incident, llm_client=FailingLLM())


# ==========================================
from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole

mock_analyst = User(
    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    username="test_analyst",
    role=UserRole.ANALYST,
    is_active=True,
)


@pytest.fixture
def sqlite_client() -> TestClient:
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



def test_api_investigate_incident_success(sqlite_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    test_chunk = make_test_chunk()
    monkeypatch.setattr("app.rag.incident_investigation.search_chunks", lambda **kwargs: [test_chunk])

    mock_llm = MockInvestigationLLM()
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm

    now_iso = datetime.now(timezone.utc).isoformat()
    # Create 2 correlated alerts from source IP 192.0.2.10
    sqlite_client.post("/alerts", json={
        "timestamp": now_iso,
        "source_ip": "192.0.2.10",
        "destination_ip": "198.51.100.20",
        "source_port": 51515,
        "destination_port": 443,
        "protocol": "TCP",
        "attack_type": "PortScan",
        "confidence": 0.91,
        "severity": "Medium",
        "description": "Alert 1",
    })
    sqlite_client.post("/alerts", json={
        "timestamp": now_iso,
        "source_ip": "192.0.2.10",
        "destination_ip": "198.51.100.20",
        "source_port": 51516,
        "destination_port": 22,
        "protocol": "TCP",
        "attack_type": "SSH-Bruteforce",
        "confidence": 0.95,
        "severity": "High",
        "description": "Alert 2",
    })

    # Fetch correlations to obtain an incident_id
    corr_res = sqlite_client.get("/alerts/correlations?lookback_minutes=60")
    assert corr_res.status_code == 200
    corr_data = corr_res.json()
    assert corr_data["total_incidents"] == 1
    incident_id = corr_data["incidents"][0]["incident_id"]

    # Call POST /alerts/correlations/{incident_id}/investigate
    investigate_res = sqlite_client.post(f"/alerts/correlations/{incident_id}/investigate?top_k=5")
    assert investigate_res.status_code == 200

    data = investigate_res.json()
    assert data["incident"]["incident_id"] == incident_id
    assert data["incident"]["source_ips"] == ["192.0.2.10"]
    assert data["incident"]["alert_count"] == 2
    assert "Correlated incident involving repeated PortScan" in data["investigation"]["executive_summary"]
    assert len(data["investigation"]["mitigations"]) == 2
    assert len(data["sources"]) == 1
    assert data["sources"][0]["chunk_id"] == "chunk_t1110"


def test_api_investigate_incident_404_not_found(sqlite_client: TestClient) -> None:
    random_id = str(uuid.uuid4())
    res = sqlite_client.post(f"/alerts/correlations/{random_id}/investigate")
    assert res.status_code == 404
    assert res.json()["detail"] == "Incident not found."


def test_api_investigate_incident_missing_api_key_503(sqlite_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    test_chunk = make_test_chunk()
    monkeypatch.setattr("app.rag.incident_investigation.search_chunks", lambda **kwargs: [test_chunk])
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    now_iso = datetime.now(timezone.utc).isoformat()
    # Create alert
    sqlite_client.post("/alerts", json={
        "timestamp": now_iso,
        "source_ip": "192.0.2.10",
        "destination_ip": "198.51.100.20",
        "source_port": 51515,
        "destination_port": 443,
        "protocol": "TCP",
        "attack_type": "PortScan",
        "confidence": 0.91,
        "severity": "Medium",
        "description": "Alert for key check",
    })

    corr_res = sqlite_client.get("/alerts/correlations")
    incident_id = corr_res.json()["incidents"][0]["incident_id"]

    # Use real GeminiProvider without key
    app.dependency_overrides[get_llm_provider] = lambda: GeminiProvider(api_key=None)

    inv_res = sqlite_client.post(f"/alerts/correlations/{incident_id}/investigate")
    assert inv_res.status_code == 503
    assert "GEMINI_API_KEY" in inv_res.json()["detail"]
