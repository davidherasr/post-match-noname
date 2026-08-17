"""Player Report 360 and internal model assessment fields.

Revision ID: 0006_player_report_360_3_6
Revises: 0005_planning_scout_3_5
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_player_report_360_3_6"
down_revision = "0005_planning_scout_3_5"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_insp().get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {c["name"] for c in _insp().get_columns(table)}


def upgrade() -> None:
    if "player_season_decisions" not in _tables():
        return
    cols = _columns("player_season_decisions")
    if "current_level" not in cols:
        op.add_column("player_season_decisions", sa.Column("current_level", sa.Float()))
    if "potential_score" not in cols:
        op.add_column("player_season_decisions", sa.Column("potential_score", sa.Float()))
    if "criteria_json" not in cols:
        op.add_column("player_season_decisions", sa.Column("criteria_json", sa.Text()))


def downgrade() -> None:
    if "player_season_decisions" not in _tables():
        return
    cols = _columns("player_season_decisions")
    for col in ["criteria_json", "potential_score", "current_level"]:
        if col in cols:
            op.drop_column("player_season_decisions", col)
