from __future__ import annotations

from datetime import date

from core.workflow_defaults import recent_match_defaults
from repositories import scouting as repo


def _seed(session):
    admin = repo.create_user(session, "Admin", "admin341@example.com", "ValidPass123!", role="admin", must_change_password=False)
    reporter = repo.create_user(session, "Informador", "reporter341@example.com", "ValidPass123!", role="reporter", must_change_password=False)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    competition = repo.create_competition(session, "Liga", "España", admin.id)
    own = repo.create_team(session, "No Name", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "Rival", actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    return admin, reporter, season, competition, own, rival


def test_recent_match_defaults_reuse_competition_formation_and_reporters(session_factory):
    with session_factory.begin() as session:
        admin, reporter, season, competition, own, rival = _seed(session)
        match = repo.create_match(
            session,
            season_id=season.id,
            competition_id=competition.id,
            round_name="Jornada 1",
            match_date=date(2026, 8, 10),
            home_team_id=rival.id,
            away_team_id=own.id,
            created_by=admin.id,
            home_formation="4-3-3",
            away_formation="4-4-2",
            status="published",
        )
        repo.assign_reporters(session, match.id, [reporter.id], admin.id)
        defaults = recent_match_defaults(session, own.id, season.id)

    assert defaults["competition_id"] == competition.id
    assert defaults["own_formation"] == "4-4-2"
    assert defaults["reporter_ids"] == [reporter.id]
    assert defaults["defaults_source_round"] == "Jornada 1"


def test_recent_match_defaults_are_empty_without_previous_match(session_factory):
    with session_factory.begin() as session:
        admin, reporter, season, competition, own, rival = _seed(session)
        defaults = recent_match_defaults(session, own.id, season.id)
    assert defaults == {}
