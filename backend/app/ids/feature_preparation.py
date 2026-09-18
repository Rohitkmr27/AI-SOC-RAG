"""Feature selection and reproducible splits for the IDS."""

from dataclasses import dataclass
import pandas as pd
from sklearn.model_selection import train_test_split
from app.ids.config import IDENTIFIER_COLUMNS, LABEL_COLUMN

@dataclass(frozen=True)
class FeatureDataset:
    features: pd.DataFrame
    target: pd.Series
    dropped_columns: list[str]

def prepare_features(dataframe: pd.DataFrame) -> FeatureDataset:
    """Drop label and capture-specific identifiers that risk data leakage."""
    dropped = sorted(set(dataframe.columns).intersection(IDENTIFIER_COLUMNS))
    feature_columns = [c for c in dataframe.columns if c != LABEL_COLUMN and c not in IDENTIFIER_COLUMNS]
    if not feature_columns:
        raise ValueError("No model features remain after removing label and identifiers.")
    return FeatureDataset(dataframe[feature_columns].copy(), dataframe[LABEL_COLUMN].astype(str).copy(), dropped)

def stratified_split(features: pd.DataFrame, target: pd.Series, test_size: float = 0.2, random_state: int = 42):
    """Split without fitting preprocessing on held-out data."""
    if target.value_counts().min() < 2:
        raise ValueError("A class has fewer than two records and cannot be stratified.")
    return train_test_split(features, target, test_size=test_size, random_state=random_state, stratify=target)
