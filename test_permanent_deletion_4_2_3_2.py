"""Cross-linked hard deletes require precise plans and keep unrelated history intact."""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from models import Base
from models.entities import (AppSetting, AuditLog, Match, MatchOpinion, Player, PlayerEvaluation,
                             Report, ReportAssignment, ReportVersion, Team, TeamRoster,
                             Participation, Document, Season, ScoutObservation)
from repositories import scouting as repo
from repositories import players as players_repo
from repositories import permanent_deletion as purge


@pytest.fixture()
def strict_db():
    engine = create_engine('sqlite:///:memory:')
    @event.listens_for(engine, 'connect')
    def fk_on(dbapi, _):
        dbapi.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()


def seeded(session):
    admin = repo.create_user(session, 'Admin', 'purge_admin@test.local', 'pw', role='admin', roles=['admin'])
    reporter = repo.create_user(session, 'Reporter', 'purge_staff@test.local', 'pw', role='reporter', roles=['reporter'], actor_id=admin.id)
    season = repo.create_season(session, 'Purge 2026/27', date(2026, 7, 1), date(2027, 6, 30), admin.id)
    competition = repo.create_competition(session, 'Purge Liga', actor_id=admin.id)
    real = repo.create_team(session, 'C.D. Noname', actor_id=admin.id)
    fake = repo.create_team(session, 'Noname Club', actor_id=admin.id)
    rival = repo.create_team(session, 'Santa Marta', actor_id=admin.id)
    players_repo.set_own_team(session, real.id, admin.id)
    players_repo.set_active_season(session, season.id, admin.id)
    own_player = repo.find_or_create_player(session, 'Futbolista real', actor_id=admin.id)
    fake_player = repo.find_or_create_player(session, 'Futbolista exclusivo fake', actor_id=admin.id)
    shared = repo.find_or_create_player(session, 'Futbolista compartido', actor_id=admin.id)
    repo.assign_player_to_roster(session, fake.id, season.id, fake_player.id, 9, admin.id)
    repo.assign_player_to_roster(session, fake.id, season.id, shared.id, 10, admin.id)
    repo.assign_player_to_roster(session, real.id, season.id, own_player.id, 11, admin.id)
    repo.assign_player_to_roster(session, real.id, season.id, shared.id, 12, admin.id)
    test_match = repo.create_match(session, season_id=season.id, competition_id=competition.id, round_name='Prueba',
        match_date=date(2026, 9, 1), home_team_id=fake.id, away_team_id=rival.id, created_by=admin.id,
        kickoff_at=datetime(2026, 9, 1, 17, 0), schedule_status='confirmed', status='published')
    real_match = repo.create_match(session, season_id=season.id, competition_id=competition.id, round_name='Real',
        match_date=date(2026, 9, 2), home_team_id=real.id, away_team_id=rival.id, created_by=admin.id,
        kickoff_at=datetime(2026, 9, 2, 17, 0), schedule_status='confirmed', status='published')
    session.flush()
    return admin, reporter, season, real, fake, rival, own_player, fake_player, shared, test_match, real_match


def _execute(session, roots, actor):
    plan = purge.build_plan(session, roots, actor)
    return plan, purge.execute_plan(session, roots, actor, plan.fingerprint)


def test_delete_test_team_includes_all_match_dependents_preserves_real_club(strict_db):
    with strict_db.begin() as session:
        admin, reporter, season, real, fake, rival, own_player, fake_player, shared, tm, rm = seeded(session)
        repo.assign_reporters(session, tm.id, [reporter.id], admin.id)
        report = repo.get_or_create_report(session, tm.id, reporter.id)
        report.status = 'incorporated'
        session.flush()
        rv = ReportVersion(report_id=report.id, version=1, status='incorporated', snapshot_json='{}', created_by=admin.id)
        session.add(rv)
        session.flush()
        session.add(Document(report_id=report.id, report_version_id=rv.id, version=1,
                             storage_bucket='private', storage_path='reports/proof.pdf'))
        session.add(PlayerEvaluation(report_id=report.id, player_id=fake_player.id, team_id=fake.id,
                                     observation_status='evaluated', general_rating=8))
        session.flush()
        plan = purge.build_plan(session, {'equipos':[fake.id]}, admin.id)
        assert len(plan.rows['matches']) == 1 and tm.id in plan.rows['matches']
        assert len(plan.rows['reports']) == 1
        assert len(plan.rows['documents']) == 1 and len(plan.external_files) == 1
        assert len(plan.rows['team_rosters']) == 2
        suggestions = purge.orphan_player_suggestions(session, plan)
        assert [pid for pid, _ in suggestions] == [fake_player.id]
        assert shared.id not in [pid for pid, _ in suggestions]
        fake_id, fake_player_id, match_id, real_match_id, shared_id, real_id = (fake.id, fake_player.id, tm.id, rm.id, shared.id, real.id)
        _, deleted = _execute(session, {'equipos':[fake_id], 'jugadores':[fake_player_id]}, admin.id)
        assert deleted['matches'] == 1 and deleted['players'] == 1
        assert session.get(Team, fake_id) is None
        assert session.get(Player, fake_player_id) is None
        assert session.get(Match, match_id) is None
        assert session.get(Match, real_match_id) is not None
        assert session.get(Player, shared_id) is not None
        assert players_repo.get_own_team(session).id == real_id
        assert session.scalar(select(func.count(Report.id))) == 0
        assert session.scalar(select(func.count(Document.id))) == 0
        assert session.scalar(select(func.count(AuditLog.id)).where(AuditLog.action=='permanent_delete_sporting_records')) == 1


