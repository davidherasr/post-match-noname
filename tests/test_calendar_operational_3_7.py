from __future__ import annotations

from datetime import date, datetime

import pytest

from core.calendar_import import parse_calendar_text
from core.schedule import is_schedule_confirmed
from repositories import calendar as calendar_repo
from repositories import planning as planning_repo
from repositories import scouting as repo


def _base(session):
    admin = repo.create_user(
        session, "Admin 37", "admin37@example.com", "ValidPass123!",
        role="admin", roles=["admin", "director"], must_change_password=False,
    )
    reporter = repo.create_user(
        session, "Reporter 37", "reporter37@example.com", "ValidPass123!",
        role="reporter", actor_id=admin.id, must_change_password=False,
    )
    scout = repo.create_user(
        session, "Seguimiento 37", "scout37@example.com", "ValidPass123!",
        role="reporter", roles=["reporter"], actor_id=admin.id, must_change_password=False, can_track_players=True,
    )
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Liga 37", actor_id=admin.id)
    own = repo.create_team(session, "C.D. Noname", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "La Bañeza F.C.", actor_id=admin.id)
    other = repo.create_team(session, "Laguna", actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    return admin, reporter, scout, season, comp, own, rival, other


def test_provisional_fixture_is_plannable_but_not_observable_until_confirmed(session_factory):
    with session_factory.begin() as session:
        admin, _, scout, season, comp, _, rival, other = _base(session)
        rows, errors = parse_calendar_text("6;18/10/2026;La Bañeza F.C.;Laguna", default_year=2026)
        assert not errors
        calendar_repo.import_fixtures(session, season_id=season.id, competition_id=comp.id, rows=rows, actor_id=admin.id)
        match = calendar_repo.list_calendar(session, season_id=season.id)[0]
        assert match.schedule_status == "provisional"
        assert not is_schedule_confirmed(match)

        player = repo.find_or_create_player(session, "Objetivo 37", primary_position="DC", actor_id=admin.id)
        repo.assign_player_to_roster(session, rival.id, season.id, player.id, 9, actor_id=admin.id)
        mission = planning_repo.create_mission(
            session, match_id=match.id, mission_type="player", title="Ver delantero",
            assigned_to=scout.id, requested_by=admin.id, target_team_id=rival.id,
            player_ids=[player.id], purpose="Planificar antes de conocer horario", priority=1,
        )
        assert mission.status == "pending"
        assert mission.due_at is None

        with pytest.raises(ValueError, match="horario pendiente"):
            planning_repo.create_observation(
                session, player_id=player.id, reviewer_id=scout.id,
                match_id=match.id, mission_id=mission.id, source_type="specific",
            )

        kickoff = datetime(2026, 10, 18, 17, 30)
        calendar_repo.update_schedule(session, match.id, admin.id, kickoff_at=kickoff)
        assert is_schedule_confirmed(match)
        # 4.2.1: historical ScoutMission records are no longer part of the active calendar workflow.
        # The match confirmation enables the observation, but does not mutate legacy mission deadlines.
        assert mission.due_at is None

        obs = planning_repo.create_observation(
            session, player_id=player.id, reviewer_id=scout.id,
            match_id=match.id, mission_id=mission.id, source_type="specific",
        )
        assert obs.match_id == match.id
        assert mission.status == "in_progress"


def test_reimporting_provisional_calendar_preserves_manually_confirmed_kickoff(session_factory):
    with session_factory.begin() as session:
        admin, _, _, season, comp, own, rival, _ = _base(session)
        rows, errors = parse_calendar_text("1;13/09/2026;C.D. Noname;La Bañeza F.C.", default_year=2026)
        assert not errors
        calendar_repo.import_fixtures(session, season_id=season.id, competition_id=comp.id, rows=rows, actor_id=admin.id)
        match = calendar_repo.list_calendar(session, season_id=season.id, team_id=own.id)[0]
        confirmed = datetime(2026, 9, 12, 18, 0)
        calendar_repo.update_schedule(session, match.id, admin.id, kickoff_at=confirmed, venue="Campo real")

        # Federation source is imported again later with its original reference Sunday.
        result = calendar_repo.import_fixtures(session, season_id=season.id, competition_id=comp.id, rows=rows, actor_id=admin.id)
        assert result["updated"] == 1
        assert match.kickoff_at == confirmed
        assert match.match_date == date(2026, 9, 12)
        assert match.schedule_status == "confirmed"
        assert match.venue == "Campo real"


def test_scheduled_match_cannot_open_new_postmatch_report_without_confirmed_kickoff(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, season, comp, own, rival, _ = _base(session)
        match = repo.create_match(
            session, season_id=season.id, competition_id=comp.id, round_name="J1",
            match_date=date(2026, 9, 13), home_team_id=own.id, away_team_id=rival.id,
            created_by=admin.id, status="scheduled", schedule_status="provisional",
        )
        with pytest.raises(ValueError, match="horario del partido todavía no está confirmado"):
            repo.get_or_create_report(session, match.id, reporter.id)


def test_multirole_director_permission_uses_all_roles_not_only_primary(session_factory):
    with session_factory.begin() as session:
        admin, reporter, scout, season, comp, own, rival, _ = _base(session)
        # A user may combine Informador + Dirección Deportiva while tracking remains an independent capability.
        repo.set_user_roles(session, scout.id, ["reporter", "director"], actor_id=admin.id, primary_role="reporter")
        match = repo.create_match(
            session, season_id=season.id, competition_id=comp.id, round_name="J2",
            match_date=date(2026, 9, 20), home_team_id=own.id, away_team_id=rival.id,
            created_by=admin.id, status="published", kickoff_at=datetime(2026, 9, 20, 17, 0), schedule_status="confirmed",
        )
        report = repo.get_or_create_report(session, match.id, reporter.id)
        # Secondary director role is enough to edit another reporter's summary.
        repo.save_report_summary(
            session, report.id, rival_level=None, opponent_overview="Revisión DD",
            own_team_note=None, key_takeaways=None, standout_player_id=None,
            actor_id=scout.id,
        )
        assert report.opponent_overview == "Revisión DD"
