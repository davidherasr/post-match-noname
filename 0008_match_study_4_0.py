"""Neutral match study context for 4.0.

Revision ID: 0008_match_study_4_0
Revises: 0007_product_consolidation_3_8
Create Date: 2026-09-13

Additive/non-destructive. Existing formations are marked as known; all other
legacy matches remain valid and default to roster-only/no-video study context.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_match_study_4_0"
down_revision = "0007_product_consolidation_3_8"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if "matches" not in sa.inspect(op.get_bind()).get_table_names():
        return
    cols = _columns("matches")
    if "video_available" not in cols:
        op.add_column("matches", sa.Column("video_available", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "video_reference" not in cols:
        op.add_column("matches", sa.Column("video_reference", sa.Text(), nullable=True))
    if "home_formation_known" not in cols:
        op.add_column("matches", sa.Column("home_formation_known", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "away_formation_known" not in cols:
        op.add_column("matches", sa.Column("away_formation_known", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "study_notes" not in cols:
        op.add_column("matches", sa.Column("study_notes", sa.Text(), nullable=True))

    conn = op.get_bind()
    # Preserve every existing known formation instead of asking the user to
    # reclassify historical matches after upgrade.
    conn.execute(sa.text("UPDATE matches SET home_formation_known = :yes WHERE home_formation IS NOT NULL AND TRIM(home_formation) <> ''"), {"yes": True})
    conn.execute(sa.text("UPDATE matches SET away_formation_known = :yes WHERE away_formation IS NOT NULL AND TRIM(away_formation) <> ''"), {"yes": True})


def downgrade() -> None:
    cols = _columns("matches")
    # Dropping only the additive metadata is safe; formations/rosters themselves
    # are stored in pre-existing columns/tables and are never deleted here.
    for name in ["study_notes", "away_formation_known", "home_formation_known", "video_reference", "video_available"]:
        if name in cols:
            op.drop_column("matches", name)
