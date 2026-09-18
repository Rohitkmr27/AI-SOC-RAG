"""create alerts table

Revision ID: 20260919_01
Revises:
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from alembic import op

revision = "20260919_01"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    severity = sa.Enum("Informational", "Low", "Medium", "High", "Critical", name="alert_severity")
    status = sa.Enum("NEW", "TRIAGED", "INVESTIGATING", "RESOLVED", name="alert_status")
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_ip", sa.String(length=45), nullable=False),
        sa.Column("destination_ip", sa.String(length=45), nullable=False),
        sa.Column("source_port", sa.Integer(), nullable=False),
        sa.Column("destination_port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=20), nullable=False),
        sa.Column("attack_type", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alerts_source_ip", "alerts", ["source_ip"])
    op.create_index("ix_alerts_destination_ip", "alerts", ["destination_ip"])
    op.create_index("ix_alerts_attack_type", "alerts", ["attack_type"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])

def downgrade() -> None:
    op.drop_table("alerts")
    op.execute("DROP TYPE IF EXISTS alert_status")
    op.execute("DROP TYPE IF EXISTS alert_severity")
