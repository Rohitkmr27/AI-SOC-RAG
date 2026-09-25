import sys
import os
from datetime import datetime, timezone
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.alerts.models import Base, Alert, AlertSeverity, AlertStatus
from app.rag.alert_enrichment import enrich_alert
from app.rag.llm import GeminiProvider

def run_enrichment_smoke_test():
    print("Testing Alert Enrichment with SQLite FTS5 Retrieval...")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    alert = Alert(
        timestamp=datetime.now(timezone.utc),
        source_ip="192.168.10.50",
        destination_ip="172.16.0.1",
        source_port=49459,
        destination_port=80,
        protocol="TCP",
        attack_type="DDoS",
        confidence=0.98,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.NEW,
        description="DDoS attack detected on flow 192.168.10.50:49459 -> 172.16.0.1:80 via TCP",
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n--- TEST TASK 19: Missing GEMINI_API_KEY ---")
        try:
            enrich_alert(alert)
            print("ERROR: Should have raised RuntimeError for missing API key")
        except RuntimeError as exc:
            print(f"SUCCESS: Caught expected RuntimeError when GEMINI_API_KEY missing:\n  {exc}")
    else:
        print("\n--- TEST TASK 18: Real Gemini API Call with FTS5 Retrieval ---")
        analysis, sources = enrich_alert(alert)
        print("Summary:", analysis.summary)
        print("Observed Indicators:", analysis.observed_indicators)
        print("Security Context:", analysis.security_context)
        print("Investigation Steps:", analysis.investigation_steps)
        print("Recommended Mitigations:", analysis.recommended_mitigations)
        print(f"Retrieved Sources ({len(sources)}):")
        for s in sources:
            print(f"  - [{s.source}] {s.file_name} (Score: {s.score})")

if __name__ == "__main__":
    run_enrichment_smoke_test()
