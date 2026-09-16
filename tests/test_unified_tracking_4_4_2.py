"""4.4.2: one logical event, optional postmatch enrichment, DD audit workflow."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from models.entities import AuditLog, PlayerEvaluation, ScoutObservation
from repositories import scouting as repo
from repositories import tracking, planning, player_report, player_catalog

ROOT = Path(__file__).resolve().parents[1]


def _case(session):
    admin = repo.create_user(session, "Admin", "a442@example.com", "pass", role="admin", roles=["admin", "director"])
    author = repo.create_user(session, "David", "d442@example.com", "pass", role="reporter", roles=["reporter"], actor_id=admin.id,
                              can_track_players=True)
    without_flag = repo.create_user(session, "Normal", "n442@example.com", "pass", role="reporter", roles=["reporter"], actor_id=admin.id)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Liga 442", actor_id=admin.id)
    own = repo.create_team(session, "C.D. Noname", actor_id=admin.id)
    rival = repo.create_team(session, "Rival", actor_id=admin.id)
    repo.set_own_team(session, own.id, admin.id)
    player = repo.find_or_create_player(session, "Jugador rival", primary_position="LI", actor_id=admin.id)
    own_player = repo.find_or_create_player(session, "Jugador propio", primary_position="DC", actor_id=admin.id)
    repo.assign_player_to_roster(session, rival.id, season.id, player.id, 3, actor_id=admin.id)
    repo.assign_player_to_roster(session, own.id, season.id, own_player.id, 9, actor_id=admin.id)
    match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="J1",
        match_date=date(2026, 9, 12), home_team_id=own.id, away_team_id=rival.id,
        created_by=admin.id, status="published", kickoff_at=datetime(2026, 9, 12, 17), schedule_status="confirmed")
    parts = repo.replace_participations(session, match.id, rival.id, [
        {"selected": True, "player_id": player.id, "shirt_number": 3,
         "starter": True, "position": "LI", "minute_in": 0, "minute_out": 90, "captain": False}
    ], admin.id)
    repo.assign_reporters(session, match.id, [author.id], admin.id)
    report = repo.get_or_create_report(session, match.id, author.id)
    repo.upsert_evaluation(session, report.id, player.id, rival.id, parts[0].id,
        actor_id=author.id, observation_status="evaluated", general_rating=8.0,
        short_note="Lateral de perfil combinativo")
    repo.submit_report(session, report.id, author.id)
    evaluation = session.scalar(select(PlayerEvaluation).where(PlayerEvaluation.report_id == report.id,
                                                               PlayerEvaluation.player_id == player.id))
    return admin, author, without_flag, season, own, rival, player, own_player, match, report, evaluation


def test_optional_enrichment_is_idempotent_and_reuses_postmatch_rating(session_factory):
    with session_factory.begin() as session:
        admin, author, other, season, own, rival, player, own_player, match, report, ev = _case(session)
        assert [x.id for x in tracking.report_tracking_candidates(session, report.id, author.id)] == [ev.id]
        assert not tracking.match_observations(session, player.id, author.id, match.id)
        observation = tracking.enrich_postmatch_evaluation(session, evaluation_id=ev.id, author_id=author.id,
            summary="Defiende bien su lado", strengths="Anticipación", recommendation="Volver a ver")
        original_id = observation.id
        assert observation.general_rating == 8.0 and observation.player_evaluation_id == ev.id
        second = tracking.enrich_postmatch_evaluation(session, evaluation_id=ev.id, author_id=author.id,
            summary="Conclusión revisada", recommendation="Seguimiento")
        assert second.id == original_id and second.general_rating == 8.0
        assert len(tracking.match_observations(session, player.id, author.id, match.id)) == 1
        dossier = player_report.build_player_report_360(session, player.id, season_id=season.id)
        assert len(dossier["timeline"]) == 1
        assert dossier["timeline"][0]["source"] == "Postpartido + seguimiento"
        assert dossier["timeline"][0]["rating"] == 8.0
        assert dossier["evidence"]["specific_observations"] == 1
        result = player_catalog.search_players(session, season_id=season.id, search="Jugador rival")
        assert next(row for row in result["rows"] if row["player"].id == player.id)["tracking_count"] == 1
        events = tracking.tracking_activity(session, season.id)
        assert len(events) == 1 and events[0]["player"].id == player.id and events[0]["author"].id == author.id
        assert session.scalar(select(AuditLog).where(AuditLog.action == "postmatch_tracking_enriched"))


def test_cannot_track_own_or_without_permission_and_8_does_not_create_automatically(session_factory):
    with session_factory.begin() as session:
        admin, author, other, season, own, rival, player, own_player, match, report, ev = _case(session)
        assert tracking.match_observations(session, player.id, author.id, match.id) == []
        with pytest.raises(PermissionError):
            tracking.report_tracking_candidates(session, report.id, other.id)
        with pytest.raises(PermissionError):
            tracking.get_or_create_match_observation(session, player_id=player.id, author_id=other.id, match_id=match.id)
        with pytest.raises(ValueError, match="No Name"):
            tracking.get_or_create_match_observation(session, player_id=own_player.id, author_id=author.id, match_id=match.id)


def test_legacy_duplicate_display_once_and_dd_can_delete_exact_duplicate(session_factory):
    with session_factory.begin() as session:
        admin, author, other, season, own, rival, player, own_player, match, report, ev = _case(session)
        one, created = tracking.get_or_create_match_observation(session, player_id=player.id,
            author_id=author.id, match_id=match.id)
        one.general_rating = 8.0
        one.summary = "Primera"
        one.status = "submitted"
        # Legacy duplicates are never silently rewritten on deployment.
        extra = ScoutObservation(profile_id=one.profile_id, reviewer_id=author.id,
            match_id=match.id, general_rating=8.0, summary="Segunda",
            status="submitted", source_type="specific", observation_level="observation")
        session.add(extra)
        session.flush()
        before = tracking.duplicate_groups(session, season.id)
        assert len(before) == 1 and len(before[0]["observations"]) == 2
        assert len(tracking.tracking_activity(session, season.id)) == 1
        report360 = player_report.build_player_report_360(session, player.id, season_id=season.id)
        assert len(report360["timeline"]) == 1 and report360["timeline"][0]["rating"] == 8.0
        assert report360["evidence"]["specific_observations"] == 1
        with pytest.raises(PermissionError):
            tracking.delete_duplicate_observation(session, observation_id=extra.id, actor_id=author.id)
        tracking.delete_duplicate_observation(session, observation_id=extra.id, actor_id=admin.id)
        assert session.get(ScoutObservation, extra.id) is None and session.get(ScoutObservation, one.id)
        assert tracking.duplicate_groups(session, season.id) == []
        assert session.scalar(select(AuditLog).where(AuditLog.action == "delete_duplicate_tracking"))
        with pytest.raises(ValueError, match="última"):
            tracking.delete_duplicate_observation(session, observation_id=one.id, actor_id=admin.id)



def test_dd_cannot_delete_linked_postmatch_evidence_when_duplicate_exists(session_factory):
    with session_factory.begin() as session:
        admin, author, other, season, own, rival, player, own_player, match, report, ev = _case(session)
        linked = tracking.enrich_postmatch_evaluation(session, evaluation_id=ev.id, author_id=author.id)
        duplicate = ScoutObservation(profile_id=linked.profile_id, reviewer_id=author.id,
            match_id=match.id, general_rating=8.0, summary="Duplicado previo",
            status="submitted", source_type="specific", observation_level="observation")
        session.add(duplicate)
        session.flush()
        with pytest.raises(ValueError, match="vinculado"):
            tracking.delete_duplicate_observation(session, observation_id=linked.id, actor_id=admin.id)
        tracking.delete_duplicate_observation(session, observation_id=duplicate.id, actor_id=admin.id)
        assert session.get(ScoutObservation, linked.id).player_evaluation_id == ev.id

def test_reuse_existing_legacy_followup_without_new_physical_row(session_factory):
    with session_factory.begin() as session:
        admin, author, other, season, own, rival, player, own_player, match, report, ev = _case(session)
        old, _ = tracking.get_or_create_match_observation(session, player_id=player.id,
            author_id=author.id, match_id=match.id)
        old.summary = "Seguimiento ya redactado"
        old.general_rating = 7.0
        old.status = "submitted"
        linked = tracking.enrich_postmatch_evaluation(session, evaluation_id=ev.id, author_id=author.id)
        assert linked.id == old.id and linked.general_rating == 8.0
        assert linked.summary == "Seguimiento ya redactado"
        assert linked.player_evaluation_id == ev.id
        assert len(tracking.match_observations(session, player.id, author.id, match.id)) == 1


def test_ui_routes_offer_optional_wizard_and_dd_activity_without_old_scout_missions():
    reports = (ROOT / "views/reports.py").read_text(encoding="utf-8")
    home = (ROOT / "views/home.py").read_text(encoding="utf-8")
    squad = (ROOT / "views/squad.py").read_text(encoding="utf-8")
    assert "_render_postmatch_tracking_step" in reports
    assert "postmatch_tracking_wizard" in reports
    assert 'with st.form(f"postmatch_tracking_step_442_{report_id}")' in reports
    assert 'tracking_repo.tracking_activity' in home and '"Seguimiento"' in squad
    assert 'tracking_repo.duplicate_groups' in squad and 'tracking_repo.delete_duplicate_observation' in squad


def test_additive_migration_from_0013_and_fresh_database(tmp_path):
    """Real CLI upgrade in isolated SQLite; never connects to the user's Supabase."""
    import os
    import subprocess
    import sys
    from sqlalchemy import create_engine, inspect, text

    for kind in ("fresh", "upgrade"):
        uri = f"sqlite:///{tmp_path / (kind + '.sqlite')}"
        env = {**os.environ, "DATABASE_URL": uri, "DEMO_MODE": "true", "RUN_MIGRATIONS": "true"}
        steps = ["head"] if kind == "fresh" else ["0013_data_governance_4_2_3", "head"]
        for revision in steps:
            completed = subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
            assert completed.returncode == 0, completed.stdout + completed.stderr
            if kind == "upgrade" and revision == "0013_data_governance_4_2_3":
                # Simulate existing historical rows before the additive migration.
                # Foreign identifiers are illustrative; this test checks that the
                # batch ALTER copies existing data without deduplicating/deleting.
                historical = create_engine(uri, future=True)
                with historical.begin() as conn:
                    for observation_id in (71, 72):
                        conn.execute(text("""INSERT INTO scout_observations
                            (id, profile_id, reviewer_id, source_type, observation_level,
                             status, observed_at, created_at, updated_at, summary)
                            VALUES (:id, 3, 2, 'specific', 'observation', 'submitted',
                                    '2026-09-12 17:00:00', '2026-09-12 18:00:00',
                                    '2026-09-12 18:00:00', 'Texto histórico')"""), {"id": observation_id})
                historical.dispose()
        engine = create_engine(uri, future=True)
        try:
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0015_observation_requests_4_4_3"
            inspector = inspect(engine)
            assert "player_evaluation_id" in {col["name"] for col in inspector.get_columns("scout_observations")}
            assert "uq_scout_observation_evaluation_442" in {idx["name"] for idx in inspector.get_indexes("scout_observations")}
            if kind == "upgrade":
                with engine.connect() as connection:
                    assert connection.execute(text("SELECT id, summary FROM scout_observations ORDER BY id")).all() == [
                        (71, "Texto histórico"), (72, "Texto histórico")]
        finally:
            engine.dispose()
