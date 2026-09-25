"""Central paths and constants used by the IDS module."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "cicids2017"
DEFAULT_ARTIFACT_DIRECTORY = PROJECT_ROOT / "backend" / "artifacts" / "ids"
MODEL_FILENAME = "cicids2017_random_forest.joblib"
LABEL_COLUMN = "Label"
IDENTIFIER_COLUMNS = {"Flow ID", "Source IP", "Destination IP", "Timestamp", "SimillarHTTP"}

# Project-level triage guidance, not a certified security risk score.
SEVERITY_BY_LABEL = {
    "BENIGN": "Informational", "Bot": "High", "DDoS": "High", "DoS GoldenEye": "High",
    "DoS Hulk": "High", "DoS Slowhttptest": "Medium", "DoS slowloris": "Medium",
    "FTP-Patator": "High", "Heartbleed": "Critical", "Infiltration": "Critical",
    "PortScan": "Medium", "SSH-Patator": "High", "Web Attack - Brute Force": "High",
    "Web Attack - Sql Injection": "Critical", "Web Attack - XSS": "High",
}

# Detection limits and safety controls
MAX_DETECTION_FILE_SIZE_MB = 10
MAX_DETECTION_ROWS = 10000
MAX_DETECTION_RESPONSE_RESULTS = 100

