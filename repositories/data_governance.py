"""4.2.3 · A single, audited and reversible boundary for non-sporting test data.

Never infer test status from a club name: an administrator must select actual IDs.
This module does not delete, merge or rewrite sporting history.
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from models.entities import (Team, Match, TeamRoster, Participation, Report,
                             ReportAssignment, MatchOpinion, PlayerEvaluation, ScoutObservation)
from repositories.common import UTC_NOW, audit
from repositories.users import assert_role


def excluded_team_ids():
    return select(Team.id).where(or_(Team.is_test.is_(True), Team.archived_at.is_not(None)))


def official_match_clause():
    """Apply to *all* official calendar/report/reading queries (SQL-level filter)."""
    excluded = excluded_team_ids()
    return and_(Match.deleted_at.is_(None), Match.status != 'archived',
                Match.is_test.is_(False),
                ~Match.home_team_id.in_(excluded), ~Match.away_team_id.in_(excluded))


def official_team_clause():
    return and_(Team.is_test.is_(False), Team.archived_at.is_(None))


def team_dependencies(session: Session, team_id: int) -> dict[str, int]:
    tid = int(team_id)
    match_ids = select(Match.id).where(or_(Match.home_team_id == tid, Match.away_team_id == tid))
    return {
        'partidos': int(session.scalar(select(func.count(Match.id)).where(Match.id.in_(match_ids))) or 0),
        'plantillas': int(session.scalar(select(func.count(TeamRoster.id)).where(TeamRoster.team_id == tid)) or 0),
        'participaciones': int(session.scalar(select(func.count(Participation.id)).where(Participation.team_id == tid)) or 0),
        'informes': int(session.scalar(select(func.count(Report.id)).where(Report.match_id.in_(match_ids))) or 0),
        'lecturas': int(session.scalar(select(func.count(MatchOpinion.id)).where(MatchOpinion.match_id.in_(match_ids))) or 0),
    }


def match_dependencies(session: Session, match_id: int) -> dict[str, int]:
    mid = int(match_id)
    report_ids = select(Report.id).where(Report.match_id == mid)
    return {
        'participaciones': int(session.scalar(select(func.count(Participation.id)).where(Participation.match_id == mid)) or 0),
        'asignaciones': int(session.scalar(select(func.count(ReportAssignment.id)).where(ReportAssignment.match_id == mid)) or 0),
        'informes': int(session.scalar(select(func.count(Report.id)).where(Report.match_id == mid)) or 0),
        'valoraciones': int(session.scalar(select(func.count(PlayerEvaluation.id)).where(PlayerEvaluation.report_id.in_(report_ids))) or 0),
        'lecturas': int(session.scalar(select(func.count(MatchOpinion.id)).where(MatchOpinion.match_id == mid)) or 0),
        'observaciones_formales': int(session.scalar(select(func.count(ScoutObservation.id)).where(ScoutObservation.match_id == mid)) or 0),
    }


def mark_team_test(session: Session, team_id: int, actor_id: int, is_test: bool) -> Team:
    assert_role(session, actor_id, 'admin')
    team = session.get(Team, int(team_id))
    if team is None:
        raise ValueError('Equipo no encontrado.')
    from repositories.players import get_own_team
    own = get_own_team(session)
    if is_test and (team.is_own_team or (own and own.id == team.id)):
        raise ValueError('Cambia primero el equipo propio: no se puede marcar como prueba.')
    before = {'is_test': bool(team.is_test)}
    team.is_test = bool(is_test)
    audit(session, actor_id, 'mark_team_test', 'team', team.id,
          before=before, after={'is_test': bool(team.is_test)})
    return team


def archive_team(session: Session, team_id: int, actor_id: int) -> Team:
    assert_role(session, actor_id, 'admin')
    team = session.get(Team, int(team_id))
    if team is None:
        raise ValueError('Equipo no encontrado.')
    from repositories.players import get_own_team
    own = get_own_team(session)
    if team.is_own_team or (own and own.id == team.id):
        raise ValueError('El equipo propio está protegido: selecciona otro equipo válido primero.')
    if not team.is_test:
        raise ValueError('Marca y comprueba este equipo como dato de prueba antes de archivarlo.')
    if team.archived_at is not None:
        raise ValueError('El equipo ya está archivado.')
    if not team.active:
        raise ValueError('El equipo ya está inactivo; revisa su estado antes del archivado.')
    team.archived_at = UTC_NOW()
    team.active = False
    audit(session, actor_id, 'archive_test_team', 'team', team.id,
          before={'active': True, 'archived_at': None},
          after={'active': False, 'archived_at': team.archived_at},
          detail=str(team_dependencies(session, team.id)))
    return team


def restore_team(session: Session, team_id: int, actor_id: int) -> Team:
    assert_role(session, actor_id, 'admin')
    team = session.get(Team, int(team_id))
    if team is None or team.archived_at is None:
        raise ValueError('No hay un equipo archivado con ese ID.')
    team.archived_at = None
    team.active = True
    audit(session, actor_id, 'restore_test_team', 'team', team.id,
          after={'active': True, 'is_test': team.is_test})
    return team


def mark_match_test(session: Session, match_id: int, actor_id: int, is_test: bool) -> Match:
    assert_role(session, actor_id, 'admin')
    match = session.get(Match, int(match_id))
    if not match:
        raise ValueError('Partido no encontrado.')
    old = bool(match.is_test)
    match.is_test = bool(is_test)
    match.revision = (match.revision or 0) + 1
    audit(session, actor_id, 'mark_match_test', 'match', match.id,
          before={'is_test': old}, after={'is_test': bool(is_test)})
    return match


def archive_test_match(session: Session, match_id: int, actor_id: int) -> Match:
    assert_role(session, actor_id, 'admin')
    match = session.get(Match, int(match_id))
    if not match or match.deleted_at is not None or match.status == 'archived':
        raise ValueError('Partido inexistente o ya archivado.')
    if not match.is_test:
        raise ValueError('Marca y confirma este partido como dato de prueba antes de archivarlo.')
    old = match.status
    deps = match_dependencies(session, match.id)
    match.archived_previous_status = old
    match.status = 'archived'
    match.deleted_at = UTC_NOW()
    match.revision = (match.revision or 0) + 1
    audit(session, actor_id, 'archive_test_match', 'match', match.id,
          before={'status': old, 'is_test': True},
          after={'status': 'archived', 'deleted_at': match.deleted_at}, detail=str(deps))
    return match


def restore_test_match(session: Session, match_id: int, actor_id: int) -> Match:
    assert_role(session, actor_id, 'admin')
    match = session.get(Match, int(match_id))
    if not match or match.status != 'archived' or match.deleted_at is None or not match.archived_previous_status:
        raise ValueError('No hay un partido archivado por este flujo que pueda restaurarse con seguridad.')
    previous = match.archived_previous_status
    match.status = previous
    match.deleted_at = None
    match.archived_previous_status = None
    match.revision = (match.revision or 0) + 1
    audit(session, actor_id, 'restore_test_match', 'match', match.id,
          after={'status': previous, 'is_test': match.is_test})
    return match
