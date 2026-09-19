"""Initialization script for creating the initial local administrative user."""

import logging
import os
import sys
from pathlib import Path

# Add backend root directory to Python path if executed directly
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.database import DatabaseConfigurationError, get_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def init_admin() -> None:
    """Create or update the initial administrative user using environment variables."""
    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    email = os.getenv("ADMIN_EMAIL", "admin@aisoc.local").strip()
    password = os.getenv("ADMIN_PASSWORD", "admin123").strip()

    if not username or not email or not password:
        logger.error("ADMIN_USERNAME, ADMIN_EMAIL, and ADMIN_PASSWORD must not be empty.")
        sys.exit(1)

    try:
        session_factory = get_session_factory()
    except DatabaseConfigurationError as error:
        logger.warning("Database configuration unavailable; skipping admin user initialization: %s", error)
        return

    with session_factory() as session:

        # Check if user exists by username or email
        user = session.execute(
            select(User).where((User.username == username) | (User.email == email))
        ).scalar_one_or_none()

        if user:
            logger.info("Admin user '%s' (%s) already exists. Updating password hash and role...", user.username, user.email)
            user.password_hash = hash_password(password)
            user.role = UserRole.ADMIN
            user.is_active = True
            session.commit()
            logger.info("Admin user '%s' updated successfully.", user.username)
        else:
            logger.info("Creating initial admin user '%s' (%s)...", username, email)
            admin_user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin_user)
            session.commit()
            logger.info("Initial admin user '%s' created successfully.", username)


if __name__ == "__main__":
    init_admin()
