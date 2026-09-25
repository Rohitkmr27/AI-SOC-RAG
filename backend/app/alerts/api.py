"""FastAPI endpoints for persisted security alerts."""

import logging
import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.alerts.models import AlertSeverity, AlertStatus
from app.alerts.schemas import (
    AlertCreate,
    AlertEnrichmentResponse,
    AlertResponse,
    AlertUpdate,
    CorrelationResponse,
    IdsAlertCreate,
    IncidentInvestigationResponse,
    IncidentResponse,
)
from app.alerts.service import (
    create_alert,
    get_alert,
    list_alerts,
    list_recent_alerts,
    update_alert,
)
from app.alerts.correlation import DEFAULT_CORRELATION_WINDOW_MINUTES, correlate_alerts
from app.database import get_db
from app.rag.alert_enrichment import enrich_alert
from app.rag.api import get_llm_provider
from app.rag.incident_investigation import investigate_incident
from app.rag.llm import LLMProvider
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.ids.config import DEFAULT_ARTIFACT_DIRECTORY, MODEL_FILENAME
from app.ids.model import load_model
from app.ids.prediction import predict_flow


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])


def database_error(session: Session, error: SQLAlchemyError) -> HTTPException:
    session.rollback()
    logger.error("Alert database operation failed: %s", error.__class__.__name__)
    return HTTPException(status_code=503, detail="Alert database operation failed.")


@router.post("", response_model=AlertResponse, status_code=201)
def post_alert(payload: AlertCreate, session: Session = Depends(get_db)) -> AlertResponse:
    try:
        return create_alert(session, payload)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error


@router.get("", response_model=list[AlertResponse])
def get_alerts(
    severity: AlertSeverity | None = None,
    status: AlertStatus | None = None,
    attack_type: str | None = Query(default=None, min_length=1, max_length=100),
    session: Session = Depends(get_db),
) -> Sequence[AlertResponse]:
    try:
        return list_alerts(session, severity, status, attack_type)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error


@router.post("/seed", response_model=list[AlertResponse], status_code=201)
def seed_alerts_endpoint(session: Session = Depends(get_db)) -> Sequence[AlertResponse]:
    """Seed sample security alerts into PostgreSQL database for dashboard telemetry."""
    from app.alerts.seed import seed_alerts
    try:
        return seed_alerts(session)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error


@router.post("/from-ids", response_model=AlertResponse, status_code=201)
def create_alert_from_ids(payload: IdsAlertCreate, session: Session = Depends(get_db)) -> AlertResponse:
    """Run the existing trained IDS then persist its real classification as an alert."""
    try:
        prediction = predict_flow(
            load_model(DEFAULT_ARTIFACT_DIRECTORY / MODEL_FILENAME), payload.features
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail="Trained IDS model is unavailable.") from error
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(status_code=422, detail="Features do not match the trained IDS schema.") from error

    alert_payload = AlertCreate(
        timestamp=payload.timestamp,
        source_ip=payload.source_ip,
        destination_ip=payload.destination_ip,
        source_port=payload.source_port,
        destination_port=payload.destination_port,
        protocol=payload.protocol,
        attack_type=prediction["prediction"],
        confidence=prediction["confidence"],
        severity=prediction["severity"],
        description="Created from a trained IDS prediction.",
    )
    try:
        return create_alert(session, alert_payload)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error


@router.get("/correlations", response_model=CorrelationResponse)
def get_alert_correlations(
    lookback_minutes: int = Query(default=60, ge=1, le=10080),
    correlation_window_minutes: int = Query(default=DEFAULT_CORRELATION_WINDOW_MINUTES, ge=1, le=1440),
    source_ip: str | None = Query(default=None),
    minimum_risk_score: int | None = Query(default=None, ge=0, le=100),
    session: Session = Depends(get_db),
) -> CorrelationResponse:
    """Retrieve deterministic incident groups formed from correlated alerts."""
    try:
        alerts = list_recent_alerts(session, lookback_minutes=lookback_minutes, source_ip=source_ip)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error

    incidents = correlate_alerts(alerts, correlation_window_minutes=correlation_window_minutes)

    if minimum_risk_score is not None:
        incidents = [inc for inc in incidents if inc.risk_score >= minimum_risk_score]

    total_correlated_alerts = sum(inc.alert_count for inc in incidents)

    return CorrelationResponse(
        incidents=incidents,
        total_incidents=len(incidents),
        total_correlated_alerts=total_correlated_alerts,
        lookback_minutes=lookback_minutes,
        correlation_window_minutes=correlation_window_minutes,
    )


