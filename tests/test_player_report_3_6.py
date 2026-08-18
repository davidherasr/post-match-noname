from __future__ import annotations

from datetime import date, datetime

from repositories import planning as planning_repo
from repositories import player_report as player_report_repo
from repositories import scouting as repo
from reports.player_report_pdf import generate_player_executive_pdf, generate_player_360_pdf


def _seed(session):
    admin = repo.create_user(session, "Admin", "admin36@example.com", "ValidPass123!", role="admin", roles=["admin", "director", "scout"], must_change_password=False)
    reporter = repo.create_user(session, "Info", "info36@example.com", "ValidPass123!", role="reporter", actor_id=admin.id, must_change_password=False)
    scout = repo.create_user(session, "Scout", "scout36@example.com", "ValidPass123!", role="scout", roles=["scout"], actor_id=admin.id, must_change_password=False)
    season = repo.create_season(session, "2026/27", date(2026,7,1), date(2027,6,30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Liga", actor_id=admin.id)
    own = repo.create_team(session, "No Name", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "La Bañeza", actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    return admin, reporter, scout, season, comp, own, rival


def _approved_postmatch(session, admin, reporter, season, comp, own, rival, player, rating=8.2):
    match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1", match_date=date(2026,8,16), home_team_id=own.id, away_team_id=rival.id, created_by=admin.id, status="published", kickoff_at=datetime(2026,8,16,17,0), schedule_status="confirmed")
    part = repo.replace_participations(session, match.id, rival.id, [{"selected":True,"player_id":player.id,"shirt_number":9,"starter":True,"position":"DC","minute_in":0,"minute_out":90,"captain":False}], admin.id)[0]
    report = repo.get_or_create_report(session, match.id, reporter.id)
    repo.bulk_upsert_evaluations_fast(session, report.id, [{"player_id":player.id,"team_id":rival.id,"participation_id":part.id,"observation_status":"evaluated","general_rating":rating,"short_note":"Ataca bien el espacio","standout":True,"pdf_include":True}], reporter.id)
    repo.submit_report(session, report.id, reporter.id)
    repo.approve_report(session, report.id, admin.id)
    return match


def test_player_report_360_uses_only_real_model_scores_and_internal_comparison(session_factory):
    with session_factory.begin() as session:
        admin, reporter, scout, season, comp, own, rival = _seed(session)
        player = repo.find_or_create_player(session, "Pedro Objetivo", primary_position="DC", actor_id=admin.id)
        repo.assign_player_to_roster(session, rival.id, season.id, player.id, 9, actor_id=admin.id)
        match = _approved_postmatch(session, admin, reporter, season, comp, own, rival, player)
        role = planning_repo.create_model_role(session, admin.id, name="Profundidad", position="DC", description="Atacar espalda")
        c1 = planning_repo.add_model_criterion(session, admin.id, role.id, name="Desmarque ruptura", category="Táctico", weight=5)
        c2 = planning_repo.add_model_criterion(session, admin.id, role.id, name="Ataque área", category="Táctico", weight=4)
        c3 = planning_repo.add_model_criterion(session, admin.id, role.id, name="Presión", category="Mental", weight=3)
        obs = planning_repo.create_observation(session, player_id=player.id, reviewer_id=scout.id, match_id=match.id, source_type="specific")
        planning_repo.save_observation(session, obs.id, scout.id, observed_position="DC", general_rating=8.5, tactical_rating=8.0, physical_rating=7.5, mental_rating=8.0, current_level=8.0, potential_score=8.5, model_fit_score=8.4, attributes={"model_role_id":role.id, str(c1.id):9.0, str(c2.id):8.0, str(c3.id):8.0}, strengths="Profundidad\nMovilidad", weaknesses="Juego de espaldas", summary="Delantero vertical", recommendation="Seguimiento", submit=True)
        planning_repo.upsert_season_decision(session, admin.id, season_id=season.id, player_id=player.id, status="Seguimiento", priority=1, model_role_id=role.id, director_note="Encaja en el rol", fit_score=8.4)

        own_player = repo.find_or_create_player(session, "Delantero No Name", primary_position="DC", actor_id=admin.id)
        repo.assign_player_to_roster(session, own.id, season.id, own_player.id, 10, actor_id=admin.id)
        planning_repo.upsert_season_decision(session, admin.id, season_id=season.id, player_id=own_player.id, status="Plantilla", priority=2, model_role_id=role.id, director_note="Referencia interna", fit_score=7.8, current_level=7.5, potential_score=7.5, criteria_scores={c1.id:8.0,c2.id:7.5,c3.id:8.5})

        payload = player_report_repo.build_player_report_360(session, player.id, season_id=season.id)
        assert payload["postmatch"]["average"] == 8.2
        assert payload["fit_score"] == 8.4
        assert payload["role"].id == role.id
        assert {r["name"]: r["score"] for r in payload["criteria"]} == {"Desmarque ruptura":9.0,"Ataque área":8.0,"Presión":8.0}
        assert payload["strengths"][0] == "Profundidad"
        assert payload["weaknesses"][0] == "Juego de espaldas"
        assert payload["own_comparison"][0]["name"] == "Delantero No Name"
        assert payload["own_comparison"][0]["criteria_scores"][c1.id] == 8.0


def test_player_report_pdfs_are_generated_without_invented_data(session_factory):
    with session_factory.begin() as session:
        admin, reporter, scout, season, comp, own, rival = _seed(session)
        player = repo.find_or_create_player(session, "Jugador PDF", primary_position="MC", actor_id=admin.id)
        repo.assign_player_to_roster(session, rival.id, season.id, player.id, 8, actor_id=admin.id)
        _approved_postmatch(session, admin, reporter, season, comp, own, rival, player, rating=7.8)
        payload = player_report_repo.build_player_report_360(session, player.id, season_id=season.id)
        settings = {"club_name":"No Name","primary_color":"#B91C1C","secondary_color":"#111827"}
        executive = generate_player_executive_pdf(payload, settings)
        dossier = generate_player_360_pdf(payload, settings)
        assert executive.startswith(b"%PDF") and len(executive) > 1500
        assert dossier.startswith(b"%PDF") and len(dossier) > 1500
