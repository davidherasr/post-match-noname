from __future__ import annotations

from datetime import date, datetime

from core.calendar_import import parse_calendar_text
from models.entities import ScoutObservation, UserRole
from repositories import calendar as calendar_repo
from repositories import planning as planning_repo
from repositories import scouting as repo


def _base(session):
    admin = repo.create_user(session, "Admin", "admin35@example.com", "ValidPass123!", role="admin", roles=["admin", "director"], must_change_password=False, can_track_players=True)
    scout = repo.create_user(session, "Seguimiento", "scout35@example.com", "ValidPass123!", role="reporter", roles=["reporter"], actor_id=admin.id, must_change_password=False, can_track_players=True)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Liga", actor_id=admin.id)
    own = repo.create_team(session, "No Name", is_own_team=True, actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    return admin, scout, season, comp, own


def test_full_league_calendar_import_and_schedule_confirmation(session_factory):
    with session_factory.begin() as session:
        admin, _, season, comp, own = _base(session)
        rows, errors = parse_calendar_text(
            "1;16/08/2026;No Name;La Bañeza\n"
            "1;16/08/2026;Laguna;Benavente\n"
            "2;22/08/2026;18:30;La Bañeza;Laguna",
            default_year=2026,
        )
        assert not errors
        result = calendar_repo.import_fixtures(session, season_id=season.id, competition_id=comp.id, rows=rows, actor_id=admin.id)
        assert result["created"] == 3
        all_matches = calendar_repo.list_calendar(session, season_id=season.id)
        assert len(all_matches) == 3
        neutral = next(m for m in all_matches if {m.home_team.name, m.away_team.name} == {"Laguna", "Benavente"})
        assert neutral.fixture_type == "league"
        own_match = next(m for m in all_matches if own.id in {m.home_team_id, m.away_team_id})
        assert own_match.schedule_status == "provisional"
        assert own_match.match_date == date(2026, 8, 16)
        assert own_match.window_start is None
        assert own_match.window_end is None
        calendar_repo.update_schedule(
            session, own_match.id, admin.id, definitive_date=date(2026, 8, 16),
            kickoff_at=datetime(2026, 8, 16, 12, 0), schedule_status="confirmed", venue="Campo",
        )
        assert own_match.kickoff_at.hour == 12
        assert calendar_repo.schedule_label(own_match).endswith("12:00")


def test_multi_role_profile_and_scout_mission_with_repeated_observations(session_factory):
    with session_factory.begin() as session:
        admin, scout, season, comp, _ = _base(session)
        assert not repo.user_has_role(session, scout.id, "scout")
        assert repo.user_has_role(session, scout.id, "reporter")
        assert scout.can_track_players is True
        assert {r.role for r in session.query(UserRole).filter(UserRole.user_id == scout.id)} == {"reporter"}

        a = repo.create_team(session, "La Bañeza", actor_id=admin.id)
        b = repo.create_team(session, "Laguna", actor_id=admin.id)
        match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J5", match_date=date(2026, 9, 17), home_team_id=a.id, away_team_id=b.id, created_by=admin.id, status="scheduled", kickoff_at=datetime(2026, 9, 17, 18, 0), schedule_status="confirmed")
        player = repo.find_or_create_player(session, "Objetivo Scout", primary_position="DC", actor_id=admin.id)
        repo.assign_player_to_roster(session, a.id, season.id, player.id, 9, actor_id=admin.id)
        mission = planning_repo.create_mission(
            session, match_id=match.id, mission_type="player", title="Observar delantero", assigned_to=scout.id,
            requested_by=admin.id, target_team_id=a.id, player_ids=[player.id], purpose="Segunda observación", focus=["Profundidad", "Presión"], priority=1,
        )
        assert planning_repo.mission_targets(session, mission.id)[0].player_id == player.id
        first = planning_repo.create_observation(session, player_id=player.id, reviewer_id=scout.id, mission_id=mission.id, source_type="specific")
        planning_repo.save_observation(session, first.id, scout.id, observed_position="DC", general_rating=8.0, current_level=7.5, model_fit_score=8.0, summary="Primera específica", recommendation="Seguimiento", submit=True)
        second = planning_repo.create_observation(session, player_id=player.id, reviewer_id=scout.id, match_id=match.id, source_type="spontaneous")
        planning_repo.save_observation(session, second.id, scout.id, observed_position="DC", general_rating=8.5, current_level=8.0, model_fit_score=8.5, summary="Segunda específica", recommendation="Prioritario", submit=True)
        rows = planning_repo.list_observations(session, player_id=player.id)
        assert len(rows) == 2
        assert session.query(ScoutObservation).filter(ScoutObservation.profile_id == first.profile_id).count() == 2
        evidence = planning_repo.scouting_evidence_summary(session, player.id, season_id=season.id)
        assert evidence["specific_observations"] == 2
        assert evidence["specific_strength"] in {"Media", "Alta"}


def test_model_roles_needs_shadow_squad_and_opportunity(session_factory):
    with session_factory.begin() as session:
        admin, scout, season, comp, _ = _base(session)
        rival = repo.create_team(session, "Rival Modelo", actor_id=admin.id)
        other = repo.create_team(session, "Otro", actor_id=admin.id)
        player = repo.find_or_create_player(session, "MCD Modelo", primary_position="MCD", actor_id=admin.id)
        repo.assign_player_to_roster(session, rival.id, season.id, player.id, 6, actor_id=admin.id)
        role = planning_repo.create_model_role(session, admin.id, name="Base", position="MCD", description="Primer pase y defensa de espacios")
        c1 = planning_repo.add_model_criterion(session, admin.id, role.id, name="Salida limpia", category="Táctico", weight=5)
        c2 = planning_repo.add_model_criterion(session, admin.id, role.id, name="Defensa espacios", category="Táctico", weight=4)
        fit = planning_repo.weighted_model_fit([c1, c2], {c1.id: 8.0, c2.id: 7.0})
        assert 7.4 < fit < 7.7
        planning_repo.upsert_squad_need(session, admin.id, season_id=season.id, model_role_id=role.id, need_level="Alta", status="Abierta", note="Prioridad")
        planning_repo.ensure_scout_profile(session, player.id, admin.id)
        decision = planning_repo.upsert_season_decision(session, admin.id, season_id=season.id, player_id=player.id, status="Seguimiento", priority=1, model_role_id=role.id, fit_score=8.0)
        future = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J10", match_date=date.today().fromordinal(date.today().toordinal()+20), home_team_id=rival.id, away_team_id=other.id, created_by=admin.id, status="scheduled")
        board = planning_repo.shadow_squad(session, season.id)
        block = next(x for x in board if x["role"].id == role.id)
        assert block["need"].need_level == "Alta"
        assert block["candidates"][0].player_id == player.id
        opportunities = planning_repo.scouting_opportunities(session, season_id=season.id)
        assert opportunities
        assert opportunities[0]["match"].id == future.id
        assert opportunities[0]["decision"].id == decision.id


def test_player_ranking_search_is_server_side(session_factory):
    with session_factory.begin() as session:
        admin, _, season, _, _ = _base(session)
        # This test verifies the SQL search argument is accepted without requiring client-side filtering.
        # No approved reports means an empty result, but it must execute safely with accented/partial search.
        assert repo.player_rankings(session, season_id=season.id, search="García", limit=25, offset=0) == []


def test_scout_can_save_quick_sweep_for_multiple_players(session_factory):
    with session_factory.begin() as session:
        admin, scout, season, comp, _ = _base(session)
        home = repo.create_team(session, "Equipo Scan A", actor_id=admin.id)
        away = repo.create_team(session, "Equipo Scan B", actor_id=admin.id)
        match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J Scan", match_date=date(2026, 10, 4), home_team_id=home.id, away_team_id=away.id, created_by=admin.id, status="scheduled", kickoff_at=datetime(2026, 10, 4, 17, 0), schedule_status="confirmed")
        p1 = repo.find_or_create_player(session, "Scan Uno", primary_position="MC", actor_id=admin.id)
        p2 = repo.find_or_create_player(session, "Scan Dos", primary_position="DC", actor_id=admin.id)
        count = planning_repo.save_quick_match_observations(session, match_id=match.id, reviewer_id=scout.id, rows=[
            {"player_id": p1.id, "general_rating": 7.5, "observed_position": "MC", "summary": "Buen ritmo"},
            {"player_id": p2.id, "general_rating": 8.0, "observed_position": "DC", "summary": "Ataca profundidad"},
        ])
        assert count == 2
        rows = planning_repo.list_observations(session, reviewer_id=scout.id)
        assert {o.source_type for o in rows} == {"match_scan"}
        assert sorted(o.general_rating for o in rows) == [7.5, 8.0]


def test_calendar_import_uses_single_provisional_reference_date():
    rows, errors = parse_calendar_text(
        '8;01/11/2026;C.D. Ribert;La Bañeza F.C.',
        default_year=2026,
    )
    assert not errors
    assert len(rows) == 1
    assert rows[0]["match_date"] == date(2026, 11, 1)
    assert rows[0]["window_start"] is None
    assert rows[0]["window_end"] is None
    assert rows[0]["schedule_status"] == "provisional"
    assert rows[0]["kickoff_at"] is None


def test_calendar_import_rejects_ranges_with_clear_guidance():
    rows, errors = parse_calendar_text(
        '1;12/09/2026-13/09/2026;Ciudad Rodrigo C.F.;C.D.F. Mojados',
        default_year=2026,
    )
    assert rows == []
    assert errors
    assert "no uses rangos" in errors[0].lower()


def test_calendar_import_can_confirm_exact_kickoff_directly():
    rows, errors = parse_calendar_text(
        '1;12/09/2026;18:30;Equipo A;Equipo B',
        default_year=2026,
    )
    assert not errors
    assert rows[0]["schedule_status"] == "confirmed"
    assert rows[0]["kickoff_at"] == datetime(2026, 9, 12, 18, 30)
