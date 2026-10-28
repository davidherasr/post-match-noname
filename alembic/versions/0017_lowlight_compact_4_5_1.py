"""4.5.1: optional least-outstanding ranking in own match evaluations.

Revision ID: 0017_lowlight_compact_4_5_1
Revises: 0016_partial_reading_4_5
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_lowlight_compact_4_5_1"
down_revision = "0016_partial_reading_4_5"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "player_evaluations" not in inspector.get_table_names():
        return
    present = {col["name"] for col in inspector.get_columns("player_evaluations")}
    if "lowlight_rank" not in present:
        op.add_column("player_evaluations", sa.Column("lowlight_rank", sa.Integer(), nullable=True))
    # Check constraints are backed up by repository-level validation in SQLite
    # and PostgreSQL; don't rewrite or recreate historic evaluation tables.


def downgrade():
    # Non-destructive by design: preserve the evidence.
    pass
