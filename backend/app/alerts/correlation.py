"""Stage 7: Alert Correlation and Deterministic Risk Scoring Engine."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
import uuid

from app.alerts.models import AlertSeverity
from app.alerts.schemas import IncidentResponse

DEFAULT_CORRELATION_WINDOW_MINUTES = 15

SEVERITY_WEIGHTS = {
    AlertSeverity.INFORMATIONAL: 10,
    AlertSeverity.LOW: 25,
    AlertSeverity.MEDIUM: 50,
    AlertSeverity.HIGH: 75,
    AlertSeverity.CRITICAL: 100,
}

STRING_SEVERITY_WEIGHTS = {
    "informational": 10,
    "low": 25,
    "medium": 50,
    "high": 75,
    "critical": 100,
}


def _get_attr(item: Any, key: str, default: Any = "") -> Any:
    """Extract attribute safely from object or dictionary."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _get_timestamp(item: Any) -> datetime:
    """Extract datetime timestamp normalized to UTC."""
    val = _get_attr(item, "timestamp")
    if isinstance(val, str):
        val = datetime.fromisoformat(val)
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _get_severity_score(item: Any) -> tuple[int, str]:
    """Return numeric severity weight and canonical display name."""
    sev = _get_attr(item, "severity", AlertSeverity.INFORMATIONAL)
    if isinstance(sev, AlertSeverity):
        return SEVERITY_WEIGHTS.get(sev, 10), sev.value
    if isinstance(sev, str):
        cleaned = sev.strip().lower()
        if cleaned in STRING_SEVERITY_WEIGHTS:
            return STRING_SEVERITY_WEIGHTS[cleaned], sev.strip().capitalize()
    return 10, "Informational"


def calculate_deterministic_risk_score(alerts: list[Any]) -> tuple[int, list[str]]:
    """Calculate an explainable, bounded risk score (0-100) and contributing risk factors.

    This formula is a deterministic prioritization heuristic, not a statistically
    or operationally validated probability of compromise.
    """
    if not alerts:
        return 0, []

    risk_factors: list[str] = []

    # 1. Base Severity Contribution (highest severity in group)
    severity_tuples = [_get_severity_score(a) for a in alerts]
    max_severity_score, max_severity_name = max(severity_tuples, key=lambda t: t[0])
    risk_factors.append(f"Base severity: {max_severity_name} ({max_severity_score} pts)")

    # 2. Confidence Contribution (avg confidence * 15)
    confidences = [float(_get_attr(a, "confidence", 0.5)) for a in alerts]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
    conf_points = int(avg_conf * 15)
    if avg_conf >= 0.7:
        risk_factors.append(f"High model confidence (avg: {avg_conf:.2f})")
    elif avg_conf > 0.0:
        risk_factors.append(f"Model confidence contribution (avg: {avg_conf:.2f})")

    # 3. Alert Volume Contribution
    count = len(alerts)
    volume_points = 0
    if count > 1:
        volume_points = min((count - 1) * 10, 25)
        risk_factors.append(f"Multiple correlated alerts ({count} alerts in incident)")

    # 4. Attack Type Diversity Contribution
    attack_types = sorted(list({str(_get_attr(a, "attack_type", "")).strip() for a in alerts if _get_attr(a, "attack_type", "")}))
    diversity_points = 0
    if len(attack_types) > 1:
        diversity_points = min((len(attack_types) - 1) * 10, 20)
        types_str = ", ".join(attack_types)
        risk_factors.append(f"Multiple distinct attack types observed ({len(attack_types)} types: {types_str})")

    # 5. Repeated Source IP Activity
    source_ips = [str(_get_attr(a, "source_ip", "")).strip() for a in alerts if _get_attr(a, "source_ip", "")]
    source_counts = Counter(source_ips)
    repeated_source_points = 0
    if any(c > 1 for c in source_counts.values()):
        repeated_source_points = 10
        risk_factors.append("Repeated source IP activity")

    # 6. Temporal Concentration (alerts occurring within 5 minutes)
    temporal_points = 0
    if count >= 2:
        timestamps = [_get_timestamp(a) for a in alerts]
        span_seconds = abs((max(timestamps) - min(timestamps)).total_seconds())
        if span_seconds <= 300:
            temporal_points = 10
            risk_factors.append("High temporal concentration (alerts within 5 minutes)")

    # Total Score Calculation Clamped to [0, 100]
    raw_score = (
        max_severity_score
        + conf_points
        + volume_points
        + diversity_points
        + repeated_source_points
        + temporal_points
    )
    clamped_score = min(max(int(raw_score), 0), 100)

    return clamped_score, risk_factors


