"""Repair the full core workspace schema used by Home/Jornada.

Revision ID: 0010_core_workspace_schema_repair_4_0_4
Revises: 0009_schema_repair_4_0_3
Create Date: 2026-09-14

A production failure showed that checking only the columns added in recent
releases is insufficient: SQLAlchemy ORM selects every mapped column of an
entity unless explicitly narrowed.  Therefore Home could pass the 4.0.3 schema
contract and still fail with PostgreSQL ``ProgrammingError`` when an older
physical table lacked a pre-3.5 optional column.

This migration is additive/idempotent.  It never drops or rewrites sporting
records.  It restores only columns whose values can be introduced safely.  Core
identity/relationship columns are not invented; startup validation reports them
clearly if a database is fundamentally incompatible.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_core_workspace_schema_repair_4_0_4"
down_revision = "0009_schema_repair_4_0_3"
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


def _add(table: str, name: str, column: sa.Column) -> None:
    if table in _tables() and name not in _columns(table):
        op.add_column(table, column)


def upgrade() -> None:
    # ``matches``: restore every non-identity field that can be added without
    # fabricating a team/season/competition/date relationship.
    if "matches" in _tables():
        _add("matches", "window_start", sa.Column("window_start", sa.Date(), nullable=True))
        _add("matches", "window_end", sa.Column("window_end", sa.Date(), nullable=True))
        _add("matches", "kickoff_at", sa.Column("kickoff_at", sa.DateTime(), nullable=True))
        _add("matches", "schedule_status", sa.Column("schedule_status", sa.String(30), nullable=False, server_default="provisional"))
        _add("matches", "fixture_type", sa.Column("fixture_type", sa.String(30), nullable=False, server_default="league"))
        _add("matches", "home_score", sa.Column("home_score", sa.Integer(), nullable=True))
        _add("matches", "away_score", sa.Column("away_score", sa.Integer(), nullable=True))
        _add("matches", "venue", sa.Column("venue", sa.String(160), nullable=True))
        _add("matches", "home_formation", sa.Column("home_formation", sa.String(40), nullable=True))
        _add("matches", "away_formation", sa.Column("away_formation", sa.String(40), nullable=True))
        _add("matches", "video_available", sa.Column("video_available", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add("matches", "video_reference", sa.Column("video_reference", sa.Text(), nullable=True))
        _add("matches", "home_formation_known", sa.Column("home_formation_known", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add("matches", "away_formation_known", sa.Column("away_formation_known", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add("matches", "study_notes", sa.Column("study_notes", sa.Text(), nullable=True))
        _add("matches", "status", sa.Column("status", sa.String(30), nullable=False, server_default="draft"))
        _add("matches", "report_due_at", sa.Column("report_due_at", sa.DateTime(), nullable=True))
        _add("matches", "revision", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        _add("matches", "deleted_at", sa.Column("deleted_at", sa.DateTime(), nullable=True))
        # ``created_by`` is required for new writes but may be absent in a very
        # old physical schema.  Nullable preserves existing rows; application
        # writes always supply the actor id.
        _add("matches", "created_by", sa.Column("created_by", sa.Integer(), nullable=True))
        _add("matches", "created_at", sa.Column("created_at", sa.DateTime(), nullable=True))
        _add("matches", "updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True))

        cols = _columns("matches")
        conn = op.get_bind()
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
        if "created_at" in cols:
            conn.execute(sa.text("UPDATE matches SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        if "updated_at" in cols:
            conn.execute(sa.text("UPDATE matches SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

    # Related entities loaded by Home.  Only optional/defaultable fields are
    # repaired; id/name and core relations are never fabricated.
    if "teams" in _tables():
        _add("teams", "short_name", sa.Column("short_name", sa.String(40), nullable=True))
        _add("teams", "country", sa.Column("country", sa.String(80), nullable=True))
        _add("teams", "logo_b64", sa.Column("logo_b64", sa.Text(), nullable=True))
        _add("teams", "logo_mime", sa.Column("logo_mime", sa.String(80), nullable=True))
        _add("teams", "is_own_team", sa.Column("is_own_team", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add("teams", "active", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
        _add("teams", "created_at", sa.Column("created_at", sa.DateTime(), nullable=True))
        _add("teams", "updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True))
        cols = _columns("teams")
        conn = op.get_bind()
        if "created_at" in cols:
            conn.execute(sa.text("UPDATE teams SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        if "updated_at" in cols:
            conn.execute(sa.text("UPDATE teams SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

    if "competitions" in _tables():
        _add("competitions", "country", sa.Column("country", sa.String(80), nullable=True))
        _add("competitions", "active", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
        _add("competitions", "updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True))
        cols = _columns("competitions")
        if "updated_at" in cols:
            op.get_bind().execute(sa.text("UPDATE competitions SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

    if "seasons" in _tables():
        _add("seasons", "start_date", sa.Column("start_date", sa.Date(), nullable=True))
        _add("seasons", "end_date", sa.Column("end_date", sa.Date(), nullable=True))
        _add("seasons", "active", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
        _add("seasons", "updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True))
        cols = _columns("seasons")
        if "updated_at" in cols:
            op.get_bind().execute(sa.text("UPDATE seasons SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))


def downgrade() -> None:
    # Repair migration: never remove recovered production columns/data.
    pass
