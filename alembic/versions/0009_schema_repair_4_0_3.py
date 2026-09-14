"""Repair/verify additive schema used by the 4.x application.

Revision ID: 0009_schema_repair_4_0_3
Revises: 0008_match_study_4_0
Create Date: 2026-09-14

This migration exists because a real production deployment reached the 4.0
application with an Alembic revision that did not match the physical columns
available in ``matches``.  The ORM then selected the 4.0 fields and PostgreSQL
raised ``ProgrammingError`` before Home could render.

The migration is intentionally idempotent and non-destructive.  It never drops,
renames or rewrites sporting records.  It only restores additive columns/indexes
that should already exist after revisions 0005-0008 and backfills safe metadata.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_schema_repair_4_0_3"
down_revision = "0008_match_study_4_0"
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


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {x["name"] for x in _insp().get_indexes(table)}


def _add_column(table: str, name: str, column: sa.Column) -> None:
    if table in _tables() and name not in _columns(table):
        op.add_column(table, column)


def _add_index(name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    if table in _tables() and all(col in _columns(table) for col in columns) and name not in _indexes(table):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    conn = op.get_bind()

    # Calendar/planning columns introduced in 3.5.  A production database that
    # was stamped ahead or restored from an older backup may legitimately miss
    # one of them, so repair them before the ORM touches Match.
    if "matches" in _tables():
        _add_column("matches", "window_start", sa.Column("window_start", sa.Date(), nullable=True))
        _add_column("matches", "window_end", sa.Column("window_end", sa.Date(), nullable=True))
        _add_column("matches", "kickoff_at", sa.Column("kickoff_at", sa.DateTime(), nullable=True))
        _add_column(
            "matches",
            "schedule_status",
            sa.Column("schedule_status", sa.String(30), nullable=False, server_default="provisional"),
        )
        _add_column(
            "matches",
            "fixture_type",
            sa.Column("fixture_type", sa.String(30), nullable=False, server_default="league"),
        )

        # Match Study fields introduced in 4.0.  These five columns are the
        # important repair for the production ProgrammingError seen in Home.
        _add_column(
            "matches",
            "video_available",
            sa.Column("video_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        _add_column("matches", "video_reference", sa.Column("video_reference", sa.Text(), nullable=True))
        _add_column(
            "matches",
            "home_formation_known",
            sa.Column("home_formation_known", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        _add_column(
            "matches",
            "away_formation_known",
            sa.Column("away_formation_known", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        _add_column("matches", "study_notes", sa.Column("study_notes", sa.Text(), nullable=True))

        # Safe metadata backfill only.  Scores, dates, players, reports and
        # formations themselves are never modified or invented.
        cols = _columns("matches")
        if {"window_start", "window_end", "match_date"}.issubset(cols):
            conn.execute(sa.text(
                "UPDATE matches SET window_start = COALESCE(window_start, match_date), "
                "window_end = COALESCE(window_end, match_date)"
            ))
        if {"home_formation_known", "home_formation"}.issubset(cols):
            conn.execute(sa.text(
                "UPDATE matches SET home_formation_known = :yes "
                "WHERE home_formation IS NOT NULL AND TRIM(home_formation) <> ''"
            ), {"yes": True})
        if {"away_formation_known", "away_formation"}.issubset(cols):
            conn.execute(sa.text(
                "UPDATE matches SET away_formation_known = :yes "
                "WHERE away_formation IS NOT NULL AND TRIM(away_formation) <> ''"
            ), {"yes": True})

        _add_index("ix_matches_schedule_window", "matches", ["season_id", "schedule_status", "window_start"])
        _add_index("ix_matches_kickoff", "matches", ["kickoff_at"])

    # 3.6 decision fields.  They are additive and safe to restore if an older
    # physical table was retained while Alembic was stamped to a newer revision.
    if "player_season_decisions" in _tables():
        _add_column("player_season_decisions", "current_level", sa.Column("current_level", sa.Float(), nullable=True))
        _add_column("player_season_decisions", "potential_score", sa.Column("potential_score", sa.Float(), nullable=True))
        _add_column("player_season_decisions", "criteria_json", sa.Column("criteria_json", sa.Text(), nullable=True))

    # 3.8 canonical observation fields.  Do not replay legacy-copy logic here;
    # this repair only guarantees that the current ORM has the columns it needs.
    if "scout_observations" in _tables():
        _add_column(
            "scout_observations",
            "observation_level",
            sa.Column("observation_level", sa.String(20), nullable=False, server_default="observation"),
        )
        _add_column("scout_observations", "model_role_id", sa.Column("model_role_id", sa.Integer(), nullable=True))
        _add_column("scout_observations", "legacy_review_id", sa.Column("legacy_review_id", sa.Integer(), nullable=True))
        _add_index("ix_scout_observation_role_level", "scout_observations", ["model_role_id", "observation_level"])
        _add_index("ux_scout_observation_legacy_review", "scout_observations", ["legacy_review_id"], unique=True)


def downgrade() -> None:
    # This revision is a schema repair.  Removing repaired columns during a
    # downgrade could destroy data written by 4.x, so downgrade is deliberately
    # non-destructive/no-op.
    pass
