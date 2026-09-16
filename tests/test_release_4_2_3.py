"""Regression tests for 4.2.3 governance, catalog, incorporation, wizard."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select

from models.entities import AuditLog, Match, Report, ReportVersion, Team
from repositories import scouting as repo
from repositories import players as player_repo
from repositories import data_governance as gov
from repositories.player_catalog import search_players, teams_for_filter
from repositories.sporting_reading import save_neutral_opinion

ROOT = Path(__file__).resolve().parents[1]


def _seed(session):
    admin = repo.create_user(session, 'Admin', 'admin423@example.com', 'pass', role='admin', roles=['admin'])
    reporter = repo.create_user(session, 'Staff', 'staff423@example.com', 'pass', role='reporter', roles=['reporter'], actor_id=admin.id)
    season = repo.create_season(session, '2026/27', date(2026, 7, 1), date(2027, 6, 30), admin.id)
    comp = repo.create_competition(session, 'Liga 423', actor_id=admin.id)
    real = repo.create_team(session, 'C.D. Noname', actor_id=admin.id)
    fake = repo.create_team(session, 'Noname Club', actor_id=admin.id)
    rival = repo.create_team(session, 'Santa Marta', actor_id=admin.id)
    real_player = repo.find_or_create_player(session, 'Futbolista real', primary_position='DC', actor_id=admin.id)
    fake_player = repo.find_or_create_player(session, 'Futbolista de prueba', primary_position='DC', actor_id=admin.id)
    repo.assign_player_to_roster(session, real.id, season.id, real_player.id, 9, admin.id)
    repo.assign_player_to_roster(session, fake.id, season.id, fake_player.id, 11, admin.id)
    player_repo.set_own_team(session, real.id, admin.id)
    fake_match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name='Test',
        match_date=date(2026, 9, 1), home_team_id=fake.id, away_team_id=rival.id,
        created_by=admin.id, kickoff_at=datetime(2026, 9, 1, 18), schedule_status='confirmed', status='published')
    real_match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name='J1',
        match_date=date(2026, 9, 2), home_team_id=real.id, away_team_id=rival.id,
        created_by=admin.id, kickoff_at=datetime(2026, 9, 2, 18), schedule_status='confirmed', status='published')
    return admin, reporter, season, real, fake, rival, real_player, fake_player, fake_match, real_match


def test_own_team_is_consistent_protected_and_only_id_selected(session_factory):
    with session_factory.begin() as session:
        admin, _, _, real, fake, *_ = _seed(session)
        assert player_repo.get_own_team(session).id == real.id
        assert player_repo.get_setting(session, 'own_team_id') == str(real.id)
        assert [t.id for t in session.scalars(select(Team).where(Team.is_own_team.is_(True)))] == [real.id]
        with pytest.raises(ValueError, match='equipo propio'):
            gov.mark_team_test(session, real.id, admin.id, True)
        with pytest.raises(ValueError, match='equipo propio'):
            gov.archive_team(session, real.id, admin.id)
        gov.mark_team_test(session, fake.id, admin.id, True)
        with pytest.raises(ValueError, match='no ser de prueba'):
            player_repo.set_own_team(session, fake.id, admin.id)
        assert player_repo.get_own_team(session).id == real.id
        assert session.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == 'set_own_team')) >= 1


def test_test_team_and_matches_are_excluded_without_deleting_and_restorable(session_factory):
    with session_factory.begin() as session:
        admin, _, season, real, fake, _, real_player, fake_player, fake_match, real_match = _seed(session)
        assert len(repo.list_matches(session, season_id=season.id)) == 2
        gov.mark_team_test(session, fake.id, admin.id, True)
        assert [m.id for m in repo.list_matches(session, season_id=season.id)] == [real_match.id]
        assert [p['player'].id for p in search_players(session, season_id=season.id)['rows']] == [real_player.id]
        assert fake.id not in [t.id for t in teams_for_filter(session, season.id)]
        gov.archive_team(session, fake.id, admin.id)
        assert session.get(Team, fake.id).active is False
        gov.restore_team(session, fake.id, admin.id)
        assert session.get(Team, fake.id).is_test is True
        gov.mark_team_test(session, fake.id, admin.id, False)
        assert len(repo.list_matches(session, season_id=season.id)) == 2
        gov.mark_match_test(session, fake_match.id, admin.id, True)
        assert [m.id for m in repo.list_matches(session, season_id=season.id)] == [real_match.id]
        gov.archive_test_match(session, fake_match.id, admin.id)
        assert session.get(Match, fake_match.id).deleted_at is not None
        assert session.get(Match, fake_match.id).archived_previous_status == 'published'
        assert session.get(Match, fake_match.id).id in [m.id for m in repo.list_matches(session, include_archived=True)]
        gov.restore_test_match(session, fake_match.id, admin.id)
        assert session.get(Match, fake_match.id).status == 'published'
        assert session.get(Match, fake_match.id).deleted_at is None
        assert session.get(Match, fake_match.id).is_test is True
        assert len(repo.list_matches(session, season_id=season.id)) == 1
        gov.mark_match_test(session, fake_match.id, admin.id, False)
        assert len(repo.list_matches(session, season_id=season.id)) == 2
        assert session.get(Match, real_match.id).status == 'published'


def test_submitted_report_is_directly_incorporated_without_fictitious_reviewer(session_factory):
    with session_factory.begin() as session:
        admin, reporter, season, real, _, rival, own_player, _, _, match = _seed(session)
        opponent = repo.find_or_create_player(session, 'Rival evaluado', primary_position='DC', actor_id=admin.id)
        repo.assign_player_to_roster(session, rival.id, season.id, opponent.id, 7, admin.id)
        repo.replace_participations(session, match.id, real.id,
            [{'selected':True,'player_id':own_player.id,'starter':True,'position':'DC','minute_in':0,'minute_out':90,'captain':False}], admin.id)
        repo.replace_participations(session, match.id, rival.id,
            [{'selected':True,'player_id':opponent.id,'starter':True,'position':'DC','minute_in':0,'minute_out':90,'captain':False}], admin.id)
        repo.assign_reporters(session, match.id, [reporter.id], admin.id)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        rival_part = next(p for p in repo.get_participations(session, match.id) if p.player_id == opponent.id)
        repo.upsert_evaluation(session, report.id, opponent.id, rival.id, rival_part.id,
                               actor_id=reporter.id, observation_status='evaluated', general_rating=8.0)
        assert repo.player_rankings(session) == []
        delivered, version = repo.submit_report(session, report.id, reporter.id)
        assert delivered.status == 'incorporated'
        assert delivered.reviewer_id is None and delivered.approved_at is None
        assert delivered.finalized_at is not None and delivered.submitted_at is not None
        assert session.scalar(select(func.count(ReportVersion.id)).where(ReportVersion.report_id == report.id)) == 1
        assert len(repo.player_rankings(session)) == 1
        # Official analytics must react to test-data changes without deleting
        # this real report, player evaluation or its immutable PDF snapshot.
        gov.mark_match_test(session, match.id, admin.id, True)
        assert repo.player_rankings(session) == []
        assert session.get(Report, report.id) is report
        gov.mark_match_test(session, match.id, admin.id, False)
        assert len(repo.player_rankings(session)) == 1
        snapshot_json = version.snapshot_json
        repo.reopen_report(session, report.id, admin.id, 'Corregir puntuación del rival')
        assert report.status == 'returned' and report.version == 2
        assert session.get(ReportVersion, version.id).snapshot_json == snapshot_json
        assert repo.player_rankings(session) == []
        assert repo.submit_report(session, report.id, reporter.id)[0].status == 'incorporated'
        assert session.scalar(select(func.count(ReportVersion.id)).where(ReportVersion.report_id == report.id)) == 2
        assert len(repo.player_rankings(session)) == 1


def test_publish_stage_is_discoverable_and_formation_can_remain_unknown():
    source = (ROOT / 'views/postmatch.py').read_text(encoding='utf-8')
    assert "'4 · Revisar y PUBLICAR POSTPARTIDO →'" in source
    assert 'def _go_to_publish_423()' in source
    assert 'formation_options = [None, *FORMATIONS]' in source
    assert 'Titulares ya registrados en este mismo partido' in source
    assert 'XI propuesto automáticamente' not in source
    assert 'st.button("PUBLICAR POSTPARTIDO"' in source
    assert 'return slots_for(formation) or [' in source
    assert 'never a guessed XI' in source
