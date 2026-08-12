from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from models.entities import PlayerEvaluation, ScoutedPlayerProfile, ScoutReview
from repositories import advanced_scouting as scout_repo
from repositories import league_intelligence as intel
from repositories import scouting as repo
from core.postmatch_validation import validate_postmatch_draft


def _base(session):
    admin = repo.create_user(session, "Admin", "admin33@example.com", "ClaveAdmin123!", role="admin", must_change_password=False)
    reporter = repo.create_user(session, "Informador", "reporter33@example.com", "ClaveInfo123!", role="reporter", actor_id=admin.id, must_change_password=False)
    director = repo.create_user(session, "Director", "director33@example.com", "ClaveDirector123!", role="director", actor_id=admin.id, must_change_password=False)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Liga", actor_id=admin.id)
    own = repo.create_team(session, "No Name", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "Rival 33", actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    return admin, reporter, director, season, comp, own, rival


def _approved(session, *, admin, reporter, season, comp, own, rival, player, rating, day, position="MC", standout=False):
    match = repo.create_match(
        session, season_id=season.id, competition_id=comp.id, round_name=f"J{day}",
        match_date=date(2026, 8, day), home_team_id=own.id, away_team_id=rival.id,
        created_by=admin.id, status="published",
    )
    part = repo.replace_participations(session, match.id, rival.id, [{
        "selected": True, "player_id": player.id, "shirt_number": 8, "starter": True,
        "position": position, "minute_in": 0, "minute_out": 90, "captain": False,
    }], admin.id)[0]
    report = repo.get_or_create_report(session, match.id, reporter.id)
    repo.bulk_upsert_evaluations_fast(session, report.id, [{
        "player_id": player.id, "team_id": rival.id, "participation_id": part.id,
        "observation_status": "evaluated", "general_rating": rating, "short_note": f"Nota {rating}",
        "standout": standout, "pdf_include": True,
    }], reporter.id)
    repo.submit_report(session, report.id, reporter.id)
    repo.approve_report(session, report.id, admin.id)
    return report


def test_true_bulk_upsert_updates_without_duplicates(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, season, comp, own, rival = _base(session)
        match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1", match_date=date(2026, 8, 1), home_team_id=own.id, away_team_id=rival.id, created_by=admin.id, status="published")
        p1 = repo.find_or_create_player(session, "Uno", primary_position="MC", actor_id=admin.id)
        p2 = repo.find_or_create_player(session, "Dos", primary_position="DC", actor_id=admin.id)
        parts = repo.replace_participations(session, match.id, rival.id, [
            {"selected": True, "player_id": p1.id, "shirt_number": 8, "starter": True, "position": "MC", "minute_in": 0, "minute_out": 90, "captain": False},
            {"selected": True, "player_id": p2.id, "shirt_number": 9, "starter": True, "position": "DC", "minute_in": 0, "minute_out": 90, "captain": False},
        ], admin.id)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        rows = [
            {"player_id": p1.id, "team_id": rival.id, "participation_id": parts[0].id, "observation_status": "evaluated", "general_rating": 7.0, "short_note": None, "standout": False, "pdf_include": True},
            {"player_id": p2.id, "team_id": rival.id, "participation_id": parts[1].id, "observation_status": "evaluated", "general_rating": 8.0, "short_note": None, "standout": True, "pdf_include": True},
        ]
        assert repo.bulk_upsert_evaluations_fast(session, report.id, rows, reporter.id) == 2
        rows[0]["general_rating"] = 7.8
        rows[1]["general_rating"] = 8.4
        assert repo.bulk_upsert_evaluations_fast(session, report.id, rows, reporter.id) == 2
        count = session.scalar(select(func.count(PlayerEvaluation.id)).where(PlayerEvaluation.report_id == report.id))
        assert count == 2
        stored = {e.player_id: e for e in repo.list_evaluations(session, report.id)}
        assert stored[p1.id].general_rating == 7.8
        assert stored[p2.id].general_rating == 8.4


def test_observed_position_ranking_and_confidence(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, season, comp, own, rival = _base(session)
        player = repo.find_or_create_player(session, "Polivalente", primary_position="DFC", actor_id=admin.id)
        _approved(session, admin=admin, reporter=reporter, season=season, comp=comp, own=own, rival=rival, player=player, rating=7.6, day=1, position="MCD")
        _approved(session, admin=admin, reporter=reporter, season=season, comp=comp, own=own, rival=rival, player=player, rating=8.2, day=2, position="MCD", standout=True)
        rows = intel.ranking_for_observed_position(session, "MCD", season_id=season.id, min_observations=2)
        assert len(rows) == 1
        assert rows[0]["player_id"] == player.id
        assert rows[0]["observed_position"] == "MCD"
        counts = intel.observed_position_counts(session, player.id, season_id=season.id)
        assert counts[0]["position"] == "MCD"
        conf = intel.confidence_score(4, 3, 0.2, date.today())
        assert conf["score"] >= 75
        assert conf["label"] == "Alta"


def test_advanced_scout_request_review_and_approval(session_factory):
    with session_factory.begin() as session:
        admin, reporter, director, season, comp, own, rival = _base(session)
        player = repo.find_or_create_player(session, "Jugador Scout", primary_position="DC", actor_id=admin.id)
        _approved(session, admin=admin, reporter=reporter, season=season, comp=comp, own=own, rival=rival, player=player, rating=8.3, day=1, position="DC", standout=True)
        profile = scout_repo.request_profile(session, player_id=player.id, actor_id=director.id, assigned_to=reporter.id, model_position="DC", model_role="Delantero referencia")
        assert profile.status == "requested"
        review = scout_repo.get_or_create_review(session, profile.id, reporter.id)
        scout_repo.save_review(
            session, review.id, reporter.id,
            observed_position="DC", technical_rating=7.5, tactical_rating=8.0, physical_rating=8.5, mental_rating=8.0,
            current_level=7.5, potential_score=8.0, model_fit_score=8.4,
            attributes={"Finalización": 8.0, "Juego de espaldas": 8.5}, strengths="Fija centrales", weaknesses="Giro lento",
            summary="Perfil que encaja como referencia.", recommendation="Seguimiento", submit=True,
        )
        stored_review = session.get(ScoutReview, review.id)
        assert stored_review.status == "submitted"
        profile = scout_repo.update_profile(session, profile.id, director.id, fit_score=8.4, current_level=7.5, potential_score=8.0, final_decision="Seguimiento", director_summary="Encaja en nuestro modelo", approve=True)
        assert profile.status == "scouted"
        assert profile.approved_by == director.id
        bundle = scout_repo.profile_bundle(session, player.id)
        assert bundle is not None
        assert bundle["profile"].model_role == "Delantero referencia"
        assert len(bundle["reviews"]) == 1


def test_robust_trend_requires_repeated_sample(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, season, comp, own, rival = _base(session)
        player = repo.find_or_create_player(session, "En subida", primary_position="EI", actor_id=admin.id)
        for day, rating in [(1, 6.5), (2, 6.9), (3, 7.8), (4, 8.1)]:
            _approved(session, admin=admin, reporter=reporter, season=season, comp=comp, own=own, rival=rival, player=player, rating=rating, day=day, position="EI", standout=rating >= 8)
        trends = intel.robust_trends(session, season_id=season.id, min_observations=3)
        item = next(t for t in trends if t["player_id"] == player.id)
        assert item["recent_average"] > item["early_average"]
        assert item["delta"] > 1.0


def test_publish_validation_blocks_incomplete_or_duplicate_lineups():
    invalid = {
        "own_xi": [{"player_id": i} for i in range(1, 11)],
        "rival_xi": [{"name": f"Rival {i}"} for i in range(1, 11)] + [{"name": "Rival 1"}],
        "own_subs": [], "rival_subs": [], "reporter_ids": [],
    }
    errors, warnings = validate_postmatch_draft(invalid)
    assert any("11 jugadores" in e for e in errors)
    assert any("repetido" in e for e in errors)
    assert warnings
