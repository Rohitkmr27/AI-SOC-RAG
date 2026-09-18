"""Database configuration and session dependency."""

import os
from collections.abc import Generator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class DatabaseConfigurationError(RuntimeError):
    """Raised when database configuration is unavailable."""


@lru_cache
def get_engine():
    """Create a database engine only when database-backed functionality is used."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise DatabaseConfigurationError("DATABASE_URL is not configured.")
    return create_engine(database_url, pool_pre_ping=True)


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Provide a transaction session without exposing configuration details."""
    try:
        session = get_session_factory()()
    except DatabaseConfigurationError as error:
        raise HTTPException(status_code=503, detail="Alert database is not configured.") from error
    try:
        yield session
    finally:
        session.close()
