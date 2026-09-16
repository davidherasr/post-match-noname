from __future__ import annotations

from datetime import date

from repositories import scouting as repo


def _seed(session):
    admin = repo.create_user(session, "Admin", "dd-admin@example.com", "ClaveAdmin123!", role="admin", must_change_password=False)
    reporter = repo.create_user(session, "Info", "dd-info@example.com", "ClaveInfo123!", role="reporter", actor_id=admin.id, must_change_password=False)
    director = repo.create_user(session, "Dire", "dd-dire@example.com", "ClaveDire123!", role="director", actor_id=admin.id, must_change_password=False)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    comp = repo.create_competition(session, "Liga", actor_id=admin.id)
    own = repo.create_team(session, "No Name", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "Rival A", actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    return admin, reporter, director, season, comp, own, rival


def _approved_observation(session, admin, reporter, season, comp, own, rival, player_name="Rival Uno", rating=8.2, match_day=1):
    match = repo.create_match(
        session, season_id=season.id, competition_id=comp.id, round_name=f"J{match_day}",
        match_date=date(2026, 8, match_day), home_team_id=own.id, away_team_id=rival.id,
        created_by=admin.id, status="published",
    )
    player = repo.find_or_create_player(session, player_name, primary_position="DC", actor_id=admin.id)
    part = repo.replace_participations(session, match.id, rival.id, [{
        "selected": True, "player_id": player.id, "shirt_number": 9, "starter": True,
        "position": "DC", "minute_in": 0, "minute_out": 90, "captain": False,
    }], admin.id)[0]
    report = repo.get_or_create_report(session, match.id, reporter.id)
    repo.bulk_upsert_evaluations_fast(session, report.id, [{
        "player_id": player.id, "team_id": rival.id, "participation_id": part.id,
        "observation_status": "evaluated", "general_rating": rating, "short_note": "Buen partido",
        "standout": rating >= 8, "pdf_include": True,
    }], reporter.id)
    repo.submit_report(session, report.id, reporter.id)
    repo.approve_report(session, report.id, admin.id)
    return match, player, report


def test_postmatch_cloud_draft_roundtrip(session_factory):
    with session_factory.begin() as session:
        admin, _, _, season, _, _, _ = _seed(session)
        payload = {"round_name": "J1", "own_formation": "4-4-2", "rival_xi": [{"name": "Bote"}]}
        item = repo.save_postmatch_draft(session, actor_id=admin.id, payload=payload, season_id=season.id, title="J1 · Rival")
        loaded = repo.load_postmatch_draft(session, item.id, admin.id)
        assert loaded["own_formation"] == "4-4-2"
        assert loaded["rival_xi"][0]["name"] == "Bote"
        repo.close_postmatch_draft(session, item.id, admin.id)
        assert repo.list_postmatch_drafts(session, admin.id) == []


def test_fast_named_lineup_creates_players_and_roster_in_batch(session_factory):
    with session_factory.begin() as session:
        admin, _, _, season, comp, own, rival = _seed(session)
        match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1", match_date=date(2026,8,1), home_team_id=own.id, away_team_id=rival.id, created_by=admin.id)
        rows = [
            {"name": "Bote", "shirt_number": 1, "position": "POR", "starter": True, "minute_in": 0, "minute_out": 90},
            {"name": "Checkmate", "shirt_number": 4, "position": "DFC", "starter": True, "minute_in": 0, "minute_out": 65},
            {"name": "Cambio", "shirt_number": 14, "position": "DFC", "starter": False, "minute_in": 65, "minute_out": 90},
        ]
        parts = repo.save_named_lineup_fast(session, match_id=match.id, team_id=rival.id, season_id=season.id, rows=rows, actor_id=admin.id)
        assert len(parts) == 3
        roster = repo.get_roster(session, rival.id, season.id)
        assert len(roster) == 3
        assert {p.player.full_name for p in parts} == {"Bote", "Checkmate", "Cambio"}


def test_sql_player_rankings_and_league_panorama(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, season, comp, own, rival = _seed(session)
        _approved_observation(session, admin, reporter, season, comp, own, rival, rating=8.0, match_day=1)
        _approved_observation(session, admin, reporter, season, comp, own, rival, rating=8.6, match_day=2)
        rows = repo.player_rankings(session, min_observations=2, season_id=season.id)
        assert len(rows) == 1
        assert rows[0]["observations"] == 2
        assert round(rows[0]["avg_general"], 1) == 8.3
        panorama = repo.league_panorama(session, season_id=season.id)
        assert panorama["players_observed"] == 1
        assert panorama["players_repeated"] == 1
        assert panorama["teams_observed"] == 1


def test_director_profile_and_custom_list(session_factory):
    with session_factory.begin() as session:
        admin, reporter, director, season, comp, own, rival = _seed(session)
        _, player, _ = _approved_observation(session, admin, reporter, season, comp, own, rival)
        profile = repo.upsert_league_profile(session, player.id, director.id, decision_status="Prioritario", priority=1, director_note="Volver a ver")
        assert profile.decision_status == "Prioritario"
        item = repo.create_scouting_list(session, director.id, name="Delanteros", list_type="shortlist", season_id=season.id)
        repo.add_scouting_list_item(session, item.id, player.id, director.id, position="DC")
        contents = repo.list_scouting_list_items(session, item.id)
        assert len(contents) == 1
        assert contents[0].player_id == player.id


def test_review_queue_batches_submitted_reports(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, season, comp, own, rival = _seed(session)
        match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1", match_date=date(2026,8,1), home_team_id=own.id, away_team_id=rival.id, created_by=admin.id, status="published")
        player = repo.find_or_create_player(session, "Rival Review", primary_position="MC", actor_id=admin.id)
        part = repo.replace_participations(session, match.id, rival.id, [{"selected":True,"player_id":player.id,"shirt_number":8,"starter":True,"position":"MC","minute_in":0,"minute_out":90,"captain":False}], admin.id)[0]
        report = repo.get_or_create_report(session, match.id, reporter.id)
        repo.bulk_upsert_evaluations_fast(session, report.id, [{"player_id":player.id,"team_id":rival.id,"participation_id":part.id,"observation_status":"evaluated","general_rating":7.7,"short_note":None,"standout":False,"pdf_include":True}], reporter.id)
        repo.submit_report(session, report.id, reporter.id)
        queue = repo.load_review_queue(session)
        # Newly incorporated reports bypass the old mandatory-review queue.
        assert queue == []
        assert report.status == "incorporated"
