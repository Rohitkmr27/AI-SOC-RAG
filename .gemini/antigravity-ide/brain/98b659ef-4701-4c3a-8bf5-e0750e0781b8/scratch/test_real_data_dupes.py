import sys
from pathlib import Path
import pandas as pd

backend_dir = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.alerts.models import Base, Alert
from app.alerts.service import create_alerts_from_predictions
from app.ids.model import load_model
from app.ids.config import DEFAULT_ARTIFACT_DIRECTORY, MODEL_FILENAME
from app.ids.prediction import predict_flows

def run_real_data_duplicate_test():
    print("Initializing isolated SQLite test database...")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    csv_path = Path("data/raw/cicids2017/MachineLearningCVE/Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv")
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        return

    print("Loading 50 real DDoS flows starting at row 18883...")
    df_ddos = pd.read_csv(csv_path, skiprows=range(1, 18883), nrows=50)

    print("Loading cached Random Forest model...")
    model = load_model(DEFAULT_ARTIFACT_DIRECTORY / MODEL_FILENAME)

    print(f"Running batch prediction on {len(df_ddos)} flows...")
    batch_results = predict_flows(df_ddos, model=model)

    total_flows = len(batch_results)
    attacks_detected = sum(1 for r in batch_results if r["prediction"] != "BENIGN")

    print(f"\n--- UPLOAD #1 ---")
    alerts_1, dupes_1 = create_alerts_from_predictions(session, batch_results, df_ddos)
    db_count_1 = session.query(Alert).count()
    print(f"Flows processed: {total_flows}")
    print(f"Attacks detected: {attacks_detected}")
    print(f"Alerts created: {len(alerts_1)}")
    print(f"Duplicates skipped: {dupes_1}")
    print(f"Database row count: {db_count_1}")

    print(f"\n--- UPLOAD #2 (Exact Same CSV Input) ---")
    alerts_2, dupes_2 = create_alerts_from_predictions(session, batch_results, df_ddos)
    db_count_2 = session.query(Alert).count()
    print(f"Flows processed: {total_flows}")
    print(f"Attacks detected: {attacks_detected}")
    print(f"Alerts created: {len(alerts_2)}")
    print(f"Duplicates skipped: {dupes_2}")
    print(f"Database row count: {db_count_2}")

if __name__ == "__main__":
    run_real_data_duplicate_test()
