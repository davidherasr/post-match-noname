from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from repositories import scouting as repo
from repositories import sporting_reading as sporting_repo

ROOT = Path(__file__).resolve().parents[1]


def _seed(session):
    admin = repo.create_user(session, "Admin", "admin42@example.com", "1", role="admin", roles=["admin"])
    director = repo.create_user(session, "DD", "dd42@example.com", "1", role="director", roles=["director"], actor_id=admin.id)
    info_a = repo.create_user(session, "Info A", "a42@example.com", "1", role="reporter", roles=["reporter"], actor_id=admin.id)
    info_b = repo.create_user(session, "Info B", "b42@example.com", "1", role="reporter", roles=["reporter"], actor_id=admin.id)
    tracker = repo.create_user(session, "Tracker", "track42@example.com", "1", role="reporter", roles=["reporter"], actor_id=admin.id, can_track_players=True)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    comp = repo.create_competition(session, "Liga 4.2", actor_id=admin.id)
    own = repo.create_team(session, "C.D. Noname", is_own_team=True, actor_id=admin.id)
    a = repo.create_team(session, "Neutral A", actor_id=admin.id)
    b = repo.create_team(session, "Neutral B", actor_id=admin.id)
    return admin, director, info_a, info_b, tracker, season, comp, own, a, b


def test_neutral_staff_reading_is_weighted_and_only_creates_signals(session_factory):
    with session_factory.begin() as session:
        admin, director, info_a, info_b, tracker, season, comp, own, a, b = _seed(session)
        match = repo.create_match(
            session, season_id=season.id, competition_id=comp.id, round_name="J1",
            match_date=date(2026, 9, 13), kickoff_at=datetime(2026, 9, 13, 18, 0),
            schedule_status="confirmed", home_team_id=a.id, away_team_id=b.id,
            created_by=admin.id, status="scheduled",
        )
        player = repo.find_or_create_player(session, "Jugador Neutral", primary_position="DC", actor_id=admin.id)
        repo.assign_player_to_roster(session, a.id, season.id, player.id, 9, actor_id=admin.id)
        sporting_repo.upsert_staff_weight(session, actor_id=director.id, user_id=info_a.id, own_match_weight=1.0, neutral_match_weight=1.5)
        sporting_repo.upsert_staff_weight(session, actor_id=director.id, user_id=info_b.id, own_match_weight=1.0, neutral_match_weight=0.5)
        sporting_repo.save_neutral_opinion(
            session, match_id=match.id, user_id=info_a.id, home_team_rating=8, away_team_rating=6,
            summary="A domina", player_rows=[{"player_id": player.id, "team_id": a.id, "rating": 8.5, "note": "Ataca profundidad"}],
        )
        sporting_repo.save_neutral_opinion(
            session, match_id=match.id, user_id=info_b.id, home_team_rating=6, away_team_rating=7,
            summary="Más igualado", player_rows=[{"player_id": player.id, "team_id": a.id, "rating": 7.5, "note": "Buen desmarque"}],
        )
        reading = sporting_repo.neutral_match_reading(session, match.id)
        assert round(reading["home_weighted"], 2) == 7.5
        assert round(reading["away_weighted"], 2) == 6.25
        assert reading["players"][0]["mentions"] == 2
        assert round(reading["players"][0]["weighted_rating"], 2) == 8.25
        # Señalar no crea por sí solo un expediente de seguimiento.
        assert sporting_repo.user_can_track(session, info_a.id) is False


def test_tracking_is_special_permission_and_own_players_are_blocked(session_factory):
    with session_factory.begin() as session:
        admin, director, info_a, info_b, tracker, season, comp, own, a, b = _seed(session)
        own_player = repo.find_or_create_player(session, "Jugador No Name", primary_position="MC", actor_id=admin.id)
        external = repo.find_or_create_player(session, "Jugador Externo", primary_position="DC", actor_id=admin.id)
        repo.assign_player_to_roster(session, own.id, season.id, own_player.id, 8, actor_id=admin.id)
        repo.assign_player_to_roster(session, a.id, season.id, external.id, 9, actor_id=admin.id)

        with pytest.raises(PermissionError):
            sporting_repo.start_player_tracking(session, player_id=external.id, actor_id=info_a.id)
        with pytest.raises(ValueError):
            sporting_repo.start_player_tracking(session, player_id=own_player.id, actor_id=tracker.id)
        profile = sporting_repo.start_player_tracking(session, player_id=external.id, actor_id=tracker.id)
        assert profile.player_id == external.id
        assert profile.assigned_to == tracker.id


def test_active_42_ui_has_no_scout_assignment_workflow():
    jornada = (ROOT / "views/jornada.py").read_text(encoding="utf-8")
    calendar = (ROOT / "views/calendar.py").read_text(encoding="utf-8")
    player_hub = (ROOT / "views/player_hub.py").read_text(encoding="utf-8")
    admin = (ROOT / "views/admin.py").read_text(encoding="utf-8")
    squad = (ROOT / "views/squad.py").read_text(encoding="utf-8")

    assert "Dirección Deportiva · asignar seguimiento" not in jornada
    assert "Asignar trabajo de scouting" not in jornada
    assert "Asignar observación" not in calendar
    assert "Asignar próxima acción" not in player_hub
    assert '["admin", "director", "reporter"]' in admin
    assert "Puede realizar seguimiento individual de jugadores" in admin
    assert "Lectura deportiva" in squad
    assert "Criterio del staff" in squad
