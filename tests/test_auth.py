"""Comprehensive unit & integration tests for Stage 10 Authentication & Authorization."""

import sys
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.alerts.models import Base as AlertBase
from app.auth.dependencies import get_current_user, require_admin, require_analyst
from app.auth.models import Base as AuthBase, User, UserRole
from app.auth.security import create_access_token, get_password_hash
from app.database import get_db
from app.main import app


@pytest.fixture
def auth_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    AuthBase.metadata.create_all(engine)
    AlertBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    # Seed test users
    with factory() as session:
        analyst = User(
            username="analyst_test",
            email="analyst@example.com",
            password_hash=get_password_hash("AnalystPass123!"),
            role=UserRole.ANALYST,
            is_active=True,
        )
        admin = User(
            username="admin_test",
            email="admin@example.com",
            password_hash=get_password_hash("AdminPass123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        inactive = User(
            username="inactive_test",
            email="inactive@example.com",
            password_hash=get_password_hash("InactivePass123!"),
            role=UserRole.ANALYST,
            is_active=False,
        )
        session.add_all([analyst, admin, inactive])
        session.commit()

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    AuthBase.metadata.drop_all(engine)
    AlertBase.metadata.drop_all(engine)


def test_public_health_endpoint_accessible_without_auth(auth_db: TestClient) -> None:
    response = auth_db.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_success(auth_db: TestClient) -> None:
    response = auth_db.post("/auth/login", json={"username": "analyst_test", "password": "AnalystPass123!"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(auth_db: TestClient) -> None:
    response = auth_db.post("/auth/login", json={"username": "analyst_test", "password": "WrongPassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_login_inactive_user(auth_db: TestClient) -> None:
    response = auth_db.post("/auth/login", json={"username": "inactive_test", "password": "InactivePass123!"})
    assert response.status_code == 401
    assert response.json()["detail"] == "User account is inactive or disabled."



def test_get_current_user_me(auth_db: TestClient) -> None:
    login_res = auth_db.post("/auth/login", json={"username": "admin_test", "password": "AdminPass123!"})
    token = login_res.json()["access_token"]

    me_res = auth_db.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    user_info = me_res.json()
    assert user_info["username"] == "admin_test"
    assert user_info["role"] == "ADMIN"


def test_unauthenticated_request_to_protected_endpoint(auth_db: TestClient) -> None:
    response = auth_db.get("/alerts")
    assert response.status_code == 401


def test_invalid_token_rejected(auth_db: TestClient) -> None:
    response = auth_db.get("/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication token."


def test_expired_token_rejected(auth_db: TestClient) -> None:
    expired_token = create_access_token(
        data={"sub": "analyst_test", "role": "ANALYST"},
        expires_delta=timedelta(seconds=-10),
    )
    response = auth_db.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication token has expired."


def test_role_based_access_control(auth_db: TestClient) -> None:
    analyst_token = create_access_token(data={"sub": "analyst_test", "role": "ANALYST"})
    admin_token = create_access_token(data={"sub": "admin_test", "role": "ADMIN"})

    # Test analyst user requesting admin dependency
    analyst_res = auth_db.get("/auth/me", headers={"Authorization": f"Bearer {analyst_token}"})
    assert analyst_res.status_code == 200

    # Execute admin dependency check directly or via endpoint
    admin_user = User(username="admin_test", role=UserRole.ADMIN, is_active=True)
    analyst_user = User(username="analyst_test", role=UserRole.ANALYST, is_active=True)

    assert require_admin(admin_user).username == "admin_test"
    assert require_analyst(analyst_user).username == "analyst_test"

    with pytest.raises(Exception) as exc_info:
        require_admin(analyst_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Administrative privileges required."

