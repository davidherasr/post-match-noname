"""Advanced scouting workflow, observed-position indexes and performance indexes.

Revision ID: 0004_scout_workflow_3_3
Revises: 0003_league_intelligence_3_2
Create Date: 2026-08-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_scout_workflow_3_3"
down_revision = "0003_league_intelligence_3_2"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {x["name"] for x in sa.inspect(op.get_bind()).get_indexes(table)}


def _add_index(name: str, table: str, cols: list[str]) -> None:
    if table in _tables() and name not in _indexes(table):
        op.create_index(name, table, cols)


def upgrade() -> None:
    existing = _tables()
    if "scouted_player_profiles" not in existing:
        op.create_table(
            "scouted_player_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="candidate"),
            sa.Column("model_position", sa.String(20)),
            sa.Column("model_role", sa.String(80)),
            sa.Column("fit_score", sa.Float()),
            sa.Column("current_level", sa.Float()),
            sa.Column("potential_score", sa.Float()),
            sa.Column("final_decision", sa.String(50)),
            sa.Column("director_summary", sa.Text()),
            sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("approved_at", sa.DateTime()),
            sa.UniqueConstraint("player_id", name="uq_scouted_player_profile"),
        )
    existing = _tables()
    if "scout_reviews" not in existing:
        op.create_table(
            "scout_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("scouted_player_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
            sa.Column("observed_position", sa.String(20)),
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
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("submitted_at", sa.DateTime()),
            sa.UniqueConstraint("profile_id", "reviewer_id", name="uq_scout_review_reviewer"),
        )

    _add_index("ix_matches_season_status_date", "matches", ["season_id", "status", "match_date"])
    _add_index("ix_eval_report_scope", "player_evaluations", ["report_id", "evaluation_scope"])
    _add_index("ix_eval_player_rating", "player_evaluations", ["player_id", "general_rating"])
    _add_index("ix_eval_team_player", "player_evaluations", ["team_id", "player_id"])
    _add_index("ix_reports_status_match", "reports", ["status", "match_id"])
    _add_index("ix_reports_reporter_status", "reports", ["reporter_id", "status"])
    _add_index("ix_participations_match_team", "participations", ["match_id", "team_id"])
    _add_index("ix_participations_player_position", "participations", ["player_id", "position"])
    _add_index("ix_assignments_user_status", "report_assignments", ["user_id", "status"])
    _add_index("ix_followups_status_review", "follow_ups", ["status", "next_review_date"])
    _add_index("ix_rosters_team_season_active", "team_rosters", ["team_id", "season_id", "active"])
    _add_index("ix_scouted_status_assignment", "scouted_player_profiles", ["status", "assigned_to"])
    _add_index("ix_scouted_model_position", "scouted_player_profiles", ["model_position"])
    _add_index("ix_scout_review_reviewer_status", "scout_reviews", ["reviewer_id", "status"])


def downgrade() -> None:
    existing = _tables()
    if "scout_reviews" in existing:
        op.drop_table("scout_reviews")
    if "scouted_player_profiles" in existing:
        op.drop_table("scouted_player_profiles")
