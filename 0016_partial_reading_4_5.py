"""4.5 additive: participation, position context, ranked/signalled evidence and unresolved identity.

Revision ID: 0016_partial_reading_4_5
Revises: 0015_observation_requests_4_4_3
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_partial_reading_4_5"
down_revision = "0015_observation_requests_4_4_3"
branch_labels = None
depends_on = None


def _add_column(table: str, column):
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return  # legacy sparse recovery is validated later by physical schema contract
    present = {c["name"] for c in inspector.get_columns(table)}
    if column.name not in present:
        if op.get_bind().dialect.name == "sqlite" and column.foreign_keys:
            referenced = {fk.target_fullname.split(".")[0] for fk in column.foreign_keys}
            if not (referenced | {"players", "teams", "matches", "users"}).issubset(set(inspector.get_table_names())):
                # A sparse legacy repair DB cannot reflect missing FK targets.
                # The full physical-schema check still rejects it for app startup.
                op.add_column(table, sa.Column(column.name, sa.Integer(), nullable=True))
            else:
                with op.batch_alter_table(table, recreate="always") as batch:
                    batch.add_column(column)
        else:
            op.add_column(table, column)


def upgrade():
    _add_column("users", sa.Column("participation_profile", sa.String(20), nullable=False, server_default="full"))
    _add_column("team_rosters", sa.Column("usual_position", sa.String(20), nullable=True))
    _add_column("player_observation_requests", sa.Column("origin_player_evaluation_id", sa.Integer(), sa.ForeignKey("player_evaluations.id", ondelete="SET NULL", name="fk_po_request_eval_45")))
    _add_column("player_observation_requests", sa.Column("origin_neutral_signal_id", sa.Integer(), sa.ForeignKey("match_opinion_players.id", ondelete="SET NULL", name="fk_po_request_neutral_45")))
    for table in ("player_evaluations", "match_opinion_players"):
        _add_column(table, sa.Column("highlight_rank", sa.Integer(), nullable=True))
        _add_column(table, sa.Column("attention_signal", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "unidentified_player_signals" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("unidentified_player_signals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("position", sa.String(20)), sa.Column("shirt_number", sa.Integer()),
            sa.Column("label", sa.String(160)), sa.Column("rating", sa.Float()),
            sa.Column("highlight_rank", sa.Integer()),
            sa.Column("attention_signal", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("note", sa.Text()), sa.Column("source", sa.String(30), nullable=False),
            sa.Column("resolved_player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="SET NULL")),
            sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("highlight_rank IS NULL OR highlight_rank BETWEEN 1 AND 3", name="ck_unknown_rank"),
            sa.CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 10)", name="ck_unknown_rating"),
            sa.CheckConstraint("source IN ('own_report', 'neutral')", name="ck_unknown_source"))
    _add_column("player_observation_requests", sa.Column("origin_unidentified_signal_id", sa.Integer(), sa.ForeignKey("unidentified_player_signals.id", ondelete="SET NULL", name="fk_po_request_unknown_45")))
    for name, cols in [
        ("ix_unknown_match_user", ["match_id", "user_id"]),
        ("ix_unknown_resolved_player", ["resolved_player_id"]),
        ("ix_unknown_team_match", ["team_id", "match_id"])]:
        indexes = {r["name"] for r in sa.inspect(op.get_bind()).get_indexes("unidentified_player_signals")}
        if name not in indexes:
            op.create_index(name, "unidentified_player_signals", cols)
    # No destructive transformation/backfill of old player evidence.


def downgrade():
    # Deliberately non-destructive: preserve accumulated observations and identity history.
    pass
