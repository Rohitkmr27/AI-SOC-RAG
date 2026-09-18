"""Alert persistence operations shared by API routes and IDS integration."""

from collections.abc import Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts.models import Alert, AlertSeverity, AlertStatus
from app.alerts.schemas import AlertCreate, AlertUpdate


def create_alert(session: Session, payload: AlertCreate) -> Alert:
    values = payload.model_dump(exclude_none=True, mode="python")
    # Pydantic validates IPs as address objects; the database stores canonical text.
    values["source_ip"] = str(values["source_ip"])
    values["destination_ip"] = str(values["destination_ip"])
    alert = Alert(**values)
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


def list_alerts(session: Session, severity: AlertSeverity | None, status: AlertStatus | None, attack_type: str | None) -> Sequence[Alert]:
    statement = select(Alert).order_by(Alert.timestamp.desc())
    if severity:
        statement = statement.where(Alert.severity == severity)
    if status:
        statement = statement.where(Alert.status == status)
    if attack_type:
        statement = statement.where(Alert.attack_type == attack_type)
    return session.scalars(statement).all()


def get_alert(session: Session, alert_id) -> Alert | None:
    return session.get(Alert, alert_id)


def update_alert(session: Session, alert: Alert, payload: AlertUpdate) -> Alert:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    session.commit()
    session.refresh(alert)
    return alert
