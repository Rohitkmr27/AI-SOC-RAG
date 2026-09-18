"""Dataset discovery and loading for CIC-IDS2017 flow CSV files."""

import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

class DatasetNotFoundError(FileNotFoundError):
    """Raised when no input CSV files can be found."""

def discover_csv_files(data_directory: Path) -> list[Path]:
    if not data_directory.exists():
        raise DatasetNotFoundError(f"Dataset directory does not exist: {data_directory}. Extract MachineLearningCSV.zip there.")
    files = sorted(path for path in data_directory.rglob("*.csv") if path.is_file())
    if not files:
        raise DatasetNotFoundError(f"No CSV files found under {data_directory}. Extract MachineLearningCSV.zip there.")
    return files

def load_dataset(data_directory: Path) -> pd.DataFrame:
    """Load real locally supplied CSV files; never generates records."""
    frames = []
    for csv_file in discover_csv_files(data_directory):
        logger.info("Loading dataset file: %s", csv_file)
        try:
            frame = pd.read_csv(csv_file, low_memory=False)
        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as error:
            raise ValueError(f"Unable to read CSV file {csv_file}: {error}") from error
        frame.columns = frame.columns.astype(str).str.strip()
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False)
