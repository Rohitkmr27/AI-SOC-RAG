"""Command-line training entry point for CIC-IDS2017."""

import argparse
import json
import logging
from pathlib import Path
from app.ids.config import DEFAULT_ARTIFACT_DIRECTORY, DEFAULT_DATA_DIRECTORY, MODEL_FILENAME
from app.ids.data_loading import load_dataset
from app.ids.evaluation import evaluate_model, save_evaluation
from app.ids.feature_preparation import prepare_features, stratified_split
from app.ids.model import build_model_pipeline, save_model
from app.ids.validation import validate_and_clean_dataset

def main() -> None:
    parser = argparse.ArgumentParser(description="Train CIC-IDS2017 Random Forest IDS.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIRECTORY)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIRECTORY)
    parser.add_argument("--test-size", type=float, default=0.2)
    arguments = parser.parse_args()
    cleaned, cleaning = validate_and_clean_dataset(load_dataset(arguments.data_dir))
    dataset = prepare_features(cleaned)
    train_x, test_x, train_y, test_y = stratified_split(dataset.features, dataset.target, arguments.test_size)
    model = build_model_pipeline(train_x)
    logging.info("Training Random Forest on %d records", len(train_x))
    model.fit(train_x, train_y)
    save_model(model, arguments.artifact_dir / MODEL_FILENAME)
    metrics, matrix = evaluate_model(model, test_x, test_y)
    save_evaluation(metrics, matrix, arguments.artifact_dir)
    summary = {"cleaning": cleaning.__dict__, "dropped_identifier_columns": dataset.dropped_columns, "train_rows": len(train_x), "test_rows": len(test_x), "accuracy": metrics["accuracy"]}
    arguments.artifact_dir.mkdir(parents=True, exist_ok=True)
    (arguments.artifact_dir / "training_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Saved model and actual evaluation to: {arguments.artifact_dir}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
