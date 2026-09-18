"""Tests for the Stage 2 traditional IDS components."""

import sys
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.ids import api
from app.ids.feature_preparation import prepare_features
from app.ids.model import build_model_pipeline, load_model, save_model
from app.ids.prediction import predict_flow
from app.ids.validation import DataValidationError, validate_and_clean_dataset
from app.main import app

@pytest.fixture
def sample_data() -> pd.DataFrame:
    return pd.DataFrame({"Flow Duration": [1, 2, 3, 4, 5, 6, 7, 8], "Protocol": [6, 6, 17, 17, 6, 6, 17, 17], "Service": ["http", "http", "dns", "dns", "http", "http", "dns", "dns"], "Label": ["BENIGN", "BENIGN", "BENIGN", "BENIGN", "PortScan", "PortScan", "PortScan", "PortScan"]})

def fitted_model(sample_data: pd.DataFrame):
    cleaned, _ = validate_and_clean_dataset(sample_data)
    dataset = prepare_features(cleaned)
    model = build_model_pipeline(dataset.features)
    return model.fit(dataset.features, dataset.target)

def test_preprocessing_handles_missing_and_categorical_values(sample_data: pd.DataFrame) -> None:
    sample_data.loc[0, "Flow Duration"] = None
    model = fitted_model(sample_data)
    assert len(model.predict(prepare_features(sample_data).features)) == len(sample_data)

def test_validation_rejects_missing_label(sample_data: pd.DataFrame) -> None:
    with pytest.raises(DataValidationError, match="Label"):
        validate_and_clean_dataset(sample_data.drop(columns="Label"))

def test_saved_model_loads_and_predicts(tmp_path: Path, sample_data: pd.DataFrame) -> None:
    artifact = tmp_path / "ids.joblib"
    save_model(fitted_model(sample_data), artifact)
    result = predict_flow(load_model(artifact), {"Flow Duration": 2, "Protocol": 6, "Service": "http"})
    assert result["prediction"] in {"BENIGN", "PortScan"}
    assert 0 <= result["confidence"] <= 1

def test_prediction_endpoint_success(monkeypatch, sample_data: pd.DataFrame) -> None:
    monkeypatch.setattr(api, "load_model", lambda _: fitted_model(sample_data))
    response = TestClient(app).post("/ids/predict", json={"features": {"Flow Duration": 2, "Protocol": 6, "Service": "http"}})
    assert response.status_code == 200
    assert set(response.json()) == {"prediction", "confidence", "severity"}

def test_prediction_endpoint_handles_missing_model() -> None:
    response = TestClient(app).post("/ids/predict", json={"features": {"Flow Duration": 1}})
    assert response.status_code == 503

def test_prediction_endpoint_rejects_empty_features() -> None:
    assert TestClient(app).post("/ids/predict", json={"features": {}}).status_code == 422
