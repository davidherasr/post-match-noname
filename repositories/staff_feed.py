"""Read-only, permission-aware club activity. No new table and no inferred decisions.

Only official, delivered sporting information is shared in the general staff feed.
Internal DD notes, password/audit information and unanswered requests are excluded.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import select, or_, func, exists
from sqlalchemy.orm import Session, joinedload
from models.entities import (
    Match, MatchOpinion, MatchOpinionPlayer, PlayerSeasonDecision, Report, TeamRoster,
)
from repositories.data_governance import official_match_clause
from repositories.players import get_own_team

PUBLIC_DECISIONS = {"Interesante", "Seguimiento", "Prioritario"}


def _stamp(value):
    return value if isinstance(value, datetime) else datetime.min


def load_activity(session: Session, *, season_id: int, roles: set[str] | None = None,
                  limit: int = 12) -> list[dict]:
    """Return newest visible facts with immutable source links, never fabricated news."""
    roles = set(roles or ())
    official_ids = select(Match.id).where(Match.season_id == season_id, official_match_clause())
    own = get_own_team(session)
    own_player_ids = set()
    if own:
        own_player_ids = set(session.scalars(select(TeamRoster.player_id).where(
            TeamRoster.team_id == own.id, TeamRoster.season_id == season_id)).all())
    entries: list[dict] = []

    reports = list(session.scalars(
        select(Report).options(joinedload(Report.match).joinedload(Match.home_team),
                               joinedload(Report.match).joinedload(Match.away_team),
                               joinedload(Report.reporter))
        .where(Report.match_id.in_(official_ids),
               Report.status.in_(("incorporated", "approved", "final")))
        .order_by(Report.submitted_at.desc(), Report.id.desc()).limit(16)
    ).unique().all())
    for r in reports:
        if r.submitted_at is None:
            continue
        entries.append({"kind": "report", "date": r.submitted_at, "match_id": r.match_id,
            "title": "Lectura incorporada",
            "detail": (f"{r.reporter.full_name} · "
                       f"{r.match.home_team.name} – {r.match.away_team.name}"),
            "source": "Informe de partido"})

    opinions = list(session.scalars(
        select(MatchOpinion).options(joinedload(MatchOpinion.user),
             joinedload(MatchOpinion.match).joinedload(Match.home_team),
             joinedload(MatchOpinion.match).joinedload(Match.away_team))
        .where(MatchOpinion.match_id.in_(official_ids), or_(
            MatchOpinion.home_team_rating.is_not(None),
            MatchOpinion.away_team_rating.is_not(None),
            func.length(func.trim(MatchOpinion.summary)) >= 5,
            exists(select(MatchOpinionPlayer.id).where(
                MatchOpinionPlayer.opinion_id == MatchOpinion.id)),
        ))
        .order_by(MatchOpinion.updated_at.desc(), MatchOpinion.id.desc()).limit(16)
    ).unique().all())
    for o in opinions:
        entries.append({"kind": "neutral", "date": o.updated_at, "match_id": o.match_id,
            "title": "Nueva lectura de liga" if o.created_at == o.updated_at else "Lectura de liga actualizada",
            "detail": f"{o.user.full_name} · {o.match.home_team.name} – {o.match.away_team.name}",
            "source": "Lectura neutral"})

    # DD actions are derived from their explicit, audited decisions. Display
    # status only, never confidential director_note or criterion scores.
    decisions = list(session.scalars(
        select(PlayerSeasonDecision).options(joinedload(PlayerSeasonDecision.player),
                                              joinedload(PlayerSeasonDecision.updater))
        .where(PlayerSeasonDecision.season_id == season_id)
        .order_by(PlayerSeasonDecision.updated_at.desc(), PlayerSeasonDecision.id.desc()).limit(100)
    ).unique().all())
    for d in decisions:
        if d.player_id in own_player_ids:
            continue
        if d.status not in PUBLIC_DECISIONS and "director" not in roles:
            continue
        if d.status in {"Sin decisión", "Base", "Observado"}:
            continue
        person = d.player.display_name or d.player.full_name
        author = d.updater.full_name if d.updater else "Dirección Deportiva"
        entries.append({"kind": "decision", "date": d.updated_at,
            "player_id": d.player_id, "title": f"Estado DD: {d.status}",
            "detail": f"{author} · {person}", "source": "Decisión deportiva actual"})
    entries.sort(key=lambda row: (_stamp(row.get("date")), row.get("kind", "")), reverse=True)
    return entries[:max(1, min(50, int(limit)))]
