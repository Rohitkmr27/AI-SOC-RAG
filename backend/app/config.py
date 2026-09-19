"""Centralized production-ready application configuration and security validator."""

import logging
import os
import re
from enum import Enum
from typing import Any

DEFAULT_DEV_JWT_SECRET = "ai-soc-rag-dev-jwt-secret-key-32bytesmin"
DEFAULT_DEV_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class ConfigurationError(RuntimeError):
    """Raised when application configuration is missing or insecure."""


def get_app_env() -> str:
    """Retrieve the application environment (development or production)."""
    env = os.getenv("APP_ENV", AppEnvironment.DEVELOPMENT.value).lower().strip()
    if env == AppEnvironment.PRODUCTION.value:
        return AppEnvironment.PRODUCTION.value
    return AppEnvironment.DEVELOPMENT.value


def is_production() -> bool:
    """Check if the application is running in production mode."""
    return get_app_env() == AppEnvironment.PRODUCTION.value


def get_jwt_secret_key() -> str:
    """Retrieve and validate the JWT secret key based on environment.
    
    Raises:
        ConfigurationError: If running in production and key is missing, weak, or using dev default.
    """
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    env = get_app_env()

    if env == AppEnvironment.PRODUCTION.value:
        if not secret:
            raise ConfigurationError("JWT_SECRET_KEY environment variable must be set in production mode.")
        if secret == DEFAULT_DEV_JWT_SECRET:
            raise ConfigurationError("Default development JWT_SECRET_KEY cannot be used in production mode.")
        if len(secret) < 32:
            raise ConfigurationError("JWT_SECRET_KEY must be at least 32 characters long in production mode.")
        return secret

    # Development mode
    if not secret:
        logging.getLogger(__name__).warning(
            "JWT_SECRET_KEY not set in environment. Falling back to development default secret key."
        )
        return DEFAULT_DEV_JWT_SECRET
    return secret


def get_token_expire_minutes() -> int:
    """Retrieve configured access token expiration minutes."""
    raw = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60").strip()
    try:
        val = int(raw)
        if val <= 0:
            return 60
        return val
    except ValueError:
        return 60


def get_cors_allowed_origins() -> list[str]:
    """Retrieve and validate allowed CORS origins based on environment.
    
    Raises:
        ConfigurationError: If production uses wildcard '*' or lacks configured origins.
    """
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    env = get_app_env()

    if raw:
        origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    else:
        origins = []

    if env == AppEnvironment.PRODUCTION.value:
        if not origins:
            raise ConfigurationError("CORS_ALLOWED_ORIGINS must be explicitly set in production mode.")
        if "*" in origins:
            raise ConfigurationError("Wildcard CORS origin '*' is strictly prohibited in production mode.")
        return origins

    # Development mode fallback
    if not origins:
        return DEFAULT_DEV_CORS_ORIGINS
    return origins


def get_database_url() -> str | None:
    """Retrieve the configured PostgreSQL database URL."""
    url = os.getenv("DATABASE_URL", "").strip()
    if is_production() and not url:
        raise ConfigurationError("DATABASE_URL must be configured in production mode.")
    return url if url else None


def get_log_level() -> int:
    """Retrieve configured logging level."""
    raw_level = os.getenv("LOG_LEVEL", "INFO").upper().strip()
    return getattr(logging, raw_level, logging.INFO)


class SensitiveDataFilter(logging.Filter):
    """Logging filter that masks sensitive data such as passwords, JWT secrets, and auth tokens."""

    SENSITIVE_PATTERNS = [
        (re.compile(r"(password=)[^\s&'\"]+", re.IGNORECASE), r"\1[REDACTED]"),
        (re.compile(r"(:[^\s/@:]+@)", re.IGNORECASE), r":****@"),
        (re.compile(r"(Bearer\s+)[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
        (re.compile(r'(access_token["\']?\s*:\s*["\']?)[^"\'\s,]+', re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
        (re.compile(r'(secret["\']?\s*:\s*["\']?)[^"\'\s,]+', re.IGNORECASE), r"\1[REDACTED_SECRET]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        if record.args:
            if isinstance(record.args, dict):
                sanitized_args = {}
                for k, v in record.args.items():
                    if isinstance(v, str):
                        for pattern, replacement in self.SENSITIVE_PATTERNS:
                            v = pattern.sub(replacement, v)
                    sanitized_args[k] = v
                record.args = sanitized_args
            elif isinstance(record.args, tuple):
                sanitized_list = []
                for item in record.args:
                    if isinstance(item, str):
                        for pattern, replacement in self.SENSITIVE_PATTERNS:
                            item = pattern.sub(replacement, item)
                    sanitized_list.append(item)
                record.args = tuple(sanitized_list)
        return True


def validate_production_configuration() -> None:
    """Validate all production security and configuration requirements.
    
    Raises:
        ConfigurationError: If any production requirement is violated.
    """
    if is_production():
        get_jwt_secret_key()
        get_cors_allowed_origins()
        get_database_url()
