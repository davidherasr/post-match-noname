"""4.7.4 · Explicit two-XI publication gate (non-destructive).

Revision ID: 0019_rating_release_4_7_3
Revises: 0018_workspaces_4_7
"""
from alembic import op

revision = '0019_rating_release_4_7_3'
down_revision = '0018_workspaces_4_7'
branch_labels = None
depends_on = None


def upgrade():
    from models.entities import MatchRatingRelease473
    MatchRatingRelease473.__table__.create(op.get_bind(), checkfirst=True)
    # No automatic activation of historical matches. Older data remains intact.


def downgrade():
    # Intentional: never remove the publication history in a destructive rollback.
    pass
