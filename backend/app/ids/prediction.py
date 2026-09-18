"""Reusable model-derived IDS predictions and transparent triage severity."""

from typing import Any
import pandas as pd
from sklearn.pipeline import Pipeline
from app.ids.config import SEVERITY_BY_LABEL


def normalize_attack_label(label: str) -> str:
    """Normalize known CIC-IDS2017 encoding variants for display and mapping only."""
    normalized = label.replace("\ufffd", "-").replace("ï¿½", "-")
    normalized = " ".join(normalized.split())
    return normalized

def severity_for_prediction(label: str, confidence: float) -> str:
    """Project-only severity: uncertain malicious predictions are low priority."""
    if label != "BENIGN" and confidence < 0.60:
        return "Low"
    return SEVERITY_BY_LABEL.get(label, "Medium")

def predict_flow(model: Pipeline, flow_features: dict[str, Any]) -> dict[str, str | float]:
    features = pd.DataFrame([flow_features])
    prediction = normalize_attack_label(str(model.predict(features)[0]))
    confidence = float(model.predict_proba(features).max()) if hasattr(model, "predict_proba") else 0.0
    return {"prediction": prediction, "confidence": round(confidence, 4), "severity": severity_for_prediction(prediction, confidence)}
