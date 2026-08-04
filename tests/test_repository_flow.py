from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import func, select

from models.entities import PlayerEvaluation, ReportVersion
from repositories import scouting as repo
from services.report_service import generate_report_pdf


def seed(session):
    admin = repo.create_user(session, "Admin", "admin@example.com", "ClaveAdmin123!", role="admin", must_change_password=False)
    reporter = repo.create_user(session, "Informador", "info@example.com", "ClaveInfo123!", role="reporter", actor_id=admin.id, must_change_password=False)
    director = repo.create_user(session, "Director", "dir@example.com", "ClaveDirector123!", role="director", actor_id=admin.id, must_change_password=False)
    season = repo.create_season(session, "2026/27", actor_id=admin.id)
    comp = repo.create_competition(session, "Liga", actor_id=admin.id)
    own = repo.create_team(session, "Equipo propio", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "Equipo rival", actor_id=admin.id)
    own_player = repo.find_or_create_player(session, "Jugador Propio", primary_position="DC", actor_id=admin.id)
    rival_player = repo.find_or_create_player(session, "Jugador Rival", primary_position="MC", actor_id=admin.id)
    repo.assign_player_to_roster(session, own.id, season.id, own_player.id, 9, admin.id)
    repo.assign_player_to_roster(session, rival.id, season.id, rival_player.id, 8, admin.id)
    match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1", match_date=date(2026, 8, 1), home_team_id=own.id, away_team_id=rival.id, created_by=admin.id, status="published")
    for team, player, number, pos in [(own, own_player, 9, "DC"), (rival, rival_player, 8, "MC")]:
        repo.replace_participations(session, match.id, team.id, [{"selected": True, "player_id": player.id, "shirt_number": number, "starter": True, "position": pos, "minute_in": 0, "minute_out": 90, "captain": False}], admin.id)
    repo.assign_reporters(session, match.id, [reporter.id], admin.id)
    return admin, reporter, director, season, comp, own, rival, own_player, rival_player, match


def test_approved_rival_only_analytics_and_immutable_version(session_factory):
    with session_factory.begin() as session:
        admin, reporter, director, _, _, own, rival, own_player, rival_player, match = seed(session)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        report.opponent_overview = "Rival competitivo y con un interior especialmente interesante."
        parts = {p.player_id: p for p in repo.get_participations(session, match.id)}
        repo.upsert_evaluation(session, report.id, rival_player.id, rival.id, parts[rival_player.id].id, actor_id=reporter.id, observation_status="evaluated", general_rating=8.0, recommendation="Jugador interesante", short_note="Buen partido.", confidence="Alta")
        repo.upsert_evaluation(session, report.id, own_player.id, own.id, parts[own_player.id].id, actor_id=reporter.id, observation_status="evaluated", general_rating=9.5, short_note="Valoración interna.")
        assert repo.player_rankings(session) == []  # drafts are excluded
        submitted, version = repo.submit_report(session, report.id, reporter.id)
        assert submitted.status == "submitted"
        snapshot_before = version.snapshot_json
        repo.approve_report(session, report.id, director.id)
        rankings = repo.player_rankings(session)
        assert len(rankings) == 1
        assert rankings[0]["player_id"] == rival_player.id
        assert rankings[0]["avg_general"] == 8.0
        assert session.scalar(select(func.count(ReportVersion.id))) == 1
        assert session.get(ReportVersion, version.id).snapshot_json == snapshot_before
        payload = json.loads(snapshot_before)
        assert any(e["evaluation_scope"] == "rival" for e in payload["evaluations"])
        pdf = generate_report_pdf(session, report.id, version=version.version, mode="full")
        assert pdf.startswith(b"%PDF") and len(pdf) > 3000


def test_optimistic_revision_conflict(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, _, _, _, _, _, _, match = seed(session)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        revision = report.revision
        repo.save_report_summary(session, report.id, rival_level="Medio", opponent_overview="Primera edición", own_team_note=None, key_takeaways=None, standout_player_id=None, actor_id=reporter.id, expected_revision=revision)
        with pytest.raises(RuntimeError):
            repo.save_report_summary(session, report.id, rival_level="Alto", opponent_overview="Edición obsoleta", own_team_note=None, key_takeaways=None, standout_player_id=None, actor_id=reporter.id, expected_revision=revision)


def test_lineup_reconciliation_removes_draft_evaluation(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, _, _, _, rival, _, rival_player, match = seed(session)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        part = repo.get_participations(session, match.id, rival.id)[0]
        repo.upsert_evaluation(session, report.id, rival_player.id, rival.id, part.id, actor_id=reporter.id, observation_status="evaluated", general_rating=7.0)
        repo.replace_participations(session, match.id, rival.id, [], admin.id)
        assert session.scalar(select(func.count(PlayerEvaluation.id)).where(PlayerEvaluation.report_id == report.id)) == 0
