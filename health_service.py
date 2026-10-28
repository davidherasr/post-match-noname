from __future__ import annotations

from datetime import date
from time import perf_counter
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from models.entities import PlayerEvaluation
from repositories import advanced_scouting as scout_repo
from repositories import league_intelligence as league_repo
from repositories import scouting as repo


def database_probe(session: Session) -> dict:
    """Read-only probe used from Administration after deployment."""
    started = perf_counter()
    session.execute(text("SELECT 1")).scalar_one()
    ping_ms = (perf_counter() - started) * 1000.0
    started = perf_counter()
    counts = {
        "users": repo.count_users(session),
        "matches": len(repo.list_matches(session, limit=500)),
        "reports": len(repo.list_reports(session, limit=500)),
    }
    catalog_ms = (perf_counter() - started) * 1000.0
    return {"ping_ms": round(ping_ms, 1), "catalog_ms": round(catalog_ms, 1), **counts}


def live_acceptance_rollback(session: Session, actor_id: int) -> dict:
    """Run the critical workflow against the *real configured DB* and roll it back.

    The SAVEPOINT is always rolled back, so the test leaves no temporary sports data.
    It validates the schema, constraints and repository workflow used in production.
    """
    repo.assert_role(session, actor_id, "admin")
    own = repo.get_own_team(session)
    season = repo.get_active_season(session)
    if not own or not season:
        raise ValueError("Configura primero No Name y una temporada activa.")

    token = uuid4().hex[:8]
    savepoint = session.begin_nested()
    started = perf_counter()
    try:
        competition = repo.create_competition(session, f"__ACCEPT_{token}", actor_id=actor_id)
        rival = repo.create_team(session, f"__RIVAL_{token}", actor_id=actor_id)
        player = repo.find_or_create_player(session, f"__PLAYER_{token}", primary_position="DC", actor_id=actor_id)
        # 4.2.2: Admin no longer inherits reporting rights. The live acceptance
        # test creates a disposable Informador inside the SAVEPOINT so the real
        # production permission model is exercised without leaving data behind.
        reporter = repo.create_user(
            session,
            f"__REPORTER_{token}",
            f"__reporter_{token}@acceptance.invalid",
            "1",
            role="reporter",
            roles=["reporter"],
            actor_id=actor_id,
            must_change_password=False,
        )
        match = repo.create_match(
            session, season_id=season.id, competition_id=competition.id, round_name=f"ACCEPT-{token}", match_date=date.today(),
            home_team_id=own.id, away_team_id=rival.id, created_by=actor_id, home_score=1, away_score=0,
            home_formation="4-4-2", away_formation="4-4-2", status="published",
        )
        rival_parts = repo.replace_participations(session, match.id, rival.id, [{
            "selected": True, "player_id": player.id, "shirt_number": 9, "starter": True,
            "position": "DC", "minute_in": 0, "minute_out": 90, "captain": False,
        }], actor_id)
        report = repo.get_or_create_report(session, match.id, reporter.id, actor_role="reporter")
        repo.bulk_upsert_evaluations_fast(session, report.id, [{
            "player_id": player.id, "team_id": rival.id, "participation_id": rival_parts[0].id,
            "expected_revision": None, "observation_status": "evaluated", "general_rating": 8.2,
            "short_note": "Prueba de aceptación con rollback", "standout": True, "pdf_include": True,
            "recommendation": None, "confidence": None,
        }], actor_id=reporter.id)
        fresh = repo.get_evaluation(session, report.id, player.id)
        if not fresh or float(fresh.general_rating or 0) != 8.2:
            raise AssertionError("La evaluación masiva no se ha recuperado correctamente.")
        submitted, _ = repo.submit_report(session, report.id, reporter.id)
        if submitted.status == "submitted":
            repo.approve_report(session, report.id, actor_id, "Aceptación automática con rollback")
        pool = league_repo.ranking_for_observed_position(session, "DC", season_id=season.id, min_observations=1)
        if not any(int(row["player_id"]) == player.id for row in pool):
            raise AssertionError("El ranking por posición observada no contiene el jugador de prueba.")
        profile = scout_repo.request_profile(session, player_id=player.id, actor_id=actor_id, model_position="DC")
        if not profile:
            raise AssertionError("No se ha podido abrir la ficha scout.")
        elapsed = (perf_counter() - started) * 1000.0
        result = {
            "ok": True, "elapsed_ms": round(elapsed, 1), "match": True, "bulk_upsert": True,
            "observed_position": True, "scout_workflow": True, "rollback": True,
        }
    finally:
        savepoint.rollback()
        # Expire any rolled-back ORM identity so later code cannot reuse it accidentally.
        session.expire_all()
    return result