def test_player_purge_clears_nullable_standout_but_keeps_report(strict_db):
    with strict_db.begin() as session:
        admin, reporter, _, real, _, _, real_player, _, _, _, rm = seeded(session)
        repo.assign_reporters(session, rm.id, [reporter.id], admin.id)
        report = repo.get_or_create_report(session, rm.id, reporter.id)
        report.standout_player_id = real_player.id
        session.flush()
        session.add(PlayerEvaluation(report_id=report.id, player_id=real_player.id, team_id=real.id,
                                     observation_status='evaluated', general_rating=7))
        session.flush()
        player_id, report_id, match_id = real_player.id, report.id, rm.id
        plan, _ = _execute(session, {'jugadores':[player_id]}, admin.id)
        assert ('reports', 'standout_player_id') in plan.detach
        assert session.get(Player, player_id) is None
        assert session.get(Report, report_id).standout_player_id is None
        assert session.get(Match, rm.id) is not None
        assert session.scalar(select(func.count(PlayerEvaluation.id)).where(PlayerEvaluation.player_id==player_id)) == 0


def test_season_purge_clears_active_setting_but_keeps_team_and_player(strict_db):
    with strict_db.begin() as session:
        admin, _, season, real, fake, _, own_player, _, _, tm, rm = seeded(session)
        season_id, test_match_id, real_match_id, team_id, player_id = season.id, tm.id, rm.id, real.id, own_player.id
        plan, _ = _execute(session, {'temporadas':[season_id]}, admin.id)
        assert 'active_season_id' in plan.settings
        assert len(plan.rows['matches']) == 2
        assert session.get(Season, season_id) is None
        assert session.get(Match, test_match_id) is None and session.get(Match, real_match_id) is None
        assert session.get(Team, team_id) is not None
        assert session.get(Player, player_id) is not None
        assert players_repo.get_setting(session, 'active_season_id') is None


def test_can_delete_own_team_only_with_explicit_id_and_clears_pointer(strict_db):
    with strict_db.begin() as session:
        admin, _, _, real, _, _, _, _, _, _, rm = seeded(session)
        team_id, match_id = real.id, rm.id
        plan, _ = _execute(session, {'equipos':[team_id]}, admin.id)
        assert plan.settings == ('own_team_id',)
        assert session.get(Team, team_id) is None and session.get(Match, match_id) is None
        assert players_repo.get_setting(session, 'own_team_id') is None


def test_nonadmin_is_denied_and_stale_preview_aborts_with_no_deletions(strict_db):
    with strict_db.begin() as session:
        admin, reporter, _, real, fake, _, _, _, _, tm, rm = seeded(session)
        with pytest.raises(PermissionError):
            purge.build_plan(session, {'equipos':[fake.id]}, reporter.id)
        with pytest.raises(PermissionError):
            purge.execute_plan(session, {'equipos':[fake.id]}, reporter.id, '0'*64)
        plan = purge.build_plan(session, {'equipos':[fake.id]}, admin.id)
        session.add(Participation(match_id=tm.id, team_id=fake.id,
                                  player_id=next(session.scalars(select(Player.id)).all().__iter__())))
        session.flush()
        with pytest.raises(ValueError, match='cambiado'):
            purge.execute_plan(session, {'equipos':[fake.id]}, admin.id, plan.fingerprint)
        assert session.get(Team, fake.id) is not None and session.get(Match, rm.id) is not None


def test_missing_ids_and_empty_selection_refused(strict_db):
    with strict_db.begin() as session:
        admin, *_ = seeded(session)
        with pytest.raises(ValueError, match='Selecciona'):
            purge.build_plan(session, {}, admin.id)
        with pytest.raises(ValueError, match='inexistentes'):
            purge.build_plan(session, {'jugadores':[999999]}, admin.id)
