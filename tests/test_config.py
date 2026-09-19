"""Tests for Stage 11.1 Production Configuration & Security Hardening."""

import logging
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.config import (
    DEFAULT_DEV_JWT_SECRET,
    ConfigurationError,
    SensitiveDataFilter,
    get_app_env,
    get_cors_allowed_origins,
    get_jwt_secret_key,
    is_production,
    validate_production_configuration,
)
from app.main import app


def test_development_mode_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert get_app_env() == "development"
    assert not is_production()
    assert get_jwt_secret_key() == DEFAULT_DEV_JWT_SECRET
    origins = get_cors_allowed_origins()
    assert "http://localhost:5173" in origins


def test_production_missing_jwt_secret_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://soc.example.com")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    with pytest.raises(ConfigurationError, match="JWT_SECRET_KEY environment variable must be set"):
        get_jwt_secret_key()

    with pytest.raises(ConfigurationError):
        validate_production_configuration()


def test_production_weak_jwt_secret_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "short_secret_key")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://soc.example.com")

    with pytest.raises(ConfigurationError, match="at least 32 characters long"):
        get_jwt_secret_key()


def test_production_default_jwt_secret_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", DEFAULT_DEV_JWT_SECRET)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://soc.example.com")

    with pytest.raises(ConfigurationError, match="Default development JWT_SECRET_KEY cannot be used"):
        get_jwt_secret_key()


def test_production_valid_jwt_secret_success(monkeypatch: pytest.MonkeyPatch) -> None:
    valid_secret = "a_super_secure_production_secret_key_that_is_long_enough_32bytes"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", valid_secret)

    assert get_jwt_secret_key() == valid_secret


def test_production_cors_wildcard_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    with pytest.raises(ConfigurationError, match=r"Wildcard CORS origin '\*' is strictly prohibited"):
        get_cors_allowed_origins()



def test_production_cors_missing_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(ConfigurationError, match="CORS_ALLOWED_ORIGINS must be explicitly set"):
        get_cors_allowed_origins()


def test_security_headers_present() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert headers["X-XSS-Protection"] == "1; mode=block"


def test_sensitive_data_log_filtering() -> None:
    log_filter = SensitiveDataFilter()

    # Test password redaction
    rec1 = logging.LogRecord("test", logging.INFO, "path", 10, "User login with password=SuperSecretPassword123!", (), None)
    log_filter.filter(rec1)
    assert "SuperSecretPassword123!" not in rec1.msg
    assert "[REDACTED]" in rec1.msg

    # Test database URL credentials redaction
    rec2 = logging.LogRecord("test", logging.INFO, "path", 10, "Connecting to postgresql://admin:SecretPass123@localhost:5432/db", (), None)
    log_filter.filter(rec2)
    assert "SecretPass123" not in rec2.msg

    # Test Bearer token redaction
    rec3 = logging.LogRecord("test", logging.INFO, "path", 10, "Request header Bearer eyJhbGciOiJIUzI1NiJ9.header.signature", (), None)
    log_filter.filter(rec3)
    assert "eyJhbGciOiJIUzI1NiJ9" not in rec3.msg
    assert "[REDACTED_TOKEN]" in rec3.msg
