"""Validation and cleaning routines for raw IDS data."""

from dataclasses import dataclass
import numpy as np
import pandas as pd
from app.ids.config import LABEL_COLUMN

class DataValidationError(ValueError):
    """Raised when data cannot be used for supervised IDS training."""

@dataclass(frozen=True)
class CleaningReport:
    input_rows: int
    duplicate_rows_removed: int
    rows_without_label_removed: int
    output_rows: int

def validate_and_clean_dataset(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Normalize labels, replace infinities, and remove unusable records."""
    if dataframe.empty:
        raise DataValidationError("The dataset contains no rows.")
    dataframe = dataframe.copy()
    dataframe.columns = dataframe.columns.astype(str).str.strip()
    if LABEL_COLUMN not in dataframe.columns:
        raise DataValidationError(f"Expected target column '{LABEL_COLUMN}' was not found. Available columns: {list(dataframe.columns)}")
    dataframe[LABEL_COLUMN] = dataframe[LABEL_COLUMN].astype("string").str.strip()
    dataframe = dataframe.replace([np.inf, -np.inf], np.nan)
    input_rows = len(dataframe)
    dataframe = dataframe.drop_duplicates().reset_index(drop=True)
    duplicates = input_rows - len(dataframe)
    before_labels = len(dataframe)
    dataframe = dataframe.dropna(subset=[LABEL_COLUMN])
    dataframe = dataframe.loc[dataframe[LABEL_COLUMN] != ""].reset_index(drop=True)
    missing_labels = before_labels - len(dataframe)
    if dataframe[LABEL_COLUMN].nunique() < 2:
        raise DataValidationError("At least two target classes are required for training.")
    return dataframe, CleaningReport(input_rows, duplicates, missing_labels, len(dataframe))
