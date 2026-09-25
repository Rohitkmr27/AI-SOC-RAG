"""Reusable model-derived IDS predictions and transparent triage severity."""

from typing import Any
import pandas as pd
from sklearn.pipeline import Pipeline
from app.ids.config import IDENTIFIER_COLUMNS, LABEL_COLUMN, SEVERITY_BY_LABEL
from app.ids.model import load_model


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


def predict_flows(dataframe: pd.DataFrame, model: Pipeline | None = None) -> list[dict[str, Any]]:
    """Run batch prediction on a DataFrame of flow features.
    
    Returns a list of dicts with keys: row_index, prediction, confidence, severity.
    Preserves row order and does not mutate database or model state.
    """
    if dataframe.empty:
        return []

    if model is None:
        model = load_model()

    features = dataframe.copy()
    features.columns = features.columns.astype(str).str.strip()

    # Drop identifier columns and target label if present
    to_drop = [c for c in features.columns if c in IDENTIFIER_COLUMNS or c == LABEL_COLUMN]
    if to_drop:
        features = features.drop(columns=to_drop)

    if features.empty or features.shape[1] == 0:
        raise ValueError("No valid model feature columns remain after removing identifiers.")

    raw_predictions = model.predict(features)

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(features)
        confidences = probabilities.max(axis=1)
    else:
        confidences = [0.0] * len(features)

    results: list[dict[str, Any]] = []
    for idx, (raw_pred, conf) in enumerate(zip(raw_predictions, confidences)):
        pred_label = normalize_attack_label(str(raw_pred))
        conf_val = round(float(conf), 4)
        sev = severity_for_prediction(pred_label, conf_val)
        results.append({
            "row_index": idx,
            "prediction": pred_label,
            "confidence": conf_val,
            "severity": sev,
        })
    return results


def predict_flow(model: Pipeline, flow_features: dict[str, Any]) -> dict[str, str | float]:
    features = pd.DataFrame([flow_features])
    features.columns = features.columns.astype(str).str.strip()
    prediction = normalize_attack_label(str(model.predict(features)[0]))
    confidence = float(model.predict_proba(features).max()) if hasattr(model, "predict_proba") else 0.0
    return {"prediction": prediction, "confidence": round(confidence, 4), "severity": severity_for_prediction(prediction, confidence)}

