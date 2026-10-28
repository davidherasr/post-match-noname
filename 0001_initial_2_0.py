"""Initial PostMatch Scout 2.0 schema.

Revision ID: 0001_initial_2_0
Revises:
Create Date: 2026-08-04
"""
from __future__ import annotations

from alembic import op

from models import Base

revision = "0001_initial_2_0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
