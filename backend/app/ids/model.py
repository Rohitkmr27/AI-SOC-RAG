"""Baseline model creation and persistence."""

from pathlib import Path
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from app.ids.preprocessing import build_preprocessor

def build_model_pipeline(training_features: pd.DataFrame) -> Pipeline:
    """Build an imbalance-aware conventional Random Forest baseline."""
    return Pipeline([
        ("preprocessor", build_preprocessor(training_features)),
        ("classifier", RandomForestClassifier(n_estimators=100, class_weight="balanced_subsample", n_jobs=-1, random_state=42)),
    ])

def save_model(model: Pipeline, artifact_path: Path) -> None:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_path)

def load_model(artifact_path: Path) -> Pipeline:
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Trained IDS model was not found at {artifact_path}. Run training first.")
    return joblib.load(artifact_path)
