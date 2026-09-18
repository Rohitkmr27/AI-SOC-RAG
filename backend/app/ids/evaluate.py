"""Re-evaluate a saved IDS model against the deterministic held-out split."""

import argparse
import json
from pathlib import Path
from app.ids.config import DEFAULT_ARTIFACT_DIRECTORY, DEFAULT_DATA_DIRECTORY, MODEL_FILENAME
from app.ids.data_loading import load_dataset
from app.ids.evaluation import evaluate_model, save_evaluation
from app.ids.feature_preparation import prepare_features, stratified_split
from app.ids.model import load_model
from app.ids.validation import validate_and_clean_dataset

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained CIC-IDS2017 IDS.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIRECTORY)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIRECTORY)
    arguments = parser.parse_args()
    cleaned, _ = validate_and_clean_dataset(load_dataset(arguments.data_dir))
    dataset = prepare_features(cleaned)
    _, test_x, _, test_y = stratified_split(dataset.features, dataset.target)
    metrics, matrix = evaluate_model(load_model(arguments.artifact_dir / MODEL_FILENAME), test_x, test_y)
    save_evaluation(metrics, matrix, arguments.artifact_dir)
    print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()
