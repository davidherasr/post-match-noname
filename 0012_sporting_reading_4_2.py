"""Sporting reading and staff-weight model for 4.2.

Revision ID: 0012_sporting_reading_4_2
Revises: 0011_user_lifecycle_4_1_1
Create Date: 2026-09-14

Adds:
- optional individual-player-tracking capability on users;
- context-specific sporting weights for staff opinions;
- lightweight neutral-match opinions and highlighted players;
- own/rival team-performance ratings on No Name postmatch reports.

Legacy Scout roles are converted non-destructively into the new capability. Existing
Scout observations/missions remain untouched for historical compatibility.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_sporting_reading_4_2"
down_revision = "0011_user_lifecycle_4_1_1"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables()

    if "users" in tables and "can_track_players" not in _columns("users"):
        op.add_column("users", sa.Column("can_track_players", sa.Boolean(), nullable=False, server_default=sa.false()))

    # Convert the organizational Scout role into a capability. We intentionally keep
    # all historical scout tables and records; only current access semantics change.
    if "users" in tables and "user_roles" in tables:
        bind.execute(sa.text(
            "UPDATE users SET can_track_players = TRUE "
            "WHERE id IN (SELECT user_id FROM user_roles WHERE role = 'scout')"
        ))
        # A former Scout still needs a normal app role. Ensure Informador exists before
        # deleting the obsolete Scout role row.
        bind.execute(sa.text(
            "INSERT INTO user_roles (user_id, role, created_at) "
            "SELECT ur.user_id, 'reporter', CURRENT_TIMESTAMP FROM user_roles ur "
            "WHERE ur.role = 'scout' AND NOT EXISTS ("
            "SELECT 1 FROM user_roles r2 WHERE r2.user_id = ur.user_id AND r2.role = 'reporter'"
            ")"
        ))
        bind.execute(sa.text("DELETE FROM user_roles WHERE role = 'scout'"))
        bind.execute(sa.text("UPDATE users SET role = 'reporter' WHERE role = 'scout'"))

    if "reports" in tables:
        cols = _columns("reports")
        if "own_team_rating" not in cols:
            op.add_column("reports", sa.Column("own_team_rating", sa.Float(), nullable=True))
        if "rival_team_rating" not in cols:
            op.add_column("reports", sa.Column("rival_team_rating", sa.Float(), nullable=True))

    tables = _tables()
    if "staff_sporting_weights" not in tables:
        op.create_table(
            "staff_sporting_weights",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("own_match_weight", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("neutral_match_weight", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", name="uq_staff_sporting_weight_user"),
        )

    tables = _tables()
    if "match_opinions" not in tables:
        op.create_table(
            "match_opinions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("home_team_rating", sa.Float(), nullable=True),
            sa.Column("away_team_rating", sa.Float(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("match_id", "user_id", name="uq_match_opinion_user"),
        )

    tables = _tables()
    if "match_opinion_players" not in tables:
        op.create_table(
            "match_opinion_players",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("opinion_id", sa.Integer(), sa.ForeignKey("match_opinions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
            sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
            sa.Column("rating", sa.Float(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("opinion_id", "player_id", name="uq_match_opinion_player"),
        )


def downgrade() -> None:
    # 4.2 is intentionally non-destructive on downgrade. Keeping collected opinions,
    # weights and the tracking capability avoids data loss if code is rolled back.
    pass
