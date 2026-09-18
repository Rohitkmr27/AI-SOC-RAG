"""Actual held-out IDS model evaluation."""

import json
from pathlib import Path
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline

def evaluate_model(model: Pipeline, test_features: pd.DataFrame, test_target: pd.Series) -> tuple[dict, pd.DataFrame]:
    """Return accuracy, classification report, per-class metrics, and matrix."""
    predicted = model.predict(test_features)
    labels = sorted(test_target.unique())
    precision, recall, f1, support = precision_recall_fscore_support(test_target, predicted, labels=labels, zero_division=0)
    metrics = {
        "accuracy": accuracy_score(test_target, predicted),
        "classification_report": classification_report(test_target, predicted, labels=labels, output_dict=True, zero_division=0),
        "per_class": {label: {"precision": float(precision[i]), "recall": float(recall[i]), "f1_score": float(f1[i]), "support": int(support[i])} for i, label in enumerate(labels)},
    }
    matrix = pd.DataFrame(confusion_matrix(test_target, predicted, labels=labels), index=labels, columns=labels)
    matrix.index.name, matrix.columns.name = "actual", "predicted"
    return metrics, matrix

def save_evaluation(metrics: dict, matrix: pd.DataFrame, artifact_directory: Path) -> None:
    artifact_directory.mkdir(parents=True, exist_ok=True)
    (artifact_directory / "evaluation_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    matrix.to_csv(artifact_directory / "confusion_matrix.csv")
