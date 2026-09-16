"""4.4 regressions: real evidence, role tasks, incomplete lineups and stable navigation."""
from __future__ import annotations

import ast
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from core.postmatch_validation import validate_postmatch_draft
from models.entities import Participation, Report
from repositories import data_governance as governance
from repositories import league_intelligence as league
from repositories import player_report as player360
from repositories import scouting as repo
from repositories import workspaces
def _preserve_known_own_participants(rows, existing):
    source = (ROOT / "views" / "postmatch.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "_preserve_known_own_participants")
    scope = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / "views" / "postmatch.py"), "exec"), scope)
    return scope["_preserve_known_own_participants"](rows, existing)

ROOT = Path(__file__).resolve().parents[1]


def _seed(session):
    admin = repo.create_user(session, "Admin 44", "admin44@example.com", "pass", role="admin", roles=["admin", "director"], must_change_password=False)
    reporter = repo.create_user(session, "Informador 44", "info44@example.com", "pass", role="reporter", roles=["reporter"], actor_id=admin.id)
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Liga 44", actor_id=admin.id)
    own = repo.create_team(session, "C.D. Noname", actor_id=admin.id)
    rival = repo.create_team(session, "Equipo de liga", actor_id=admin.id)
    repo.set_own_team(session, own.id, admin.id)
    player = repo.find_or_create_player(session, "Jugador propio 44", primary_position="DC", actor_id=admin.id)
    repo.assign_player_to_roster(session, own.id, season.id, player.id, 9, admin.id)
    return admin, reporter, season, comp, own, rival, player


def _fixture(session, ids, day, status="published", score=None):
    admin, reporter, season, comp, own, rival, player = ids
    return repo.create_match(
        session, season_id=season.id, competition_id=comp.id,
        round_name=f"J{day}", match_date=date(2026, 9, day),
        home_team_id=own.id, away_team_id=rival.id, created_by=admin.id,
        kickoff_at=datetime(2026, 9, day, 17), schedule_status="confirmed",
        status=status, home_score=score, away_score=0 if score is not None else None,
    )


def test_confidence_never_invents_agreement_for_missing_or_single_author():
    empty = league.confidence_score(0, 0, 0)
    assert empty["label"] == "No evaluable" and empty["consensus"] == "No evaluable"
    assert empty["components"]["Consenso"]["score"] == 0
    inconsistent = league.confidence_score(0, 2, 0, date.today())
    assert inconsistent["score"] == 0 and inconsistent["label"] == "No evaluable"
    one = league.confidence_score(4, 1, 0)
    assert one["consensus"] == "No comparable"
    assert one["components"]["Consenso"]["score"] == 0
    many = league.confidence_score(4, 2, 0.2)
    assert many["consensus"] == "Muy alto" and many["components"]["Consenso"]["score"] > 0


def test_own_player_360_uses_only_own_reports_and_excludes_test_data(session_factory):
    with session_factory.begin() as session:
        ids = _seed(session)
        admin, reporter, season, comp, own, rival, player = ids
        match = _fixture(session, ids, 12, score=2)
        part = repo.replace_participations(session, match.id, own.id, [{
            "selected": True, "player_id": player.id, "shirt_number": 9,
            "starter": True, "position": "DC", "minute_in": 0,
            "minute_out": 90, "captain": False,
        }], admin.id)[0]
        repo.assign_reporters(session, match.id, [reporter.id], admin.id)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        repo.upsert_evaluation(session, report.id, player.id, own.id, part.id,
                               actor_id=reporter.id, observation_status="evaluated", general_rating=8.5)
        repo.submit_report(session, report.id, reporter.id)
        own_payload = player360.build_player_report_360(session, player.id, season_id=season.id)
        assert own_payload["is_own_player"]
        assert own_payload["postmatch"]["average"] == 8.5
        assert own_payload["own_postmatch"]["observations"] == 1
        assert own_payload["rival_postmatch"]["observations"] == 0
        assert own_payload["evidence"]["postmatch_observations"] == 1
        assert own_payload["postmatch"]["confidence"]["consensus"] == "No comparable"
        governance.mark_match_test(session, match.id, admin.id, True)
        hidden = player360.build_player_report_360(session, player.id, season_id=season.id)
        assert hidden["postmatch"]["observations"] == 0
        assert hidden["postmatch"]["average"] is None
        assert hidden["postmatch"]["confidence"]["label"] == "No evaluable"


