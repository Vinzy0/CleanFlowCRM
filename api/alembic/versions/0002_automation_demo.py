"""Email tracking and demo records.

Revision ID: 0002_automation_demo
Revises: 0001_foundation
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_automation_demo"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("leads", sa.Column("demo_scenario", sa.String(40), nullable=True))
    op.add_column("activities", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.create_index("ix_activities_idempotency_key", "activities", ["idempotency_key"], unique=True)


def downgrade():
    op.drop_index("ix_activities_idempotency_key", table_name="activities")
    op.drop_column("activities", "idempotency_key")
    op.drop_column("leads", "demo_scenario")
    op.drop_column("leads", "is_demo")
