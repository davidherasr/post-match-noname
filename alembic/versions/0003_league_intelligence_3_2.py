"""League intelligence and local postmatch drafts for No Name 3.2.

Revision ID: 0003_league_intelligence_3_2
Revises: 0002_noname_3_0
Create Date: 2026-08-11

The initial 2.0 migration historically calls current Base.metadata.create_all(). On a
brand-new install that can already create these tables before this revision runs.
For that reason this migration is deliberately idempotent: existing 3.x databases
receive the new tables, while fresh databases simply add any missing indexes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_league_intelligence_3_2"
down_revision = "0002_noname_3_0"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {x["name"] for x in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    existing = _tables()
    if "postmatch_drafts" not in existing:
        op.create_table(
            "postmatch_drafts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="SET NULL")),
            sa.Column("title", sa.String(180)),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if "league_player_profiles" not in existing:
        op.create_table(
            "league_player_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
            sa.Column("decision_status", sa.String(40), nullable=False, server_default="Base"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("director_note", sa.Text()),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("player_id", name="uq_league_player_profile"),
        )
    if "scouting_lists" not in existing:
        op.create_table(
            "scouting_lists",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("list_type", sa.String(30), nullable=False, server_default="custom"),
            sa.Column("formation", sa.String(40)),
            sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="SET NULL")),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    # refresh because scouting_list_items depends on scouting_lists.
    existing = _tables()
    if "scouting_list_items" not in existing:
        op.create_table(
            "scouting_list_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("list_id", sa.Integer(), sa.ForeignKey("scouting_lists.id", ondelete="CASCADE"), nullable=False),
            sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
            sa.Column("position", sa.String(20)),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("note", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("list_id", "player_id", name="uq_scouting_list_player"),
        )

    if "ix_postmatch_drafts_created_by_status" not in _indexes("postmatch_drafts"):
        op.create_index("ix_postmatch_drafts_created_by_status", "postmatch_drafts", ["created_by", "status"])
    if "ix_league_profiles_status" not in _indexes("league_player_profiles"):
        op.create_index("ix_league_profiles_status", "league_player_profiles", ["decision_status", "priority"])
    if "ix_scouting_lists_active" not in _indexes("scouting_lists"):
        op.create_index("ix_scouting_lists_active", "scouting_lists", ["active"])


def downgrade() -> None:
    existing = _tables()
    if "scouting_list_items" in existing:
        op.drop_table("scouting_list_items")
    if "scouting_lists" in existing:
        op.drop_table("scouting_lists")
    if "league_player_profiles" in existing:
        op.drop_table("league_player_profiles")
    if "postmatch_drafts" in existing:
        op.drop_table("postmatch_drafts")
