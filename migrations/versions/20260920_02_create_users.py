"""create users table and user_role enum

Revision ID: 20260920_02
Revises: 20260919_01
Create Date: 2026-09-20
"""

import sqlalchemy as sa
from alembic import op

revision = "20260920_02"
down_revision = "20260919_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = sa.Enum("ANALYST", "ADMIN", name="user_role")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="ANALYST"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role")
