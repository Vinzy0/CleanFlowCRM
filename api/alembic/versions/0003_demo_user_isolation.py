"""Restrict public demo accounts to synthetic leads.

Revision ID: 0003_demo_user_isolation
Revises: 0002_automation_demo
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_demo_user_isolation"
down_revision = "0002_automation_demo"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("users", "is_demo")
