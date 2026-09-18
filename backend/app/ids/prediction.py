"""Reusable model-derived IDS predictions and transparent triage severity."""

from typing import Any
import pandas as pd
from sklearn.pipeline import Pipeline
from app.ids.config import SEVERITY_BY_LABEL

def severity_for_prediction(label: str, confidence: float) -> str:
    """Project-only severity: uncertain malicious predictions are low priority."""
    if label != "BENIGN" and confidence < 0.60:
        return "Low"
    return SEVERITY_BY_LABEL.get(label, "Medium")

def predict_flow(model: Pipeline, flow_features: dict[str, Any]) -> dict[str, str | float]:
    features = pd.DataFrame([flow_features])
    prediction = str(model.predict(features)[0])
    confidence = float(model.predict_proba(features).max()) if hasattr(model, "predict_proba") else 0.0
    return {"prediction": prediction, "confidence": round(confidence, 4), "severity": severity_for_prediction(prediction, confidence)}
