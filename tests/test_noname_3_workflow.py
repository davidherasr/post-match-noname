from __future__ import annotations

from datetime import date

from sqlalchemy import select

from models.entities import Player, TeamRoster
from repositories import scouting as repo


def _base(session):
    admin = repo.create_user(session, "Admin", "admin3@example.com", "ClaveAdmin123!", role="admin", must_change_password=False)
    reporter = repo.create_user(session, "Informador", "reporter3@example.com", "ClaveInfo123!", role="reporter", actor_id=admin.id, must_change_password=False)
    director = repo.create_user(session, "Director", "director3@example.com", "ClaveDirector123!", role="director", actor_id=admin.id, must_change_password=False)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Liga", actor_id=admin.id)
    own = repo.create_team(session, "No Name", "NO NAME", "España", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "Rival CF", actor_id=admin.id)
    return admin, reporter, director, season, comp, own, rival


def test_rival_lineup_can_create_players_without_prebuilt_roster(session_factory):
    with session_factory.begin() as session:
        admin, _, _, season, comp, own, rival = _base(session)
        match = repo.create_match(
            session,
            season_id=season.id,
            competition_id=comp.id,
            round_name="J1",
            match_date=date(2026, 8, 9),
            home_team_id=own.id,
            away_team_id=rival.id,
            created_by=admin.id,
            status="draft",
        )
        assert repo.get_roster(session, rival.id, season.id) == []
        parts = repo.save_named_lineup(
            session,
            match_id=match.id,
            team_id=rival.id,
            season_id=season.id,
            actor_id=admin.id,
            rows=[
                {"name": "Bote", "position": "POR", "shirt_number": 1, "starter": True, "minute_in": 0, "minute_out": 90},
                {"name": "Checkmate", "position": "DFC", "shirt_number": 4, "starter": True, "minute_in": 0, "minute_out": 90},
            ],
        )
        assert len(parts) == 2
        assert {p.player.full_name for p in parts} == {"Bote", "Checkmate"}
        assert len(repo.get_roster(session, rival.id, season.id)) == 2
        assert session.scalar(select(Player).where(Player.full_name == "Bote")) is not None


def test_copy_last_own_lineup_into_new_match(session_factory):
    with session_factory.begin() as session:
        admin, _, _, season, comp, own, rival = _base(session)
        player = repo.find_or_create_player(session, "Jugador No Name", primary_position="MC", actor_id=admin.id)
        repo.assign_player_to_roster(session, own.id, season.id, player.id, 8, admin.id)
        first = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1", match_date=date(2026, 8, 1), home_team_id=own.id, away_team_id=rival.id, created_by=admin.id, status="published")
        repo.replace_participations(session, first.id, own.id, [{"selected": True, "player_id": player.id, "shirt_number": 8, "starter": True, "position": "MC", "minute_in": 0, "minute_out": 72, "captain": True}], admin.id)
        second = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J2", match_date=date(2026, 8, 8), home_team_id=rival.id, away_team_id=own.id, created_by=admin.id, status="draft")
        copied = repo.copy_lineup_from_match(session, source_match_id=first.id, target_match_id=second.id, team_id=own.id, actor_id=admin.id)
        assert len(copied) == 1
        assert copied[0].player_id == player.id
        assert copied[0].starter is True
        assert copied[0].minute_out == 72
        assert copied[0].captain is True


def test_own_history_and_rival_history_are_separate(session_factory):
    with session_factory.begin() as session:
        admin, reporter, director, season, comp, own, rival = _base(session)
        own_player = repo.find_or_create_player(session, "Jugador Propio", primary_position="DC", actor_id=admin.id)
        rival_player = repo.find_or_create_player(session, "Jugador Rival", primary_position="MC", actor_id=admin.id)
        repo.assign_player_to_roster(session, own.id, season.id, own_player.id, 9, admin.id)
        match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1", match_date=date(2026, 8, 9), home_team_id=own.id, away_team_id=rival.id, created_by=admin.id, status="published")
        repo.replace_participations(session, match.id, own.id, [{"selected": True, "player_id": own_player.id, "shirt_number": 9, "starter": True, "position": "DC", "minute_in": 0, "minute_out": 90, "captain": False}], admin.id)
        rival_parts = repo.save_named_lineup(session, match_id=match.id, team_id=rival.id, season_id=season.id, actor_id=admin.id, rows=[{"name": rival_player.full_name, "position": "MC", "shirt_number": 8, "starter": True, "minute_in": 0, "minute_out": 90}])
        repo.assign_reporters(session, match.id, [reporter.id], admin.id)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        own_part = repo.get_participations(session, match.id, own.id)[0]
        repo.upsert_evaluation(session, report.id, own_player.id, own.id, own_part.id, actor_id=reporter.id, observation_status="evaluated", general_rating=7.4, short_note="Buen partido.")
        repo.upsert_evaluation(session, report.id, rival_player.id, rival.id, rival_parts[0].id, actor_id=reporter.id, observation_status="evaluated", general_rating=8.2, short_note="Destacado.", standout=True)
        repo.submit_report(session, report.id, reporter.id)
        repo.approve_report(session, report.id, director.id)

        own_rank = repo.own_player_rankings(session)
        rival_rank = repo.player_rankings(session)
        assert [x["player_id"] for x in own_rank] == [own_player.id]
        assert [x["player_id"] for x in rival_rank] == [rival_player.id]
        assert len(repo.player_history_by_scope(session, own_player.id, scope="own")) == 1
        assert repo.player_history_by_scope(session, own_player.id, scope="rival") == []
        assert len(repo.player_history_by_scope(session, rival_player.id, scope="rival")) == 1
        assert repo.recent_rival_highlights(session, minimum_rating=8.0)[0]["player"].id == rival_player.id


def test_own_team_and_active_season_helpers_do_not_seed_sporting_data(session_factory):
    with session_factory.begin() as session:
        assert repo.get_own_team(session) is None
        assert repo.get_active_season(session) is None
        assert session.scalar(select(Player).limit(1)) is None
        assert session.scalar(select(TeamRoster).limit(1)) is None