@router.get("/correlations/{incident_id}", response_model=IncidentResponse)
def get_one_incident(
    incident_id: uuid.UUID,
    lookback_minutes: int = Query(default=60, ge=1, le=10080),
    correlation_window_minutes: int = Query(default=DEFAULT_CORRELATION_WINDOW_MINUTES, ge=1, le=1440),
    session: Session = Depends(get_db),
) -> IncidentResponse:
    """Retrieve a specific correlated incident group by incident ID."""
    try:
        alerts = list_recent_alerts(session, lookback_minutes=lookback_minutes)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error

    incidents = correlate_alerts(alerts, correlation_window_minutes=correlation_window_minutes)
    for inc in incidents:
        if inc.incident_id == incident_id:
            return inc

    raise HTTPException(status_code=404, detail="Incident not found.")


@router.post("/correlations/{incident_id}/investigate", response_model=IncidentInvestigationResponse)
def investigate_incident_endpoint(
    incident_id: uuid.UUID,
    lookback_minutes: int = Query(default=60, ge=1, le=10080),
    correlation_window_minutes: int = Query(default=DEFAULT_CORRELATION_WINDOW_MINUTES, ge=1, le=1440),
    top_k: int = Query(default=5, ge=1, le=20),
    session: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_provider),
) -> IncidentInvestigationResponse:
    """Investigate a correlated incident with grounded multi-chunk RAG cyber intelligence synthesis."""
    try:
        alerts = list_recent_alerts(session, lookback_minutes=lookback_minutes)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error

    incidents = correlate_alerts(alerts, correlation_window_minutes=correlation_window_minutes)
    target_incident = None
    for inc in incidents:
        if inc.incident_id == incident_id:
            target_incident = inc
            break

    if target_incident is None:
        raise HTTPException(status_code=404, detail="Incident not found.")

    try:
        investigation, sources = investigate_incident(target_incident, llm_client=llm, top_k=top_k)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        logger.error("Incident investigation unavailable: %s", error)
        raise HTTPException(
            status_code=503,
            detail=f"Generation service unavailable: {error}",
        ) from error

    return IncidentInvestigationResponse(
        incident=target_incident,
        investigation=investigation,
        sources=sources,
    )


@router.get("/{alert_id}", response_model=AlertResponse)
def get_one_alert(alert_id: uuid.UUID, session: Session = Depends(get_db)) -> AlertResponse:
    try:
        alert = get_alert(session, alert_id)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert


@router.patch("/{alert_id}", response_model=AlertResponse)
def patch_alert(alert_id: uuid.UUID, payload: AlertUpdate, session: Session = Depends(get_db)) -> AlertResponse:
    try:
        alert = get_alert(session, alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found.")
        return update_alert(session, alert, payload)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error


@router.post("/{alert_id}/enrich", response_model=AlertEnrichmentResponse)
def enrich_alert_endpoint(
    alert_id: uuid.UUID,
    session: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_provider),
) -> AlertEnrichmentResponse:
    """Enrich an existing alert with grounded RAG cybersecurity analysis."""
    try:
        alert = get_alert(session, alert_id)
    except SQLAlchemyError as error:
        raise database_error(session, error) from error

    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")

    try:
        analysis, sources = enrich_alert(alert, llm_client=llm)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        logger.error("Alert enrichment unavailable: %s", error)
        raise HTTPException(
            status_code=503,
            detail=f"Generation service unavailable: {error}",
        ) from error

    return AlertEnrichmentResponse(
        alert=AlertResponse.model_validate(alert),
        analysis=analysis,
        sources=sources,
    )
