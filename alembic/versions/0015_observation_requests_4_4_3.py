"""Voluntary DD observation requests and responses; additive, preserves historical evidence.

Revision ID: 0015_observation_requests_4_4_3
Revises: 0014_unified_player_evidence_4_4_2
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_observation_requests_4_4_3"
down_revision = "0014_unified_player_evidence_4_4_2"
branch_labels = None
depends_on = None


def upgrade():
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "player_observation_requests" not in existing_tables:
        op.create_table("player_observation_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_match_id", sa.Integer(), sa.ForeignKey("matches.id", ondelete="SET NULL")),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="Normal"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime()), sa.Column("closed_reason", sa.Text()))
    existing_indexes = {row["name"] for row in sa.inspect(op.get_bind()).get_indexes("player_observation_requests")}
    for col in ("player_id", "season_id", "status"):
        name = f"ix_player_observation_requests_{col}"
        if name not in existing_indexes:
            op.create_index(name, "player_observation_requests", [col])
    if "player_observation_recipients" not in existing_tables:
        op.create_table("player_observation_recipients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("player_observation_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_id", "user_id", name="uq_observation_request_user"))
    if "ix_player_observation_recipients_user_id" not in {row["name"] for row in sa.inspect(op.get_bind()).get_indexes("player_observation_recipients")}:
        op.create_index("ix_player_observation_recipients_user_id", "player_observation_recipients", ["user_id"])
    if "player_observation_responses" not in existing_tables:
        op.create_table("player_observation_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("player_observation_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id", ondelete="SET NULL")),
        sa.Column("player_evaluation_id", sa.Integer(), sa.ForeignKey("player_evaluations.id", ondelete="SET NULL")),
        sa.Column("neutral_signal_id", sa.Integer(), sa.ForeignKey("match_opinion_players.id", ondelete="SET NULL")),
        sa.Column("result", sa.String(25), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_id", "user_id", "match_id", name="uq_observation_response_context"))
    if "ix_player_observation_responses_request_id" not in {row["name"] for row in sa.inspect(op.get_bind()).get_indexes("player_observation_responses")}:
        op.create_index("ix_player_observation_responses_request_id", "player_observation_responses", ["request_id"])


def downgrade():
    # Downgrade intentionally non-destructive, as with previous No Name releases.
    pass
