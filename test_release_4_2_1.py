from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from core.permissions import can_admin, can_direct, can_report, can_track_players
from repositories import scouting as repo
from repositories import sporting_reading as sporting_repo

ROOT = Path(__file__).resolve().parents[1]


def _seed(session):
    admin = repo.create_user(
        session, "Admin 421", "admin421@example.com", "1",
        role="admin", roles=["admin"], must_change_password=False,
    )
    director = repo.create_user(
        session, "DD 421", "dd421@example.com", "1",
        role="director", roles=["director"], actor_id=admin.id, must_change_password=False,
    )
    reporter_a = repo.create_user(
        session, "Info A 421", "infoa421@example.com", "1",
        role="reporter", roles=["reporter"], actor_id=admin.id, must_change_password=False,
    )
    reporter_b = repo.create_user(
        session, "Info B 421", "infob421@example.com", "1",
        role="reporter", roles=["reporter"], actor_id=admin.id, must_change_password=False,
    )
    tracker = repo.create_user(
        session, "Tracker 421", "tracker421@example.com", "1",
        role="reporter", roles=["reporter"], actor_id=admin.id, must_change_password=False,
        can_track_players=True,
    )
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    competition = repo.create_competition(session, "Liga 421", actor_id=admin.id)
    own = repo.create_team(session, "C.D. Noname 421", is_own_team=True, actor_id=admin.id)
    a = repo.create_team(session, "Rival A 421", actor_id=admin.id)
    b = repo.create_team(session, "Rival B 421", actor_id=admin.id)
    c = repo.create_team(session, "Rival C 421", actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    return admin, director, reporter_a, reporter_b, tracker, season, competition, own, a, b, c


def test_roles_are_strict_and_tracking_is_independent():
    admin = {"role": "admin", "roles": ["admin"], "can_track_players": False}
    director = {"role": "director", "roles": ["director"], "can_track_players": False}
    reporter = {"role": "reporter", "roles": ["reporter"], "can_track_players": False}
    tracker = {"role": "reporter", "roles": ["reporter"], "can_track_players": True}
    hybrid = {"role": "admin", "roles": ["admin", "director", "reporter"], "can_track_players": True}

    assert can_admin(admin) and not can_report(admin) and not can_direct(admin)
    assert can_direct(director) and not can_report(director) and not can_admin(director)
    assert can_report(reporter) and not can_track_players(reporter)
    assert can_report(tracker) and can_track_players(tracker)
    assert can_admin(hybrid) and can_direct(hybrid) and can_report(hybrid) and can_track_players(hybrid)


def test_neutral_reading_requires_informador_even_for_director(session_factory):
    with session_factory.begin() as session:
        admin, director, reporter, _, _, season, comp, _, a, b, _ = _seed(session)
        match = repo.create_match(
            session, season_id=season.id, competition_id=comp.id, round_name="J3",
            match_date=date(2026, 9, 27), home_team_id=a.id, away_team_id=b.id,
            created_by=admin.id, status="published", kickoff_at=datetime(2026, 9, 27, 17, 0), schedule_status="confirmed",
        )
        with pytest.raises(PermissionError, match="Informador"):
            sporting_repo.save_neutral_opinion(
                session, match_id=match.id, user_id=director.id,
                home_team_rating=7.0, away_team_rating=6.0, summary="DD no puntúa por ser DD.", player_rows=[],
            )
        opinion = sporting_repo.save_neutral_opinion(
            session, match_id=match.id, user_id=reporter.id,
            home_team_rating=7.0, away_team_rating=6.0, summary="Lectura válida.", player_rows=[],
        )
        assert opinion.user_id == reporter.id


def test_postmatch_writing_requires_informador_not_admin_or_dd(session_factory):
    with session_factory.begin() as session:
        admin, director, reporter, _, _, season, comp, own, a, _, _ = _seed(session)
        match = repo.create_match(
            session, season_id=season.id, competition_id=comp.id, round_name="J1",
            match_date=date(2026, 9, 13), home_team_id=own.id, away_team_id=a.id,
            created_by=admin.id, status="published", kickoff_at=datetime(2026, 9, 13, 18, 0), schedule_status="confirmed",
        )
        with pytest.raises(PermissionError, match="Informador"):
            repo.get_or_create_report(session, match.id, admin.id)
        with pytest.raises(PermissionError, match="Informador"):
            repo.get_or_create_report(session, match.id, director.id)

        report = repo.get_or_create_report(session, match.id, reporter.id)
        with pytest.raises(PermissionError, match="Informador"):
            repo.save_report_summary(
                session, report.id, rival_level=None, opponent_overview="No debe guardar",
                own_team_note=None, key_takeaways=None, standout_player_id=None,
                actor_id=director.id, own_team_rating=8.0, rival_team_rating=6.0,
            )
        repo.save_report_summary(
            session, report.id, rival_level=None, opponent_overview="Sí puede guardar",
            own_team_note="Bien", key_takeaways="Control", standout_player_id=None,
            actor_id=reporter.id, own_team_rating=8.0, rival_team_rating=6.0,
        )
        assert report.own_team_rating == 8.0


def test_cross_match_intelligence_surfaces_repetition_weights_trend_and_disagreement(session_factory):
    with session_factory.begin() as session:
        admin, director, a_user, b_user, _, season, comp, _, team_a, team_b, team_c = _seed(session)
        player = repo.find_or_create_player(session, "Delantero repetido 421", primary_position="DC", actor_id=admin.id)
        repo.assign_player_to_roster(session, team_a.id, season.id, player.id, 9, actor_id=admin.id)

        first = repo.create_match(
            session, season_id=season.id, competition_id=comp.id, round_name="J2",
            match_date=date(2026, 9, 20), home_team_id=team_a.id, away_team_id=team_b.id,
            created_by=admin.id, status="published", kickoff_at=datetime(2026, 9, 20, 17, 0), schedule_status="confirmed",
        )
        second = repo.create_match(
            session, season_id=season.id, competition_id=comp.id, round_name="J3",
            match_date=date(2026, 9, 27), home_team_id=team_c.id, away_team_id=team_a.id,
            created_by=admin.id, status="published", kickoff_at=datetime(2026, 9, 27, 17, 0), schedule_status="confirmed",
        )

        sporting_repo.upsert_staff_weight(
            session, actor_id=director.id, user_id=a_user.id,
            own_match_weight=1.0, neutral_match_weight=1.5,
        )
        sporting_repo.upsert_staff_weight(
            session, actor_id=director.id, user_id=b_user.id,
            own_match_weight=1.0, neutral_match_weight=0.5,
        )

        sporting_repo.save_neutral_opinion(
            session, match_id=first.id, user_id=a_user.id,
            home_team_rating=8.0, away_team_rating=6.0, summary="A domina",
            player_rows=[{"player_id": player.id, "team_id": team_a.id, "rating": 8.0, "note": "Ataca espalda"}],
        )
        sporting_repo.save_neutral_opinion(
            session, match_id=first.id, user_id=b_user.id,
            home_team_rating=4.0, away_team_rating=7.0, summary="Lectura opuesta",
            player_rows=[{"player_id": player.id, "team_id": team_a.id, "rating": 4.0, "note": "Me genera dudas"}],
        )
        sporting_repo.save_neutral_opinion(
            session, match_id=second.id, user_id=a_user.id,
            home_team_rating=6.0, away_team_rating=9.0, summary="A vuelve a destacar",
            player_rows=[{"player_id": player.id, "team_id": team_a.id, "rating": 9.0, "note": "Repite impacto"}],
        )

        intel = sporting_repo.league_intelligence(session, season.id)
        row = next(item for item in intel["players"] if item["player"].id == player.id)
        assert row["match_count"] == 2
        assert row["mentions"] == 3
        assert row["staff_count"] == 2
        assert row["staff"] == ["Info A 421", "Info B 421"]
        assert row["weighted_rating"] == pytest.approx(27.5 / 3.5)
        assert row["trend"] is not None and row["trend"] > 0
        assert row["neutral_mentions"] == 3 and row["postmatch_mentions"] == 0
        assert intel["repeated_players"] >= 1

        disagreement = next(
            item for item in intel["disagreements"]
            if item["kind"] == "Jugador" and item["entity_id"] == player.id and item["match"].id == first.id
        )
        assert disagreement["consensus"] == "Discrepancia alta"
        assert disagreement["low"][1] == 4.0 and disagreement["high"][1] == 8.0
        assert intel["high_disagreements"] >= 1

        team_row = next(item for item in intel["teams"] if item["team"].id == team_a.id)
        assert team_row["match_count"] == 2
        assert team_row["opinions"] == 3


def test_home_deep_link_and_legacy_scout_ui_are_gone():
    home = (ROOT / "views" / "home.py").read_text(encoding="utf-8")
    workspaces = (ROOT / "repositories" / "workspaces.py").read_text(encoding="utf-8")

    assert 'st.session_state["dd_area_42"] = "Lectura deportiva"' in home
    assert 'st.session_state["dd_reading_area_421"] = "Jugadores señalados"' in home
    assert 'request_navigation("Dirección Deportiva")' in home

    for obsolete in ["scout.py", "director.py", "scouted.py", "model.py", "dashboard.py"]:
        assert not (ROOT / "views" / obsolete).exists()
    for token in ["ScoutMission", "ScoutMissionTarget", "my_missions", "mission_counts", "targets_by_mission"]:
        assert token not in workspaces
