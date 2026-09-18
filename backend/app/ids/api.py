"""FastAPI routes exposing the trained traditional IDS."""

import logging
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.ids.config import DEFAULT_ARTIFACT_DIRECTORY, MODEL_FILENAME
from app.ids.model import load_model
from app.ids.prediction import predict_flow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ids", tags=["ids"])

class FlowPredictionRequest(BaseModel):
    """Feature keys must exactly match the columns used when training."""
    features: dict[str, Any] = Field(min_length=1)

class FlowPredictionResponse(BaseModel):
    prediction: str
    confidence: float
    severity: str

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
