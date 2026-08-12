from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select

from models.entities import Player, TeamRoster
from repositories import league_intelligence as league_repo
from repositories import scouting as repo
from services.health_service import live_acceptance_rollback


def _seed_minimum(session):
    admin = repo.create_user(session, "Admin", "admin34@example.com", "ValidPass123!", role="admin", must_change_password=False)
    season = repo.create_season(session, "2026/27", date(2026,7,1), date(2027,6,30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    own = repo.create_team(session, "No Name", is_own_team=True, actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    return admin, season, own


def test_confidence_is_explainable_and_recency_matters():
    fresh = league_repo.confidence_score(4, 3, .4, date.today())
    old = league_repo.confidence_score(4, 3, .4, date.today() - timedelta(days=300))
    assert fresh["score"] > old["score"]
    assert set(fresh["components"]) == {"Muestra", "Informadores", "Consenso", "Recencia"}
    assert fresh["consensus"] in {"Muy alto", "Alto", "Medio", "Bajo", "Muy bajo"}


def test_rival_homonyms_are_reported_and_can_be_resolved(session_factory):
    with session_factory.begin() as session:
        admin, season, own = _seed_minimum(session)
        rival_a = repo.create_team(session, "Rival A", actor_id=admin.id)
        rival_b = repo.create_team(session, "Rival B", actor_id=admin.id)
        target = repo.create_team(session, "Rival objetivo", actor_id=admin.id)
        p1 = repo.find_or_create_player(session, "Juan García", date_of_birth=date(2000,1,1), primary_position="MC", actor_id=admin.id)
        p2 = repo.find_or_create_player(session, "Juan Garcia", date_of_birth=date(2001,2,2), primary_position="MC", actor_id=admin.id)
        repo.assign_player_to_roster(session, rival_a.id, season.id, p1.id, 8, admin.id)
        repo.assign_player_to_roster(session, rival_b.id, season.id, p2.id, 10, admin.id)
        conflicts = repo.lineup_identity_conflicts(session, [{"name":"Juan García","position":"MC"}], team_id=target.id, season_id=season.id)
        assert len(conflicts) == 1
        assert {c["id"] for c in conflicts[0]["candidates"]} == {p1.id, p2.id}


def test_team_context_avoids_false_homonym_conflict(session_factory):
    with session_factory.begin() as session:
        admin, season, own = _seed_minimum(session)
        target = repo.create_team(session, "Rival contexto", actor_id=admin.id)
        other = repo.create_team(session, "Otro rival", actor_id=admin.id)
        p1 = repo.find_or_create_player(session, "Pedro López", date_of_birth=date(2000,1,1), actor_id=admin.id)
        p2 = repo.find_or_create_player(session, "Pedro Lopez", date_of_birth=date(2001,1,1), actor_id=admin.id)
        repo.assign_player_to_roster(session, target.id, season.id, p1.id, 4, admin.id)
        repo.assign_player_to_roster(session, other.id, season.id, p2.id, 5, admin.id)
        assert repo.lineup_identity_conflicts(session, [{"name":"Pedro López"}], team_id=target.id, season_id=season.id) == []


def test_live_acceptance_rolls_back_temporary_data(session_factory):
    with session_factory() as session:
        with session.begin():
            admin, season, own = _seed_minimum(session)
        before_players = session.scalar(select(func.count(Player.id)))
        result = live_acceptance_rollback(session, admin.id)
        after_players = session.scalar(select(func.count(Player.id)))
        assert result["ok"] is True and result["rollback"] is True
        assert before_players == after_players
