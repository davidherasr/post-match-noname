"""Link postmatch evaluations to one optional detailed tracking observation.

Revision ID: 0014_unified_player_evidence_4_4_2
Revises: 0013_data_governance_4_2_3

Historical rows are untouched, including any existing duplicates.  The nullable
unique link only applies when someone explicitly enriches an evaluation.
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_unified_player_evidence_4_4_2"
down_revision = "0013_data_governance_4_2_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "scout_observations" not in sa.inspect(bind).get_table_names():
        return
    columns = {col["name"] for col in sa.inspect(bind).get_columns("scout_observations")}
    if "player_evaluation_id" not in columns:
        with op.batch_alter_table("scout_observations") as batch:
            batch.add_column(sa.Column("player_evaluation_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_scout_observation_evaluation_442", "player_evaluations", ["player_evaluation_id"], ["id"], ondelete="SET NULL")
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("scout_observations")}
    if "uq_scout_observation_evaluation_442" not in indexes:
        op.create_index("uq_scout_observation_evaluation_442", "scout_observations", ["player_evaluation_id"], unique=True)


def downgrade() -> None:
    # No destructive downgrade: historical link metadata must remain safe.
    pass
