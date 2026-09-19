"""Pydantic request and response schemas for alert APIs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, field_validator

from app.alerts.models import AlertSeverity, AlertStatus
from app.rag.schemas import RAGSource


class AlertBase(BaseModel):
    timestamp: datetime
    source_ip: IPvAnyAddress
    destination_ip: IPvAnyAddress
    source_port: int = Field(ge=0, le=65535)
    destination_port: int = Field(ge=0, le=65535)
    protocol: str = Field(min_length=1, max_length=20)
    attack_type: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)
    severity: AlertSeverity
    description: str = Field(min_length=1, max_length=5000)

    @field_validator("protocol", "attack_type", "description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank.")
        return value


class AlertCreate(AlertBase):
    status: AlertStatus = AlertStatus.NEW


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    severity: AlertSeverity | None = None
    description: str | None = Field(default=None, min_length=1, max_length=5000)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return AlertBase.strip_required_text(value) if value is not None else value


class AlertResponse(AlertBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: AlertStatus
    created_at: datetime
    updated_at: datetime


class IdsAlertCreate(BaseModel):
    """Network metadata plus feature schema required by the trained IDS pipeline."""
    timestamp: datetime
    source_ip: IPvAnyAddress
    destination_ip: IPvAnyAddress
    source_port: int = Field(ge=0, le=65535)
    destination_port: int = Field(ge=0, le=65535)
    protocol: str = Field(min_length=1, max_length=20)
    features: dict[str, object] = Field(min_length=1)


class AlertAnalysis(BaseModel):
    """Structured security analysis generated from retrieved cybersecurity knowledge."""
    summary: str
    observed_indicators: list[str] = Field(default_factory=list)
    security_context: list[str] = Field(default_factory=list)
    investigation_steps: list[str] = Field(default_factory=list)
    recommended_mitigations: list[str] = Field(default_factory=list)


class AlertEnrichmentResponse(BaseModel):
    """Response containing original alert details, grounded analysis, and retrieved sources."""
    alert: AlertResponse
    analysis: AlertAnalysis
    sources: list[RAGSource] = Field(default_factory=list)