def correlate_alerts(
    alerts: list[Any],
    correlation_window_minutes: int = DEFAULT_CORRELATION_WINDOW_MINUTES,
) -> list[IncidentResponse]:
    """Deterministically group related alerts into incident campaigns and score risk."""
    if not alerts:
        return []

    # Deterministic initial sort: primary by timestamp, secondary by alert ID string
    sorted_alerts = sorted(
        alerts,
        key=lambda a: (_get_timestamp(a), str(_get_attr(a, "id", ""))),
    )

    window_seconds = correlation_window_minutes * 60
    n = len(sorted_alerts)

    # Build adjacency list graph where an edge exists if alerts share IP and occur within window
    adj: dict[int, set[int]] = defaultdict(set)
    for i in range(n):
        for j in range(i + 1, n):
            a1 = sorted_alerts[i]
            a2 = sorted_alerts[j]
            t1 = _get_timestamp(a1)
            t2 = _get_timestamp(a2)

            time_diff = abs((t1 - t2).total_seconds())
            if time_diff > window_seconds:
                # Since alerts are sorted by timestamp, if t2 - t1 > window_seconds,
                # no subsequent alert j' can connect to i via window_seconds if t_j' >= t_j
                continue

            src1 = str(_get_attr(a1, "source_ip", "")).strip()
            src2 = str(_get_attr(a2, "source_ip", "")).strip()
            dst1 = str(_get_attr(a1, "destination_ip", "")).strip()
            dst2 = str(_get_attr(a2, "destination_ip", "")).strip()

            # Rule: Share source_ip OR destination_ip within correlation window
            if (src1 and src1 == src2) or (dst1 and dst1 == dst2):
                adj[i].add(j)
                adj[j].add(i)

    # Find connected components using BFS for deterministic clustering
    visited = set()
    components: list[list[int]] = []

    for i in range(n):
        if i in visited:
            continue
        component = []
        queue = [i]
        visited.add(i)
        while queue:
            curr = queue.pop(0)
            component.append(curr)
            for neighbor in sorted(list(adj[curr])):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(component)

    incidents: list[IncidentResponse] = []

    for comp_indices in components:
        comp_alerts = [sorted_alerts[idx] for idx in comp_indices]

        # Re-sort component alerts deterministically by timestamp, then ID
        comp_alerts.sort(key=lambda a: (_get_timestamp(a), str(_get_attr(a, "id", ""))))

        alert_ids: list[uuid.UUID] = []
        for a in comp_alerts:
            raw_id = _get_attr(a, "id")
            if isinstance(raw_id, uuid.UUID):
                alert_ids.append(raw_id)
            else:
                alert_ids.append(uuid.UUID(str(raw_id)))

        first_seen = _get_timestamp(comp_alerts[0])
        last_seen = _get_timestamp(comp_alerts[-1])

        source_ips = sorted(list({str(_get_attr(a, "source_ip", "")).strip() for a in comp_alerts if _get_attr(a, "source_ip", "")}))
        destination_ips = sorted(list({str(_get_attr(a, "destination_ip", "")).strip() for a in comp_alerts if _get_attr(a, "destination_ip", "")}))
        attack_types = sorted(list({str(_get_attr(a, "attack_type", "")).strip() for a in comp_alerts if _get_attr(a, "attack_type", "")}))

        risk_score, risk_factors = calculate_deterministic_risk_score(comp_alerts)

        # Generate deterministic incident_id using uuid5 over sorted alert IDs
        sorted_id_strs = sorted([str(aid) for aid in alert_ids])
        incident_id = uuid.uuid5(uuid.NAMESPACE_URL, f"incident:{','.join(sorted_id_strs)}")

        incidents.append(
            IncidentResponse(
                incident_id=incident_id,
                alert_count=len(comp_alerts),
                first_seen=first_seen,
                last_seen=last_seen,
                source_ips=source_ips,
                destination_ips=destination_ips,
                attack_types=attack_types,
                risk_score=risk_score,
                risk_factors=risk_factors,
                alert_ids=alert_ids,
            )
        )

    # Sort incidents deterministically: primary risk_score desc, secondary first_seen desc, tertiary incident_id asc
    incidents.sort(
        key=lambda inc: (-inc.risk_score, -inc.first_seen.timestamp(), str(inc.incident_id))
    )

    return incidents
