"""Tests for the Stage 2 traditional IDS components."""

import sys
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.ids import api
from app.ids.feature_preparation import prepare_features
from app.ids.model import build_model_pipeline, load_model, save_model
from app.ids.prediction import predict_flow
from app.ids.validation import DataValidationError, validate_and_clean_dataset
from app.main import app

mock_analyst = User(
    username="test_analyst",
    role=UserRole.ANALYST,
    is_active=True,
)


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: mock_analyst
    yield
    app.dependency_overrides.clear()


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

def test_prediction_strips_dataset_header_whitespace(sample_data: pd.DataFrame) -> None:
    model = fitted_model(sample_data)
    result = predict_flow(model, {" Flow Duration": 2, " Protocol": 6, " Service": "http"})
    assert result["prediction"] in {"BENIGN", "PortScan"}

def test_prediction_endpoint_success(monkeypatch, sample_data: pd.DataFrame) -> None:
    monkeypatch.setattr(api, "load_model", lambda _: fitted_model(sample_data))
    response = TestClient(app).post("/ids/predict", json={"features": {"Flow Duration": 2, "Protocol": 6, "Service": "http"}})
    assert response.status_code == 200
    assert set(response.json()) == {"prediction", "confidence", "severity"}

def test_prediction_endpoint_handles_missing_model(monkeypatch) -> None:
    def missing_model(_):
        raise FileNotFoundError("model missing")

    monkeypatch.setattr(api, "load_model", missing_model)
    response = TestClient(app).post("/ids/predict", json={"features": {"Flow Duration": 1}})
    assert response.status_code == 503

from app.ids.prediction import predict_flow, predict_flows

def test_prediction_endpoint_rejects_empty_features() -> None:
    assert TestClient(app).post("/ids/predict", json={"features": {}}).status_code == 422

def test_model_caching_returns_same_instance(tmp_path: Path, sample_data: pd.DataFrame) -> None:
    artifact = tmp_path / "cached_ids.joblib"
    save_model(fitted_model(sample_data), artifact)
    load_model.cache_clear()
    m1 = load_model(artifact)
    m2 = load_model(artifact)
    assert m1 is m2

def test_predict_flows_batch_inference(sample_data: pd.DataFrame) -> None:
    model = fitted_model(sample_data)
    df_input = pd.DataFrame([
        {"Flow Duration": 2, "Protocol": 6, "Service": "http"},
        {"Flow Duration": 6, "Protocol": 6, "Service": "http"},
    ])
    results = predict_flows(df_input, model=model)
    assert len(results) == 2
    assert results[0]["row_index"] == 0
    assert results[1]["row_index"] == 1
    assert "prediction" in results[0]
    assert "confidence" in results[0]
    assert "severity" in results[0]

def test_detect_csv_endpoint_success(monkeypatch, sample_data: pd.DataFrame) -> None:
    monkeypatch.setattr(api, "load_model", lambda _: fitted_model(sample_data))
    csv_content = "Flow Duration,Protocol,Service\n2,6,http\n6,6,http\n"
    response = TestClient(app).post(
        "/ids/detect-csv",
        files={"file": ("flows.csv", csv_content, "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_flows"] == 2
    assert "normal_flows" in data
    assert "anomalies" in data
    assert "attack_types" in data
    assert "severity_counts" in data
    assert len(data["results"]) <= 100

def test_detect_csv_endpoint_empty_file() -> None:
    response = TestClient(app).post(
        "/ids/detect-csv",
        files={"file": ("empty.csv", "", "text/csv")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_detect_csv_endpoint_invalid_file_type() -> None:
    response = TestClient(app).post(
        "/ids/detect-csv",
        files={"file": ("data.txt", "some content", "text/plain")}
    )
    assert response.status_code == 400
    assert "must be a csv file" in response.json()["detail"].lower()

def test_detect_csv_endpoint_missing_feature_columns(monkeypatch, sample_data: pd.DataFrame) -> None:
    monkeypatch.setattr(api, "load_model", lambda _: fitted_model(sample_data))
    csv_content = "UnknownFeature1,UnknownFeature2\n123,456\n"
    response = TestClient(app).post(
        "/ids/detect-csv",
        files={"file": ("invalid_features.csv", csv_content, "text/csv")}
    )
    assert response.status_code in {400, 422}

def test_detect_csv_endpoint_excessive_rows(monkeypatch) -> None:
    monkeypatch.setattr("app.ids.api.MAX_DETECTION_ROWS", 2)
    csv_content = "Flow Duration,Protocol\n1,6\n2,6\n3,6\n"
    response = TestClient(app).post(
        "/ids/detect-csv",
        files={"file": ("large.csv", csv_content, "text/csv")}
    )
    assert response.status_code == 400
    assert "exceeds maximum" in response.json()["detail"].lower()

def test_detect_csv_endpoint_unauthenticated() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)
    response = client.post(
        "/ids/detect-csv",
        files={"file": ("test.csv", "Flow Duration\n1\n", "text/csv")}
    )
    assert response.status_code == 401

