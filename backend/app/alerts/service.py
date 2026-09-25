"""Alert persistence operations shared by API routes and IDS integration."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
import ipaddress
from typing import Any
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts.models import Alert, AlertSeverity, AlertStatus
from app.alerts.schemas import AlertCreate, AlertUpdate


def _clean_ip(val: Any, default: str) -> str:
    if val is not None:
        val_str = str(val).strip()
        try:
            ipaddress.ip_address(val_str)
            return val_str
        except ValueError:
            pass
    return default


def _clean_port(val: Any, default: int) -> int:
    if val is not None:
        try:
            p = int(float(val))
            if 0 <= p <= 65535:
                return p
        except (ValueError, TypeError):
            pass
    return default


def _clean_protocol(val: Any, default: str) -> str:
    if val is not None:
        val_str = str(val).strip().upper()
        if val_str in ("6", "6.0", "TCP"):
            return "TCP"
        if val_str in ("17", "17.0", "UDP"):
            return "UDP"
        if val_str in ("1", "1.0", "ICMP"):
            return "ICMP"
        if val_str and len(val_str) <= 20:
            return val_str
    return default


def _clean_timestamp(val: Any) -> datetime:
    if val is not None:
        if isinstance(val, datetime):
            if val.tzinfo is None:
                return val.replace(tzinfo=timezone.utc)
            return val.astimezone(timezone.utc)
        try:
            dt = pd.to_datetime(val, utc=True)
            if pd.notna(dt):
                return dt.to_pydatetime()
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _map_severity_enum(sev_str: str) -> AlertSeverity:
    if isinstance(sev_str, AlertSeverity):
        return sev_str
    cleaned = str(sev_str).strip().lower()
    mapping = {
        "informational": AlertSeverity.INFORMATIONAL,
        "low": AlertSeverity.LOW,
        "medium": AlertSeverity.MEDIUM,
        "high": AlertSeverity.HIGH,
        "critical": AlertSeverity.CRITICAL,
    }
    return mapping.get(cleaned, AlertSeverity.MEDIUM)


def extract_flow_metadata(row: pd.Series, row_idx: int, fallback_timestamp: datetime | None = None) -> dict[str, Any]:
    """Extract network flow metadata from a CSV DataFrame row with robust fallbacks."""
    row_keys = {str(k).strip().lower(): k for k in row.index}

    def get_val(names: list[str]) -> Any:
        for name in names:
            key = name.lower()
            if key in row_keys:
                v = row[row_keys[key]]
                if pd.notna(v):
                    return v
        return None

    src_ip_raw = get_val(["source ip", "source_ip", "src ip", "src_ip"])
    dst_ip_raw = get_val(["destination ip", "destination_ip", "dst ip", "dst_ip"])
    src_ip = _clean_ip(src_ip_raw, default="192.168.1.100")
    dst_ip = _clean_ip(dst_ip_raw, default="10.0.0.15")

    src_port_raw = get_val(["source port", "source_port", "src port", "src_port"])
    dst_port_raw = get_val(["destination port", "destination_port", "dst port", "dst_port"])
    src_port = _clean_port(src_port_raw, default=49152 + (row_idx % 1000))
    dst_port = _clean_port(dst_port_raw, default=80)

    proto_raw = get_val(["protocol"])
    protocol = _clean_protocol(proto_raw, default="TCP")

    ts_raw = get_val(["timestamp"])
    if ts_raw is not None:
        timestamp = _clean_timestamp(ts_raw)
    else:
        timestamp = fallback_timestamp or datetime.now(timezone.utc).replace(microsecond=0)

    return {
        "source_ip": src_ip,
        "destination_ip": dst_ip,
        "source_port": src_port,
        "destination_port": dst_port,
        "protocol": protocol,
        "timestamp": timestamp,
    }


def create_alerts_from_predictions(
    session: Session,
    batch_results: list[dict[str, Any]],
    dataframe: pd.DataFrame | None = None,
) -> tuple[list[Alert], int]:
    """Convert attack prediction results into Alert database records and persist them.

    Ignores BENIGN (normal) predictions.
    Extracts flow metadata (IPs, ports, protocol, timestamp) if dataframe is provided.
    Deduplicates against existing alert records in database.
    Returns (list_of_newly_created_alerts, count_of_duplicates_skipped).
    """
    attack_results = [r for r in batch_results if r.get("prediction") != "BENIGN"]
    if not attack_results:
        return [], 0

    batch_now = datetime.now(timezone.utc).replace(microsecond=0)

    existing_alerts = session.scalars(select(Alert)).all()
    existing_signatures = {
        (
            a.source_ip,
            a.destination_ip,
            a.source_port,
            a.destination_port,
            a.protocol,
            a.attack_type,
        )
        for a in existing_alerts
    }

    new_alerts: list[Alert] = []
    duplicates_skipped = 0

    for res in attack_results:
        row_idx = res.get("row_index", 0)

        if dataframe is not None and row_idx < len(dataframe):
            row = dataframe.iloc[row_idx]
            flow_meta = extract_flow_metadata(row, row_idx, fallback_timestamp=batch_now)
        else:
            flow_meta = {
                "source_ip": "192.168.1.100",
                "destination_ip": "10.0.0.15",
                "source_port": 49152 + (row_idx % 1000),
                "destination_port": 80,
                "protocol": "TCP",
                "timestamp": batch_now,
            }

        attack_type = res["prediction"]
        confidence = float(res["confidence"])
        severity_str = res["severity"]
        severity_enum = _map_severity_enum(severity_str)

        signature = (
            str(flow_meta["source_ip"]),
            str(flow_meta["destination_ip"]),
            int(flow_meta["source_port"]),
            int(flow_meta["destination_port"]),
            str(flow_meta["protocol"]),
            str(attack_type),
        )

        if signature in existing_signatures:
            duplicates_skipped += 1
            continue

        existing_signatures.add(signature)

        description = (
            f"IDS detected {attack_type} attack flow from "
            f"{flow_meta['source_ip']}:{flow_meta['source_port']} to "
            f"{flow_meta['destination_ip']}:{flow_meta['destination_port']} "
            f"(Confidence: {confidence:.2%}, Row: {row_idx})."
        )

        alert = Alert(
            timestamp=flow_meta["timestamp"],
            source_ip=str(flow_meta["source_ip"]),
            destination_ip=str(flow_meta["destination_ip"]),
            source_port=int(flow_meta["source_port"]),
            destination_port=int(flow_meta["destination_port"]),
            protocol=str(flow_meta["protocol"]),
            attack_type=str(attack_type),
            confidence=confidence,
            severity=severity_enum,
            status=AlertStatus.NEW,
            description=description,
        )
        session.add(alert)
        new_alerts.append(alert)

    if new_alerts:
        session.commit()
        for alert in new_alerts:
            session.refresh(alert)

    return new_alerts, duplicates_skipped



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


def list_recent_alerts(session: Session, lookback_minutes: int, source_ip: str | None = None) -> Sequence[Alert]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    statement = select(Alert).where(Alert.timestamp >= cutoff).order_by(Alert.timestamp.asc())
    if source_ip and source_ip.strip():
        statement = statement.where(Alert.source_ip == source_ip.strip())
    return session.scalars(statement).all()


def get_alert(session: Session, alert_id) -> Alert | None:
    return session.get(Alert, alert_id)


def update_alert(session: Session, alert: Alert, payload: AlertUpdate) -> Alert:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    session.commit()
    session.refresh(alert)
    return alert

