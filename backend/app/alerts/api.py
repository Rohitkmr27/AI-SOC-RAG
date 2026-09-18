"""FastAPI endpoints for persisted security alerts."""

import logging
import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.alerts.models import AlertSeverity, AlertStatus
from app.alerts.schemas import AlertCreate, AlertResponse, AlertUpdate, IdsAlertCreate
from app.alerts.service import create_alert, get_alert, list_alerts, update_alert
from app.database import get_db
from app.ids.config import DEFAULT_ARTIFACT_DIRECTORY, MODEL_FILENAME
from app.ids.model import load_model
from app.ids.prediction import predict_flow


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])


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
