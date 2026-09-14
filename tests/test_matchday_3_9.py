from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from core.calendar_import import CALENDAR_PARSER_VERSION, parse_calendar_text
from core.clock import local_today
from core.schedule import is_schedule_confirmed
from repositories import calendar as calendar_repo
from repositories import scouting as repo
from repositories import workspaces


def _real_j1(session):
    admin = repo.create_user(
        session, "Admin 39", "admin39@example.com", "ValidPass123!",
        role="admin", roles=["admin", "director", "scout", "reporter"], must_change_password=False,
    )
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Regional Preferente", actor_id=admin.id)
    own = repo.create_team(session, "C.D. Noname", short_name="NONAME", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "La Cistérniga C.F.", short_name="LA CISTÉRNIGA", actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    rows, errors = parse_calendar_text(
        "1;13/09/2026;La Cistérniga C.F.;C.D. Noname",
        default_year=2026,
    )
    assert not errors
    calendar_repo.import_fixtures(
        session, season_id=season.id, competition_id=comp.id, rows=rows, actor_id=admin.id,
    )
    match = calendar_repo.list_calendar(session, season_id=season.id, team_id=own.id)[0]
    return admin, season, comp, own, rival, match


def test_calendar_parser_version_is_39_and_real_j1_is_provisional():
    assert CALENDAR_PARSER_VERSION == "3.9.0"
    rows, errors = parse_calendar_text("1;13/09/2026;La Cistérniga C.F.;C.D. Noname", default_year=2026)
    assert errors == []
    assert rows[0]["round_name"] == "Jornada 1"
    assert rows[0]["match_date"] == date(2026, 9, 13)
    assert rows[0]["kickoff_at"] is None
    assert rows[0]["schedule_status"] == "provisional"


def test_default_round_opens_real_j1_on_matchday(session_factory, monkeypatch):
    with session_factory.begin() as session:
        _, season, _, own, _, _ = _real_j1(session)
        monkeypatch.setattr(workspaces, "local_today", lambda: date(2026, 9, 13))
        assert workspaces.default_round(session, season.id, own.id) == "Jornada 1"


def test_home_workspace_marks_real_j1_as_matchday(session_factory, monkeypatch):
    with session_factory.begin() as session:
        admin, _, _, _, _, match = _real_j1(session)
        monkeypatch.setattr(workspaces, "local_today", lambda: date(2026, 9, 13))
        data = workspaces.load_home_workspace(session, user_id=admin.id, roles={"admin", "director", "scout", "reporter"})
        assert data["next_match"].id == match.id
        assert data["is_matchday"] is True
        assert any(task["kind"] == "schedule" and task["match_id"] == match.id for task in data["tasks"])


def test_readiness_detects_real_j1_without_inventing_kickoff(session_factory, monkeypatch):
    with session_factory.begin() as session:
        _, _, _, _, _, match = _real_j1(session)
        monkeypatch.setattr(workspaces, "local_today", lambda: date(2026, 9, 13))
        data = workspaces.load_operational_readiness(session)
        assert data["fixture_count"] == 1
        assert data["round_count"] == 1
        assert data["today_match"].id == match.id
        assert not is_schedule_confirmed(data["today_match"])
        assert any("hora real" in warning for warning in data["warnings"])


def test_readiness_becomes_operational_after_real_time_confirmation(session_factory, monkeypatch):
    with session_factory.begin() as session:
        admin, _, _, _, _, match = _real_j1(session)
        monkeypatch.setattr(workspaces, "local_today", lambda: date(2026, 9, 13))
        calendar_repo.update_schedule(session, match.id, admin.id, kickoff_at=datetime(2026, 9, 13, 17, 30))
        data = workspaces.load_operational_readiness(session)
        assert data["today_match"].kickoff_at == datetime(2026, 9, 13, 17, 30)
        assert is_schedule_confirmed(data["today_match"])
        assert not any("hora real" in warning for warning in data["warnings"])


def test_readiness_counts_real_noname_roster(session_factory, monkeypatch):
    with session_factory.begin() as session:
        admin, season, _, own, _, _ = _real_j1(session)
        monkeypatch.setattr(workspaces, "local_today", lambda: date(2026, 9, 13))
        player = repo.find_or_create_player(session, "Jugador No Name J1", primary_position="MC", actor_id=admin.id)
        repo.assign_player_to_roster(session, own.id, season.id, player.id, 8, actor_id=admin.id)
        data = workspaces.load_operational_readiness(session)
        assert data["own_roster_count"] == 1
        assert not any("plantilla" in warning.lower() for warning in data["warnings"])


def test_matchday_clock_returns_a_date():
    assert isinstance(local_today(), date)


def test_calendar_ui_has_no_fabricated_1700_default():
    source = Path("views/calendar.py").read_text(encoding="utf-8")
    assert "time(17, 0)" not in source
    assert "Hora definitiva (HH:MM)" in source


def test_calendar_ui_no_longer_navigates_to_legacy_modules():
    source = Path("views/calendar.py").read_text(encoding="utf-8")
    assert 'main_navigation"] = "Nuevo postpartido"' not in source
    assert 'main_navigation"] = "Misiones"' not in source
    assert 'request_navigation("Jornada")' in source


def test_reports_use_cumulative_capabilities_not_primary_role():
    source = Path("views/reports.py").read_text(encoding="utf-8")
    assert 'user["role"]' not in source
    assert "can_direct(user)" in source
