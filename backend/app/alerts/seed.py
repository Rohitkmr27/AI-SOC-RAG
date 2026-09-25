"""Database seeding utility for SOC alert telemetry and correlation testing."""

from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.orm import Session

from app.alerts.models import Alert, AlertSeverity, AlertStatus
from app.database import SessionLocal


SAMPLE_ALERTS = [
    {
        "minutes_ago": 15,
        "source_ip": "192.168.1.105",
        "destination_ip": "10.0.0.15",
        "source_port": 49152,
        "destination_port": 443,
        "protocol": "TCP",
        "attack_type": "PortScan",
        "confidence": 0.92,
        "severity": AlertSeverity.HIGH,
        "status": AlertStatus.NEW,
        "description": "Sequential TCP SYN port sweep detected across multiple high ports.",
    },
    {
        "minutes_ago": 10,
        "source_ip": "192.168.1.105",
        "destination_ip": "10.0.0.15",
        "source_port": 51200,
        "destination_port": 22,
        "protocol": "TCP",
        "attack_type": "SSH-Bruteforce",
        "confidence": 0.96,
        "severity": AlertSeverity.CRITICAL,
        "status": AlertStatus.INVESTIGATING,
        "description": "High frequency failed SSH authentication attempts detected from 192.168.1.105.",
    },
    {
        "minutes_ago": 25,
        "source_ip": "185.220.101.4",
        "destination_ip": "10.0.0.8",
        "source_port": 8080,
        "destination_port": 80,
        "protocol": "TCP",
        "attack_type": "DDoS-HTTP-Flood",
        "confidence": 0.89,
        "severity": AlertSeverity.CRITICAL,
        "status": AlertStatus.NEW,
        "description": "High volume HTTP requests per second threshold exceeded targeting web gateway.",
    },
    {
        "minutes_ago": 30,
        "source_ip": "45.33.32.156",
        "destination_ip": "10.0.0.12",
        "source_port": 34120,
        "destination_port": 443,
        "protocol": "TCP",
        "attack_type": "SqlInjection",
        "confidence": 0.85,
        "severity": AlertSeverity.HIGH,
        "status": AlertStatus.TRIAGED,
        "description": "SQL syntax pattern detected in HTTP POST body payload.",
    },
    {
        "minutes_ago": 45,
        "source_ip": "198.51.100.44",
        "destination_ip": "10.0.0.20",
        "source_port": 55432,
        "destination_port": 8080,
        "protocol": "TCP",
        "attack_type": "Botnet-C2",
        "confidence": 0.78,
        "severity": AlertSeverity.HIGH,
        "status": AlertStatus.INVESTIGATING,
        "description": "Outbound periodic beaconing traffic matched known command and control IP signature.",
    },
    {
        "minutes_ago": 5,
        "source_ip": "203.0.113.12",
        "destination_ip": "10.0.0.12",
        "source_port": 61234,
        "destination_port": 80,
        "protocol": "TCP",
        "attack_type": "Web-XSS",
        "confidence": 0.74,
        "severity": AlertSeverity.MEDIUM,
        "status": AlertStatus.NEW,
        "description": "Cross-site scripting script tag detected in user parameter string.",
    },
    {
        "minutes_ago": 55,
        "source_ip": "192.168.1.200",
        "destination_ip": "10.0.0.2",
        "source_port": 1234,
        "destination_port": 53,
        "protocol": "UDP",
        "attack_type": "DNS-Tunneling",
        "confidence": 0.81,
        "severity": AlertSeverity.MEDIUM,
        "status": AlertStatus.RESOLVED,
        "description": "Anomalous DNS query payload length exceeding baseline network standard.",
    },
    {
        "minutes_ago": 2,
        "source_ip": "192.168.1.105",
        "destination_ip": "10.0.0.18",
        "source_port": 52100,
        "destination_port": 445,
        "protocol": "TCP",
        "attack_type": "SMB-Probe",
        "confidence": 0.88,
        "severity": AlertSeverity.HIGH,
        "status": AlertStatus.NEW,
        "description": "Lateral movement probe targeting Windows SMB file share port 445.",
    },
]


def seed_alerts(session: Session) -> List[Alert]:
    """Seed sample security alerts into PostgreSQL database."""
    now = datetime.now(timezone.utc)
    created_alerts = []

    for sample in SAMPLE_ALERTS:
        timestamp = now - timedelta(minutes=sample["minutes_ago"])
        alert = Alert(
            timestamp=timestamp,
            source_ip=sample["source_ip"],
            destination_ip=sample["destination_ip"],
            source_port=sample["source_port"],
            destination_port=sample["destination_port"],
            protocol=sample["protocol"],
            attack_type=sample["attack_type"],
            confidence=sample["confidence"],
            severity=sample["severity"],
            status=sample["status"],
            description=sample["description"],
        )
        session.add(alert)
        created_alerts.append(alert)

    session.commit()
    for alert in created_alerts:
        session.refresh(alert)

    return created_alerts


if __name__ == "__main__":
    session = SessionLocal()
    try:
        alerts = seed_alerts(session)
        print(f"Successfully seeded {len(alerts)} sample alerts into database.")
    finally:
        session.close()
