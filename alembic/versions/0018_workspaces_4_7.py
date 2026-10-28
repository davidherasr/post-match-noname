"""4.7 additive sporting collaboration, private drafts, director inbox and corrections.

Revision ID: 0018_workspaces_4_7
Revises: 0017_lowlight_compact_4_5_1
"""
from alembic import op
import sqlalchemy as sa

revision = '0018_workspaces_4_7'
down_revision = '0017_lowlight_compact_4_5_1'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Create only the new named entities; never recreate or alter historic rows.
    from models.entities import (
        SportingContribution47, ActivityEvent47, ActivityState47,
        PlayerProposal47, StaffRequest47, DataCorrection47, MatchPriority47,
    )
    for model in (SportingContribution47, ActivityEvent47, ActivityState47,
                  PlayerProposal47, StaffRequest47, DataCorrection47, MatchPriority47):
        model.__table__.create(bind, checkfirst=True)
    # Preserve continuity from 4.6: use source-backed historic records rather
    # than claiming the transition happened at migration time. This backfill is
    # idempotent and never touches the original reports/opinions.
    if sa.inspect(bind).has_table("reports") and sa.inspect(bind).has_table("matches"):
        bind.execute(sa.text("""
        INSERT INTO activity_events_47
            (season_id, actor_id, kind, title, detail, target_type, target_id,
             audience, recipient_id, created_at)
        SELECT m.season_id, r.reporter_id, 'legacy_report',
               'Informe histórico entregado', 'Informe incorporado antes de 4.7',
               'legacy_report', r.id, 'director', NULL, r.submitted_at
        FROM reports r JOIN matches m ON m.id = r.match_id
        WHERE r.status IN ('incorporated','approved','final')
          AND r.submitted_at IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM activity_events_47 e
              WHERE e.target_type = 'legacy_report' AND e.target_id = r.id)
    """))
    if sa.inspect(bind).has_table("match_opinions") and sa.inspect(bind).has_table("matches"):
        bind.execute(sa.text("""
        INSERT INTO activity_events_47
            (season_id, actor_id, kind, title, detail, target_type, target_id,
             audience, recipient_id, created_at)
        SELECT m.season_id, o.user_id, 'legacy_opinion',
               'Lectura de liga histórica', 'Opinión registrada antes de 4.7',
               'legacy_opinion', o.id, 'director', NULL, o.updated_at
        FROM match_opinions o JOIN matches m ON m.id = o.match_id
        WHERE o.updated_at IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM activity_events_47 e
              WHERE e.target_type = 'legacy_opinion' AND e.target_id = o.id)
    """))


def downgrade():
    # No destructive downgrade of sporting evidence.
    pass
