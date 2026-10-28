"""Operational 4.5 acceptance: optional contributions and explainable DD evidence."""
from __future__ import annotations
from datetime import date
import pytest
from sqlalchemy import select, func
from models.entities import (Match, PlayerSeasonDecision, Player, PlayerEvaluation,
                             ReportAssignment, UnidentifiedPlayerSignal)
from core.postmatch_validation import validate_postmatch_draft
from repositories import scouting as repo, reports, unidentified_players as unknown
from repositories import dd_attention, observation_requests, workspaces
from repositories.player_report import build_player_report_360


def seed(session, profile="own_only"):
    admin = repo.create_user(session, "Director", "dir45@example.test", "pass", role="admin", roles=["admin", "director"])
    reporter = repo.create_user(session, "Observador 1", "inf45@example.test", "pass", role="reporter", actor_id=admin.id,
                                participation_profile=profile)
    second = repo.create_user(session, "Observador 2", "inf45b@example.test", "pass", role="reporter", actor_id=admin.id)
    season = repo.create_season(session, "2026/27", date(2026,7,1), date(2027,6,30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Regional 4.5", actor_id=admin.id)
    own = repo.create_team(session, "C.D. Noname", is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, "Club Cubillos", actor_id=admin.id)
    third = repo.create_team(session, "Club Vallesina", actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    m = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1",
                          match_date=date(2026,9,13), home_team_id=own.id, away_team_id=rival.id,
                          status="scheduled", schedule_status="provisional", created_by=admin.id)
    m.window_start, m.window_end = date(2026,9,12), date(2026,9,13)
    return admin, reporter, second, season, comp, own, rival, third, m


def player(session, admin, team, season, name, pos="EI"):
    item = repo.find_or_create_player(session, name, primary_position=pos, actor_id=admin.id)
    repo.assign_player_to_roster(session, team.id, season.id, item.id, 11, admin.id)
    return item


def contribution(session, match, reporter, *, own_score=None, rival_score=None, note=None):
    r = repo.get_or_create_report(session, match.id, reporter.id)
    repo.save_report_summary(session, r.id, actor_id=reporter.id, rival_level=None,
        opponent_overview=None, own_team_note=None, standout_player_id=None,
        key_takeaways=note, own_team_rating=own_score, rival_team_rating=rival_score)
    return r


def test_no_schedule_no_assignment_one_side_only_and_admin_cannot_sign(session_factory):
    with session_factory.begin() as s:
        a, r, _, season, comp, own, rival, _, m = seed(s)
        assert r.participation_profile == "own_only" and m.kickoff_at is None
        with pytest.raises(PermissionError):
            repo.get_or_create_report(s, m.id, a.id)
        report = contribution(s, m, r, own_score=7)
        assert report.rival_team_rating is None
        assert s.scalar(select(ReportAssignment).where(ReportAssignment.match_id == m.id,
            ReportAssignment.user_id == r.id)).required is False
        repo.submit_report(s, report.id, r.id)
        assert report.status == "incorporated"
        assert report.rival_team_rating is None


def test_only_rival_and_no_admin_publish(session_factory):
    with session_factory.begin() as s:
        a, r, _, _, _, _, _, _, m = seed(s)
        report = contribution(s, m, r, rival_score=6)
        repo.submit_report(s, report.id, r.id)
        assert report.own_team_rating is None
        assert m.status == "scheduled"


def test_empty_own_report_rejected_and_empty_postmatch_admin_valid(session_factory):
    with session_factory.begin() as s:
        a, r, _, _, _, _, _, _, m = seed(s)
        report = repo.get_or_create_report(s, m.id, r.id)
        with pytest.raises(ValueError, match="aportación|observación"):
            repo.submit_report(s, report.id, r.id)
        assert validate_postmatch_draft({"reporter_ids": [], "kickoff_time": "",
            "own_xi": [], "rival_xi": [], "own_subs": [], "rival_subs": []})[0] == []


def test_attention_without_grade_and_top3_without_grade(session_factory):
    with session_factory.begin() as s:
        a, r, _, season, _, _, rival, _, m = seed(s)
        p = player(s, a, rival, season, "Extremo confirmado")
        report = repo.get_or_create_report(s, m.id, r.id)
        e = reports.upsert_evaluation(s, report.id, p.id, rival.id, None, actor_id=r.id,
            observation_status="observed", general_rating=None, attention_signal=True, highlight_rank=1)
        assert e.general_rating is None and e.highlight_rank == 1
        repo.submit_report(s, report.id, r.id)
        result = build_player_report_360(s, p.id, season_id=season.id)
        assert result["knowledge_45"]["rival"]["top_3"] == 1
        assert result["knowledge_45"]["rival"]["ratings"] == 0
        assert result["knowledge_45"]["rival"]["average"] is None


def test_anonymous_only_no_fake_person_reconcile_once(session_factory):
    with session_factory.begin() as s:
        a, r, _, season, _, _, rival, _, m = seed(s)
        report = repo.get_or_create_report(s, m.id, r.id)
        before = s.scalar(select(func.count(Player.id)))
        row = unknown.save_signal(s, actor_id=r.id, match_id=m.id, team_id=rival.id,
            position="EI", shirt_number=11, rating=8, attention_signal=True,
            highlight_rank=1, source="own_report")
        assert s.scalar(select(func.count(Player.id))) == before
        repo.submit_report(s, report.id, r.id)
        assert any(x["unknown_id"] == row.id for x in dd_attention.attention_feed(s, season.id) if x.get("unknown_id"))
        verified = player(s, a, rival, season, "EI real Cubillos")
        unknown.resolve(s, actor_id=a.id, signal_id=row.id, player_id=verified.id)
        unknown.resolve(s, actor_id=a.id, signal_id=row.id, player_id=verified.id)
        cases = [x for x in dd_attention.attention_feed(s, season.id) if x["player_id"] == verified.id]
        assert len(cases) == 1 and cases[0]["events"] == 1 and cases[0]["average"] == 8
        assert s.scalar(select(func.count(PlayerEvaluation.id))) == 0
        assert row.resolved_by == a.id and row.resolved_at is not None
        cover = build_player_report_360(s, verified.id, season_id=season.id)["knowledge_45"]["rival"]
        assert cover["matches"] == 1 and cover["resolved_anonymous"] == 1


def test_duplicate_rank_refused_across_unknown_and_named(session_factory):
    with session_factory.begin() as s:
        a, r, _, season, _, _, rival, _, m = seed(s)
        p = player(s, a, rival, season, "Otro lateral Cubillos", "LD")
        unknown.save_signal(s, actor_id=r.id, match_id=m.id, team_id=rival.id,
            position="EI", highlight_rank=2, source="own_report")
        report = repo.get_or_create_report(s, m.id, r.id)
        with pytest.raises(ValueError, match="puesto"):
            reports.upsert_evaluation(s, report.id, p.id, rival.id, None, actor_id=r.id,
                observation_status="observed", highlight_rank=2)


def test_position_memory_keeps_contextual_and_match_override(session_factory):
    with session_factory.begin() as s:
        a, r, _, season, _, _, rival, _, m = seed(s)
        p = player(s, a, rival, season, "Jugador polivalente", "DC")
        unknown.set_usual_position(s, actor_id=a.id, team_id=rival.id, season_id=season.id,
                                   player_id=p.id, position="EI")
        assert unknown.known_position(s, player_id=p.id, team_id=rival.id, season_id=season.id) == "EI"
        parts = repo.replace_participations(s, m.id, rival.id, [{"player_id": p.id,
            "selected": True, "position": "LD", "starter": True}], actor_id=a.id)
        assert unknown.known_position(s, player_id=p.id, team_id=rival.id,
            season_id=season.id, match_id=m.id) == "LD"
        assert unknown.known_position(s, player_id=p.id, team_id=rival.id,
            season_id=season.id) == "EI"


def test_suggest_last_formation_not_current_confirmed(session_factory):
    with session_factory.begin() as s:
        a, r, _, season, comp, own, rival, _, m = seed(s)
        m.home_formation = "4-3-3"
        m.home_formation_known = True
        next_fixture = repo.create_match(s, season_id=season.id, competition_id=comp.id,
            round_name="J2", match_date=date(2026,9,20), home_team_id=own.id,
            away_team_id=rival.id, created_by=a.id, status="scheduled")
        shape, source = unknown.latest_formation_suggestion(s, team_id=own.id,
            season_id=season.id, current_match_id=next_fixture.id)
        assert (shape, source) == ("4-3-3", m.id)
        assert next_fixture.home_formation is None and not next_fixture.home_formation_known


def test_rating_eight_no_automatic_dd_decision_and_repeat_rule(session_factory):
    with session_factory.begin() as s:
        a, r, _, season, comp, own, rival, _, m = seed(s)
        p = player(s, a, rival, season, "Señal fuerte 45")
        for mid, day in [(m, 13), (repo.create_match(s, season_id=season.id,
            competition_id=comp.id, round_name="J2", match_date=date(2026,9,day:=20),
            home_team_id=own.id, away_team_id=rival.id, status="scheduled", created_by=a.id),20)]:
            report = repo.get_or_create_report(s, mid.id, r.id)
            reports.upsert_evaluation(s, report.id, p.id, rival.id, None, actor_id=r.id,
                observation_status="evaluated", general_rating=8, highlight_rank=2)
            repo.submit_report(s, report.id, r.id)
        cards = [x for x in dd_attention.attention_feed(s, season.id) if x["player_id"] == p.id]
        assert len(cards) == 1 and cards[0]["matches"] == 2
        assert any("dos o más" in v for v in cards[0]["reasons"])
        assert s.scalar(select(PlayerSeasonDecision).where(PlayerSeasonDecision.player_id == p.id)) is None


def test_disagreement_and_request_from_original_evidence(session_factory):
    with session_factory.begin() as s:
        a, r, r2, season, _, _, rival, _, m = seed(s)
        p = player(s, a, rival, season, "Discrepancia 45")
        e1 = None
        for author, grade in [(r,8), (r2,5)]:
            report = repo.get_or_create_report(s, m.id, author.id)
            ev = reports.upsert_evaluation(s, report.id, p.id, rival.id, None, actor_id=author.id,
                observation_status="evaluated", general_rating=grade)
            if author.id == r.id:
                e1 = ev
            repo.submit_report(s, report.id, author.id)
        cards = [c for c in dd_attention.attention_feed(s, season.id) if c["player_id"] == p.id]
        assert cards[0]["authors"] == 2 and cards[0]["disagreements"]
        req = observation_requests.ask_about_evidence(s, actor_id=a.id, evidence_kind="own_report",
            evidence_id=e1.id)
        assert req.origin_player_evaluation_id == e1.id and req.target_match_id == m.id
        assert observation_requests.ask_about_evidence(s, actor_id=a.id,
            evidence_kind="own_report", evidence_id=e1.id).id == req.id
        assert s.scalar(select(func.count(PlayerEvaluation.id)).where(PlayerEvaluation.player_id == p.id)) == 2


def test_admin_cannot_open_sporting_report_as_author_and_test_excluded(session_factory):
    with session_factory.begin() as s:
        a, r, _, season, comp, own, rival, _, m = seed(s)
        with pytest.raises(PermissionError):
            repo.get_or_create_report(s, m.id, a.id)
        p = player(s, a, rival, season, "Excluido del feed")
        report = repo.get_or_create_report(s, m.id, r.id)
        reports.upsert_evaluation(s, report.id, p.id, rival.id, None, actor_id=r.id,
            observation_status="evaluated", general_rating=9)
        repo.submit_report(s, report.id, r.id)
        assert any(row["player_id"] == p.id for row in dd_attention.attention_feed(s, season.id))
        m.is_test = True
        assert not any(row["player_id"] == p.id for row in dd_attention.attention_feed(s, season.id))