def test_home_detects_past_unprepared_and_published_unassigned_and_skips_test(session_factory, monkeypatch):
    with session_factory.begin() as session:
        ids = _seed(session)
        admin, reporter, season, comp, own, rival, player = ids
        old = _fixture(session, ids, 10, status="scheduled")
        unassigned = _fixture(session, ids, 12, score=1)
        next_match = _fixture(session, ids, 20, status="scheduled")
        fake = _fixture(session, ids, 14, status="scheduled")
        governance.mark_match_test(session, fake.id, admin.id, True)
        monkeypatch.setattr(workspaces, "local_today", lambda: date(2026, 9, 16))
        data = workspaces.load_home_workspace(session, user_id=admin.id, roles={"admin"})
        actual = {(task["kind"], task["match_id"]) for task in data["tasks"]}
        assert ("prepare", old.id) in actual
        assert ("assign", unassigned.id) in actual
        assert all(mid != fake.id for _, mid in actual)
        assert data["last_match"].id == unassigned.id
        assert data["next_match"].id == next_match.id
        assert data["task_count"] == len(data["tasks"])
        repo.assign_reporters(session, unassigned.id, [reporter.id], admin.id)
        reporter_work = workspaces.load_home_workspace(session, user_id=reporter.id, roles={"reporter"})
        assert ("report", unassigned.id) in {(t["kind"], t["match_id"]) for t in reporter_work["tasks"]}
        assert all(t["match_id"] != fake.id for t in reporter_work["tasks"])


def test_partial_lineups_warn_but_do_not_force_invented_players():
    draft = {
        "kickoff_time": "17:00", "reporter_ids": [2], "own_xi": [],
        "rival_xi": [{"name": "Rival documentado"}], "own_subs": [], "rival_subs": [],
    }
    errors, warnings = validate_postmatch_draft(draft)
    assert not errors
    assert len(warnings) == 2
    draft["rival_xi"].append({"name": "Rival documentado"})
    errors, _ = validate_postmatch_draft(draft)
    assert any("repetido" in error for error in errors)
    draft["rival_xi"] = []
    draft["reporter_ids"] = []
    errors, _ = validate_postmatch_draft(draft)
    assert any("Informador" in error for error in errors)


def test_publishing_incomplete_lineup_keeps_existing_verified_participants():
    existing = [SimpleNamespace(player_id=3, shirt_number=3, starter=True, position="DFC",
                                minute_in=0, minute_out=90, captain=True, order_index=0),
                SimpleNamespace(player_id=12, shirt_number=12, starter=False, position="DC",
                                minute_in=65, minute_out=90, captain=False, order_index=1)]
    assert len(_preserve_known_own_participants([], existing)) == 2
    merged = _preserve_known_own_participants([{"player_id": 4, "starter": True}], existing)
    assert {row["player_id"] for row in merged} == {3, 4, 12}
    assert next(row for row in merged if row["player_id"] == 3)["captain"]
    with pytest.raises(ValueError, match="solapa"):
        _preserve_known_own_participants(
            [{"player_id": pid, "starter": True} for pid in range(20, 32)], existing)


def test_44_navigation_and_advanced_admin_contracts():
    home = (ROOT / "views/home.py").read_text(encoding="utf-8")
    squad = (ROOT / "views/squad.py").read_text(encoding="utf-8")
    admin = (ROOT / "views/admin_hub.py").read_text(encoding="utf-8")
    players = (ROOT / "views/player_hub.py").read_text(encoding="utf-8")
    jornada = (ROOT / "views/jornada.py").read_text(encoding="utf-8")
    assert "Mi trabajo" in home and "Último partido" in home and "Próximo partido" in home
    assert "Mostrar todas las tareas" in home
    assert "st.segmented_control" not in squad
    assert '"Mantenimiento avanzado"' in admin
    assert "_technical(user)" in admin
    assert "Rendimiento propio" in players and "Rendimiento rival" in players
    assert "Asignar Informadores" in jornada and "Continuar informe" in jornada
