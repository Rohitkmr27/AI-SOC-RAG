import io
import logging
import re
from collections import Counter
from typing import Any
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from app.auth.dependencies import get_current_user
from app.ids.config import (
    DEFAULT_ARTIFACT_DIRECTORY,
    MAX_DETECTION_FILE_SIZE_MB,
    MAX_DETECTION_RESPONSE_RESULTS,
    MAX_DETECTION_ROWS,
    MODEL_FILENAME,
)
from app.ids.model import load_model
from app.ids.prediction import predict_flow, predict_flows

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ids", tags=["ids"], dependencies=[Depends(get_current_user)])

class FlowPredictionRequest(BaseModel):
    """Feature keys must exactly match the columns used when training."""
    features: dict[str, Any] = Field(min_length=1)

class FlowPredictionResponse(BaseModel):
    prediction: str
    confidence: float
    severity: str

class FlowResult(BaseModel):
    row_index: int
    prediction: str
    confidence: float
    severity: str

class CsvDetectionResponse(BaseModel):
    total_flows: int
    normal_flows: int
    anomalies: int
    attack_types: dict[str, int]
    severity_counts: dict[str, int]
    results: list[FlowResult]

def _extract_csv_payload(raw_body: bytes, content_type: str) -> bytes:
    """Extract CSV file payload from multipart/form-data or raw request body."""
    if "multipart/form-data" in content_type:
        header_end = raw_body.find(b"\r\n\r\n")
        delimiter_len = 4
        if header_end == -1:
            header_end = raw_body.find(b"\n\n")
            delimiter_len = 2

        if header_end != -1:
            headers_part = raw_body[:header_end].decode("utf-8", errors="replace")
            fn_match = re.search(r'filename=["\']?([^"\'\r\n;]+)', headers_part, re.IGNORECASE)
            if fn_match:
                filename = fn_match.group(1).strip()
                if not filename.lower().endswith(".csv"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="File must be a CSV file with a .csv extension."
                    )
            else:
                # If name="file" is present without filename or invalid extension
                if 'name=' in headers_part and 'filename=' not in headers_part:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="File must be a CSV file with a .csv extension."
                    )

            payload = raw_body[header_end + delimiter_len:]
            boundary_idx = payload.rfind(b"\r\n--")
            if boundary_idx != -1:
                payload = payload[:boundary_idx]
            else:
                boundary_idx = payload.rfind(b"\n--")
                if boundary_idx != -1:
                    payload = payload[:boundary_idx]
            return payload.strip()

    return raw_body.strip()

@router.post("/predict", response_model=FlowPredictionResponse)
async def predict(request: FlowPredictionRequest) -> FlowPredictionResponse:
    try:
        result = predict_flow(load_model(DEFAULT_ARTIFACT_DIRECTORY / MODEL_FILENAME), request.features)
        return FlowPredictionResponse(**result)
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (ValueError, KeyError, TypeError) as error:
        logger.info("Invalid IDS prediction request: %s", error)
        raise HTTPException(status_code=422, detail="Features do not match the model's expected training schema.") from error

@router.post("/detect-csv", response_model=CsvDetectionResponse)
async def detect_csv(request: Request) -> CsvDetectionResponse:
    """Analyze a batch of network flows supplied as a CSV file.
    
    Accepts multipart/form-data CSV file or raw CSV body.
    Performs memory-safe batch detection using the cached trained IDS model.
    Does not automatically write to the database or trigger RAG/LLM.
    """
    content_type = request.headers.get("content-type", "").lower()

    try:
        raw_body = await request.body()
    except Exception as exc:
        logger.error("Failed to read uploaded request body: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded file content."
        ) from exc

    if not raw_body or len(raw_body.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV file is empty."
        )

    max_bytes = MAX_DETECTION_FILE_SIZE_MB * 1024 * 1024
    if len(raw_body) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed limit of {MAX_DETECTION_FILE_SIZE_MB}MB."
        )

    csv_bytes = _extract_csv_payload(raw_body, content_type)

    if not csv_bytes or len(csv_bytes.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV file is empty."
        )

    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        logger.warning("Invalid CSV format uploaded: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid or readable CSV."
        ) from exc

    if df.empty or len(df) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV contains no data rows."
        )

    if len(df) > MAX_DETECTION_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV row count ({len(df)}) exceeds maximum allowed limit of {MAX_DETECTION_ROWS} rows."
        )

    try:
        model = load_model(DEFAULT_ARTIFACT_DIRECTORY / MODEL_FILENAME)
    except FileNotFoundError as exc:
        logger.error("IDS model artifact missing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trained IDS model is unavailable."
        ) from exc

    try:
        batch_results = predict_flows(df, model=model)
    except (ValueError, KeyError, TypeError) as exc:
        logger.info("CSV batch prediction feature schema mismatch: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV feature columns do not match the model's expected training schema."
        ) from exc

    total_flows = len(batch_results)
    normal_flows = sum(1 for r in batch_results if r["prediction"] == "BENIGN")
    anomalies = total_flows - normal_flows

    attack_types = dict(Counter(r["prediction"] for r in batch_results if r["prediction"] != "BENIGN"))
    severity_counts = dict(Counter(r["severity"] for r in batch_results))

    anomalous_results = [r for r in batch_results if r["prediction"] != "BENIGN"]
    if anomalous_results:
        results_sample = anomalous_results[:MAX_DETECTION_RESPONSE_RESULTS]
    else:
        results_sample = batch_results[:MAX_DETECTION_RESPONSE_RESULTS]

    formatted_results = [FlowResult(**r) for r in results_sample]

    return CsvDetectionResponse(
        total_flows=total_flows,
        normal_flows=normal_flows,
        anomalies=anomalies,
        attack_types=attack_types,
        severity_counts=severity_counts,
        results=formatted_results,
    )


