from __future__ import annotations

from datetime import date

from core.formations import slots_for
from repositories import scouting as repo
from services.report_service import generate_report_pdf


def _seed(session):
    admin = repo.create_user(session, "Admin", "perf-admin@example.com", "ClaveAdmin123!", role="admin", must_change_password=False)
    reporter = repo.create_user(session, "Info", "perf-info@example.com", "ClaveInfo123!", role="reporter", actor_id=admin.id, must_change_password=False)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    comp = repo.create_competition(session, "Liga", actor_id=admin.id)
    own = repo.create_team(session, "No Name", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "Rival", actor_id=admin.id)
    match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1", match_date=date(2026,8,1), home_team_id=own.id, away_team_id=rival.id, created_by=admin.id, status="published")
    repo.assign_reporters(session, match.id, [reporter.id], admin.id)
    return admin, reporter, season, comp, own, rival, match


def test_formation_442_has_fixed_eleven_slots():
    slots = slots_for("4-4-2")
    assert len(slots) == 11
    assert [slot.code for slot in slots[:5]] == ["POR", "LD", "DFC", "DFC", "LI"]
    assert [slot.code for slot in slots[-2:]] == ["DC", "DC"]


def test_bulk_save_whole_team_updates_once_and_keeps_scope(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, _, own, rival, match = _seed(session)
        players = []
        for i, (name, pos) in enumerate([("Rival Uno", "POR"), ("Rival Dos", "DFC"), ("Rival Tres", "DC")], start=1):
            player = repo.find_or_create_player(session, name, primary_position=pos, actor_id=admin.id)
            players.append(player)
        parts = repo.replace_participations(session, match.id, rival.id, [
            {"selected": True, "player_id": p.id, "shirt_number": i, "starter": True, "position": p.primary_position, "minute_in": 0, "minute_out": 90, "captain": False}
            for i, p in enumerate(players, start=1)
        ], admin.id)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        initial_report_revision = report.revision
        rows = [
            {"player_id": p.player_id, "team_id": rival.id, "participation_id": p.id, "expected_revision": None,
             "observation_status": "evaluated", "general_rating": rating, "short_note": "Lote", "standout": rating >= 8.0, "pdf_include": True}
            for p, rating in zip(parts, [7.0, 8.2, 6.5])
        ]
        saved = repo.bulk_upsert_evaluations_fast(session, report.id, rows, reporter.id)
        assert saved == 3
        evaluations = repo.list_evaluations(session, report.id)
        assert len(evaluations) == 3
        assert all(e.evaluation_scope == "rival" for e in evaluations)
        assert report.revision == initial_report_revision + 1
        assert report.standout_player_id == players[1].id


def test_summary_pdf_is_available_for_daily_use(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, _, own, rival, match = _seed(session)
        own_player = repo.find_or_create_player(session, "Propio", primary_position="MC", actor_id=admin.id)
        rival_player = repo.find_or_create_player(session, "Rival PDF", primary_position="DC", actor_id=admin.id)
        own_part = repo.replace_participations(session, match.id, own.id, [{"selected": True, "player_id": own_player.id, "shirt_number": 8, "starter": True, "position": "MC", "minute_in": 0, "minute_out": 90, "captain": False}], admin.id)[0]
        rival_part = repo.replace_participations(session, match.id, rival.id, [{"selected": True, "player_id": rival_player.id, "shirt_number": 9, "starter": True, "position": "DC", "minute_in": 0, "minute_out": 90, "captain": False}], admin.id)[0]
        report = repo.get_or_create_report(session, match.id, reporter.id)
        repo.bulk_upsert_evaluations_fast(session, report.id, [
            {"player_id": own_player.id, "team_id": own.id, "participation_id": own_part.id, "observation_status": "evaluated", "general_rating": 7.2, "short_note": "Correcto", "standout": False, "pdf_include": True},
            {"player_id": rival_player.id, "team_id": rival.id, "participation_id": rival_part.id, "observation_status": "evaluated", "general_rating": 8.4, "short_note": "Muy peligroso al espacio", "standout": True, "pdf_include": True},
        ], reporter.id)
        pdf = generate_report_pdf(session, report.id, mode="executive")
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1500
