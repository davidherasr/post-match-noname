"""4.4.1: fast ratings, direct completion and voluntary assignments."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from core.report_ui_flow import clear_submitted_report_state
from core.score_picker import rating_choices, rating_from_choice
from models.entities import AuditLog, Report, ReportAssignment
from repositories import scouting as repo
from repositories import workspaces
from repositories import reports as report_repo

ROOT = Path(__file__).resolve().parents[1]


def _seed(session):
    admin = repo.create_user(session, "Administrador", "admin441@example.com", "pass", role="admin", roles=["admin"])
    reporter = repo.create_user(session, "Informador", "rep441@example.com", "pass", role="reporter", roles=["reporter"], actor_id=admin.id)
    director = repo.create_user(session, "Director", "dd441@example.com", "pass", role="director", roles=["director"], actor_id=admin.id)
    hybrid = repo.create_user(session, "Director e informador", "hybrid441@example.com", "pass", role="director", roles=["director", "reporter"], actor_id=admin.id)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Regional", actor_id=admin.id)
    own = repo.create_team(session, "C.D. Noname", actor_id=admin.id)
    rival = repo.create_team(session, "Equipo rival", actor_id=admin.id)
    repo.set_own_team(session, own.id, admin.id)
    match = repo.create_match(session, season_id=season.id, competition_id=comp.id,
                              round_name="J1", match_date=date(2026, 9, 12),
                              home_team_id=own.id, away_team_id=rival.id, created_by=admin.id,
                              kickoff_at=datetime(2026, 9, 12, 17), schedule_status="confirmed", status="published")
    return admin, reporter, director, hybrid, season, own, rival, match


def test_rating_is_one_tap_integer_but_preserves_historical_decimals():
    options, selected = rating_choices(0)
    assert options == ["Sin evaluar"] + [str(n) for n in range(1, 11)]
    assert selected == "Sin evaluar" and rating_from_choice(selected) == 0.0
    for number in range(1, 11):
        _, selected = rating_choices(number)
        assert selected == str(number) and rating_from_choice(selected) == float(number)
    options, selected = rating_choices(8.5)
    assert selected == "8,5" and "8,5" in options and rating_from_choice(selected) == 8.5
    assert rating_from_choice(None) == 0.0
    with pytest.raises(ValueError):
        rating_choices(11)
    with pytest.raises(ValueError):
        rating_from_choice("11")


def test_completion_clears_only_its_widget_state():
    state = {"eval33_13_21_rating": 7.0, "eval33_13_21_rating_choice": "7",
             "eval_saved_snapshot_34_13_3": {}, "report_stage_13": "finish",
             "report_workspace_33_13": {"x": 1}, "confirm_submit_38_13": True,
             "eval33_14_22_rating": 6.0, "report_stage_130": "own",
             "report_workspace_33_130": {"x": 130}, "report_submission_notice": {"match_id": 4}}
    clear_submitted_report_state(state, 13)
    assert all(not key.startswith("eval33_13_") for key in state)
    assert "report_stage_13" not in state and "report_workspace_33_13" not in state
    assert state["eval33_14_22_rating"] == 6.0
    assert state["report_stage_130"] == "own" and state["report_workspace_33_130"] == {"x": 130}
    assert state["report_submission_notice"]["match_id"] == 4


def test_informador_can_decline_and_admin_can_reactivate_without_deleting_data(session_factory, monkeypatch):
    with session_factory.begin() as session:
        admin, reporter, _, _, season, _, _, match = _seed(session)
        repo.assign_reporters(session, match.id, [reporter.id], admin.id)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        report.own_team_note = "Borrador conservado"
        monkeypatch.setattr(workspaces, "local_today", lambda: date(2026, 9, 16))
        assert any(t["match_id"] == match.id for t in workspaces.load_home_workspace(session, user_id=reporter.id, roles={"reporter"})["tasks"])
        waived = report_repo.decline_report_assignment(session, match.id, reporter.id, "No puedo asistir")
        assert waived.status == "declined" and not waived.required
        assert session.get(Report, report.id).own_team_note == "Borrador conservado"
        assert not any(t["match_id"] == match.id for t in workspaces.load_home_workspace(session, user_id=reporter.id, roles={"reporter"})["tasks"])
        with pytest.raises(PermissionError):
            repo.get_or_create_report(session, match.id, reporter.id)
        with pytest.raises(PermissionError):
            repo.save_report_summary(session, report.id, rival_level=None, opponent_overview=None,
                                     own_team_note="Cambio indebido", key_takeaways=None,
                                     standout_player_id=None, actor_id=reporter.id)
        assert session.scalar(select(AuditLog).where(AuditLog.action == "decline_report_assignment"))
        restored = repo.assign_reporters(session, match.id, [reporter.id], admin.id)[0]
        assert restored.status == "pending" and restored.required
        assert repo.get_or_create_report(session, match.id, reporter.id).id == report.id
        assert any(t["match_id"] == match.id for t in workspaces.load_home_workspace(session, user_id=reporter.id, roles={"reporter"})["tasks"])


def test_cannot_decline_delivered_work(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, _, season, _, _, match = _seed(session)
        repo.assign_reporters(session, match.id, [reporter.id], admin.id)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        report.own_team_rating = 7.0
        report.own_team_note = "Lectura colectiva suficientemente extensa"
        repo.submit_report(session, report.id, reporter.id)
        with pytest.raises(ValueError):
            report_repo.decline_report_assignment(session, match.id, reporter.id)
        assert session.get(Report, report.id).status == "incorporated"


def test_director_can_volunteer_only_when_also_informador_and_match_is_official(session_factory):
    with session_factory.begin() as session:
        admin, _, director, hybrid, season, own, rival, match = _seed(session)
        with pytest.raises(PermissionError, match="Informador"):
            report_repo.claim_director_report(session, match.id, director.id)
        assignment = report_repo.claim_director_report(session, match.id, hybrid.id)
        assert assignment.status == "pending" and not assignment.required
        assert report_repo.claim_director_report(session, match.id, hybrid.id).id == assignment.id
        report = repo.get_or_create_report(session, match.id, hybrid.id)
        assert report.reporter_id == hybrid.id
        assert session.scalar(select(AuditLog).where(AuditLog.action == "claim_director_report"))
        third = repo.create_team(session, "Otro club de liga", actor_id=admin.id)
        other = repo.create_match(session, season_id=season.id, competition_id=match.competition_id,
                                  round_name="J2", match_date=date(2026, 9, 19),
                                  home_team_id=rival.id, away_team_id=third.id, created_by=admin.id,
                                  kickoff_at=datetime(2026, 9, 19, 17), schedule_status="confirmed", status="published")
        with pytest.raises(ValueError, match="postpartido propio"):
            report_repo.claim_director_report(session, other.id, hybrid.id)
        match.is_test = True
        with pytest.raises(ValueError, match="oficial"):
            report_repo.claim_director_report(session, match.id, hybrid.id)


def test_ui_wiring_of_direct_completion_and_voluntary_assignments():
    reports = (ROOT / "views/reports.py").read_text(encoding="utf-8")
    jornada = (ROOT / "views/jornada.py").read_text(encoding="utf-8")
    home = (ROOT / "views/home.py").read_text(encoding="utf-8")
    assert "st.pills(" in reports and "number_input(" not in reports
    assert 'request_navigation("Inicio")' in reports
    assert "report_submission_notice" in reports and "report_submission_notice" in home
    assert "render_decline_control" in reports and "render_decline_control" in jornada
    assert "claim_director_report" in jornada
    assert "can_direct(user) and can_report(user)" in jornada
