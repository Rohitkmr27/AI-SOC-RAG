"""FastAPI endpoints for authentication and current-user management."""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.auth.schemas import LoginRequest, TokenResponse, UserResponse
from app.auth.security import create_access_token, get_token_expire_minutes, verify_password
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate username/email and password, returning a signed JWT access token."""
    login_id = payload.username.strip()
    query = select(User).where(or_(User.username == login_id, User.email == login_id))
    user = session.execute(query).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        logger.warning("Failed login attempt for identifier: %s", login_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning("Inactive user login attempt: %s", login_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expire_minutes = get_token_expire_minutes()
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
        },
        expires_delta=timedelta(minutes=expire_minutes),
    )

    logger.info("Successful login for user: %s (role: %s)", user.username, user.role.value)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Retrieve the authenticated user's current identity and authorization role."""
    return UserResponse.model_validate(current_user)
