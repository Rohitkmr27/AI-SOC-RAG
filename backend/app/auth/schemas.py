"""Pydantic request and response schemas for authentication & user management."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.auth.models import UserRole


class LoginRequest(BaseModel):
    """Payload for POST /auth/login."""
    username: str = Field(min_length=1, max_length=255, description="Username or email address")
    password: str = Field(min_length=1, max_length=255)


class TokenResponse(BaseModel):
    """Response containing signed JWT access token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Response representing authenticated user identity and role."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
