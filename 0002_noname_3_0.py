"""No Name PostMatch 3.0 workflow release.

The 3.0 edition reuses the normalized 2.x schema. This revision is intentionally
non-destructive: it marks the upgrade boundary so existing Supabase databases
can move to 3.0 without deleting, renaming or rewriting sporting data.

Revision ID: 0002_noname_3_0
Revises: 0001_initial_2_0
Create Date: 2026-08-09
"""
from __future__ import annotations

revision = "0002_noname_3_0"
down_revision = "0001_initial_2_0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
