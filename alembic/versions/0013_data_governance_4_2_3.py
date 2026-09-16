"""Non-destructive test-data flags and reversible match/team archival.

Revision ID: 0013_data_governance_4_2_3
Revises: 0012_sporting_reading_4_2
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = '0013_data_governance_4_2_3'
down_revision = '0012_sporting_reading_4_2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if 'teams' in tables:
        cols = {col['name'] for col in insp.get_columns('teams')}
        if 'is_test' not in cols:
            op.add_column('teams', sa.Column('is_test', sa.Boolean(), nullable=False, server_default=sa.false()))
        if 'archived_at' not in cols:
            op.add_column('teams', sa.Column('archived_at', sa.DateTime(), nullable=True))
    if 'matches' in tables:
        cols = {col['name'] for col in insp.get_columns('matches')}
        if 'is_test' not in cols:
            op.add_column('matches', sa.Column('is_test', sa.Boolean(), nullable=False, server_default=sa.false()))
        if 'archived_previous_status' not in cols:
            op.add_column('matches', sa.Column('archived_previous_status', sa.String(30), nullable=True))
    # Deliberately do not mark any named team or match as test automatically.
    # The admin must inspect the real Supabase IDs and associations in the UI.
    # Report policy is a product choice for newly submitted reports, not retroactive
    # mass approval of historical 'submitted' rows.
    if 'app_settings' in tables:
        bind.execute(sa.text("UPDATE app_settings SET value = 'false' WHERE key = 'require_report_approval'"))


def downgrade() -> None:
    # Reversible code deployment must not drop the historical data flags.
    pass
