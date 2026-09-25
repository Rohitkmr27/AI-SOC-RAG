import sys
import os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

backend_dir = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.alerts.models import Base, Alert
from app.alerts.service import create_alerts_from_predictions
from app.alerts.correlation import correlate_alerts
from app.rag.incident_investigation import investigate_incident
from app.ids.model import load_model
from app.ids.config import DEFAULT_ARTIFACT_DIRECTORY, MODEL_FILENAME
from app.ids.prediction import predict_flows

def run_incident_smoke_test():
    print("Initializing isolated SQLite test database...")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    csv_path = Path("data/raw/cicids2017/MachineLearningCVE/Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv")
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        return

    print("Loading 50 real DDoS flows from row 18883...")
    df_ddos = pd.read_csv(csv_path, skiprows=range(1, 18883), nrows=50)

    model = load_model(DEFAULT_ARTIFACT_DIRECTORY / MODEL_FILENAME)
    batch_results = predict_flows(df_ddos, model=model)

    alerts, dupes = create_alerts_from_predictions(session, batch_results, df_ddos)
    print(f"Created {len(alerts)} alerts in DB.")

    all_alerts = session.query(Alert).all()
    incidents = correlate_alerts(all_alerts)
    print(f"Correlated {len(incidents)} incident campaign(s).")

    if not incidents:
        print("Error: No incidents correlated")
        return

    target_inc = incidents[0]
    print(f"Incident ID: {target_inc.incident_id}")
    print(f"Alert Count: {target_inc.alert_count}")
    print(f"Risk Score: {target_inc.risk_score} / 100")
    print(f"Risk Factors: {target_inc.risk_factors}")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n--- TEST: Missing GEMINI_API_KEY ---")
        try:
            investigate_incident(target_inc)
            print("ERROR: Should have raised RuntimeError for missing API key")
        except RuntimeError as exc:
            print(f"SUCCESS: Caught expected RuntimeError when GEMINI_API_KEY missing:\n  {exc}")
    else:
        print("\n--- TEST: Real Gemini Incident Investigation with SQLite FTS5 ---")
        investigation, sources = investigate_incident(target_inc)
        print("Executive Summary:", investigation.executive_summary)
        print("Observed Evidence:", investigation.observed_evidence)
        print("Threat Context:", investigation.threat_context)
        print("Investigation Priorities:", investigation.investigation_priorities)
        print("Recommended Actions:", investigation.recommended_actions)
        print("Mitigations:", investigation.mitigations)
        print(f"Retrieved Sources ({len(sources)}):")
        for s in sources:
            print(f"  - [{s.source}] {s.file_name} (Score: {s.score})")

        # Module check assertion
        assert 'sentence_transformers' not in sys.modules
        assert 'torch' not in sys.modules
        assert 'qdrant_client' not in sys.modules
        print("\nSUCCESS: Verified ZERO heavy PyTorch/Qdrant modules loaded during incident investigation!")

if __name__ == "__main__":
    run_incident_smoke_test()
