"""Regression: a published own match must reach a real assigned Informador."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select

from core.postmatch_validation import validate_postmatch_draft
from models.entities import Match, ReportAssignment
from repositories import scouting as repo
from repositories import players as players_repo
from repositories import workspaces

ROOT = Path(__file__).resolve().parents[1]


def _published_match(session):
    admin = repo.create_user(session, 'Administrator', 'admin4231@example.test', 'pass', role='admin', roles=['admin'])
    informador = repo.create_user(session, 'Informador', 'report4231@example.test', 'pass', role='reporter', roles=['reporter'], actor_id=admin.id)
    season = repo.create_season(session, 'Temporada 4231', date(2026, 7, 1), date(2027, 6, 30), admin.id)
    comp = repo.create_competition(session, 'Liga', actor_id=admin.id)
    own = repo.create_team(session, 'C.D. Noname', actor_id=admin.id)
    rival = repo.create_team(session, 'Rival real', actor_id=admin.id)
    players_repo.set_own_team(session, own.id, admin.id)
    match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name='J1',
        match_date=date(2026, 9, 12), home_team_id=rival.id, away_team_id=own.id,
        created_by=admin.id, kickoff_at=datetime(2026, 9, 12, 17, 0), schedule_status='confirmed', status='published')
    session.flush()
    return admin, informador, match


def test_postmatch_publish_requires_at_least_one_reporter():
    valid = dict(kickoff_time='17:00', own_xi=[{'player_id': i} for i in range(1, 12)],
        rival_xi=[{'name': f'Rival {i}'} for i in range(1, 12)],
        own_subs=[], rival_subs=[], reporter_ids=[])
    errors, warnings = validate_postmatch_draft(valid)
    assert len(errors) == 1
    assert 'Informador' in errors[0]
    assert warnings == []
    valid['reporter_ids'] = [42]
    assert validate_postmatch_draft(valid) == ([], [])


def test_admin_recovers_published_match_and_informador_receives_task(session_factory):
    with session_factory.begin() as session:
        admin, informador, match = _published_match(session)
        initial = workspaces.load_match_workspace(session, match_id=match.id, user_id=informador.id)
        assert initial['is_own_match'] and initial['my_assignment'] is None
        assert initial['reports'] == [] and initial['assignments'] == []
        saved = repo.assign_reporters(session, match.id, [informador.id], admin.id,
                                     due_at=datetime(2026, 9, 13, 23, 59))
        assert len(saved) == 1 and saved[0].status == 'pending'
        assert session.get(Match, match.id).status == 'published'
        assert workspaces.load_match_workspace(session, match_id=match.id,
                                               user_id=informador.id)['my_assignment'].user_id == informador.id
        home = workspaces.load_home_workspace(session, user_id=informador.id, roles={'reporter'})
        assert any(t['kind'] == 'report' and t['match_id'] == match.id for t in home['tasks'])
        repo.assign_reporters(session, match.id, [informador.id], admin.id)
        assert session.scalar(select(func.count(ReportAssignment.id)).where(ReportAssignment.match_id == match.id)) == 1
        report = repo.get_or_create_report(session, match.id, informador.id)
        assert report.reporter_id == informador.id
        assert any(t['kind'] == 'report' for t in workspaces.load_home_workspace(session,
                                          user_id=informador.id, roles={'reporter'})['tasks'])


def test_invalid_or_admin_only_assignment_is_rejected_not_silently_ignored(session_factory):
    with session_factory.begin() as session:
        admin, informador, match = _published_match(session)
        with pytest.raises(ValueError, match='rol Informador'):
            repo.assign_reporters(session, match.id, [admin.id], admin.id)
        with pytest.raises(ValueError, match='usuario ID'):
            repo.assign_reporters(session, match.id, [987654], admin.id)
        assert session.scalar(select(func.count(ReportAssignment.id)).where(ReportAssignment.match_id == match.id)) == 0
        assert repo.assign_reporters(session, match.id, [informador.id], admin.id)


def test_admin_recovery_is_reachable_and_informador_has_direct_route():
    jornada = (ROOT / 'views/jornada.py').read_text(encoding='utf-8')
    home = (ROOT / 'views/home.py').read_text(encoding='utf-8')
    postmatch = (ROOT / 'views/postmatch.py').read_text(encoding='utf-8')
    assert 'def _manage_postmatch_assignments_4231(' in jornada
    assert 'if not can_admin(user) or match.status != "published":' in jornada
    assert 'matches_repo.assign_reporters(session, match.id, selected_ids' in jornada
    assert 'no tiene asignación' in jornada
    assert 'def _open_report(match_id: int)' in home
    assert '"match_hub_mode"] = "report"' in home
    assert '"Rellenar informe"' in home
    assert 'errors, warnings = _validate_draft_for_publish(d)' in postmatch
    assert 'disabled=bool(errors)' in postmatch
