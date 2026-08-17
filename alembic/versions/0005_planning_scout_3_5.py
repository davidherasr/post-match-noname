"""League calendar, multi-role Scout workflow and No Name planning model.

Revision ID: 0005_planning_scout_3_5
Revises: 0004_scout_workflow_3_3
Create Date: 2026-08-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_planning_scout_3_5"
down_revision = "0004_scout_workflow_3_3"
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


def _add_index(name: str, table: str, cols: list[str]) -> None:
    if table in _tables() and name not in _indexes(table):
        op.create_index(name, table, cols)


def _add_match_column(name: str, column: sa.Column) -> None:
    if "matches" in _tables() and name not in _columns("matches"):
        op.add_column("matches", column)


def upgrade() -> None:
    _add_match_column("window_start", sa.Column("window_start", sa.Date()))
    _add_match_column("window_end", sa.Column("window_end", sa.Date()))
    _add_match_column("kickoff_at", sa.Column("kickoff_at", sa.DateTime()))
    _add_match_column("schedule_status", sa.Column("schedule_status", sa.String(30), nullable=False, server_default="window"))
    _add_match_column("fixture_type", sa.Column("fixture_type", sa.String(30), nullable=False, server_default="league"))
    # Backfill legacy matches without inventing a kickoff time.
    if "matches" in _tables():
        op.execute(sa.text("UPDATE matches SET window_start = COALESCE(window_start, match_date), window_end = COALESCE(window_end, match_date)"))
        op.execute(sa.text("UPDATE matches SET schedule_status = 'date_confirmed' WHERE status IN ('published','closed','archived') AND kickoff_at IS NULL"))

    existing = _tables()
    if "user_roles" not in existing:
        op.create_table(
            "user_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(30), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "role", name="uq_user_role"),
        )
        # Preserve every existing account role as the first capability.
        op.execute(sa.text("INSERT INTO user_roles (user_id, role, created_at) SELECT id, role, CURRENT_TIMESTAMP FROM users"))

    existing = _tables()
    if "scout_missions" not in existing:
        op.create_table(
            "scout_missions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("mission_type", sa.String(40), nullable=False, server_default="player"),
            sa.Column("target_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL")),
            sa.Column("title", sa.String(180), nullable=False),
            sa.Column("purpose", sa.Text()),
            sa.Column("focus_json", sa.Text()),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("result_summary", sa.Text()),
            sa.Column("due_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    existing = _tables()
    if "scout_mission_targets" not in existing:
        op.create_table(
            "scout_mission_targets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("mission_id", sa.Integer(), sa.ForeignKey("scout_missions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
            sa.Column("note", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("mission_id", "player_id", name="uq_scout_mission_player"),
        )
    existing = _tables()
    if "scout_observations" not in existing:
        op.create_table(
            "scout_observations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("scouted_player_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id", ondelete="SET NULL")),
            sa.Column("mission_id", sa.Integer(), sa.ForeignKey("scout_missions.id", ondelete="SET NULL")),
            sa.Column("source_type", sa.String(30), nullable=False, server_default="specific"),
            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.Column("observed_position", sa.String(20)),
            sa.Column("general_rating", sa.Float()),
            sa.Column("technical_rating", sa.Float()),
            sa.Column("tactical_rating", sa.Float()),
            sa.Column("physical_rating", sa.Float()),
            sa.Column("mental_rating", sa.Float()),
            sa.Column("current_level", sa.Float()),
            sa.Column("potential_score", sa.Float()),
            sa.Column("model_fit_score", sa.Float()),
            sa.Column("attributes_json", sa.Text()),
            sa.Column("strengths", sa.Text()),
            sa.Column("weaknesses", sa.Text()),
            sa.Column("summary", sa.Text()),
            sa.Column("recommendation", sa.String(80)),
            sa.Column("submitted_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    existing = _tables()
    if "game_model_roles" not in existing:
        op.create_table(
            "game_model_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("position", sa.String(20), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("name", "position", name="uq_game_model_role"),
        )
    existing = _tables()
    if "game_model_criteria" not in existing:
        op.create_table(
            "game_model_criteria",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("game_model_roles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("category", sa.String(30), nullable=False, server_default="Táctico"),
            sa.Column("description", sa.Text()),
            sa.Column("weight", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("role_id", "name", name="uq_model_role_criterion"),
        )
    existing = _tables()
    if "squad_needs" not in existing:
        op.create_table(
            "squad_needs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False),
            sa.Column("model_role_id", sa.Integer(), sa.ForeignKey("game_model_roles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("need_level", sa.String(20), nullable=False, server_default="Media"),
            sa.Column("status", sa.String(30), nullable=False, server_default="Abierta"),
            sa.Column("note", sa.Text()),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("season_id", "model_role_id", name="uq_squad_need_role"),
        )
    existing = _tables()
    if "player_season_decisions" not in existing:
        op.create_table(
            "player_season_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False),
            sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
            sa.Column("model_role_id", sa.Integer(), sa.ForeignKey("game_model_roles.id", ondelete="SET NULL")),
            sa.Column("status", sa.String(40), nullable=False, server_default="Base"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("director_note", sa.Text()),
            sa.Column("fit_score", sa.Float()),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("season_id", "player_id", name="uq_player_season_decision"),
        )

    _add_index("ix_matches_schedule_window", "matches", ["season_id", "schedule_status", "window_start"])
    _add_index("ix_matches_kickoff", "matches", ["kickoff_at"])
    _add_index("ix_user_roles_role_user", "user_roles", ["role", "user_id"])
    _add_index("ix_scout_mission_assignee_status", "scout_missions", ["assigned_to", "status"])
    _add_index("ix_scout_mission_match", "scout_missions", ["match_id", "status"])
    _add_index("ix_scout_observation_profile_date", "scout_observations", ["profile_id", "observed_at"])
    _add_index("ix_scout_observation_reviewer", "scout_observations", ["reviewer_id", "status"])
    _add_index("ix_model_roles_position_active", "game_model_roles", ["position", "active"])
    _add_index("ix_squad_needs_season_level", "squad_needs", ["season_id", "need_level"])
    _add_index("ix_player_season_decision_status", "player_season_decisions", ["season_id", "status", "priority"])


def downgrade() -> None:
    for table in [
        "player_season_decisions", "squad_needs", "game_model_criteria", "game_model_roles",
        "scout_observations", "scout_mission_targets", "scout_missions", "user_roles",
    ]:
        if table in _tables():
            op.drop_table(table)
    for col in ["fixture_type", "schedule_status", "kickoff_at", "window_end", "window_start"]:
        if "matches" in _tables() and col in _columns("matches"):
            op.drop_column("matches", col)
