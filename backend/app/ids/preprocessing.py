"""Leakage-safe feature transformations fitted only during model training."""

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

def identify_feature_types(features: pd.DataFrame) -> tuple[list[str], list[str]]:
    numerical = features.select_dtypes(include=["number", "bool"]).columns.tolist()
    return numerical, [column for column in features.columns if column not in numerical]

def build_preprocessor(features: pd.DataFrame) -> ColumnTransformer:
    """Impute numeric data and one-hot encode observed categorical features."""
    numerical, categorical = identify_feature_types(features)
    transformers = []
    if numerical:
        transformers.append(("numerical", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numerical))
    if categorical:
        transformers.append(("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]), categorical))
    if not transformers:
        raise ValueError("No numerical or categorical features are available.")
    return ColumnTransformer(transformers=transformers, remainder="drop")
