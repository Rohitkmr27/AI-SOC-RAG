"""Security utilities for password hashing and JWT token management."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import bcrypt

from app.config import (
    DEFAULT_DEV_JWT_SECRET as DEFAULT_JWT_SECRET,
    get_jwt_secret_key,
    get_token_expire_minutes,
)

ALGORITHM = "HS256"



def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


get_password_hash = hash_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))



def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token containing claims and expiration."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=get_token_expire_minutes())

    to_encode.update({
        "exp": expire,
        "iat": now,
    })
    secret_key = get_jwt_secret_key()
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token signature and expiration.
    
    Raises:
        ValueError: If token is expired, invalid, or malformed.
    """
    secret_key = get_jwt_secret_key()
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("Token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid or malformed authentication token.") from exc
