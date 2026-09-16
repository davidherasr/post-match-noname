from __future__ import annotations

from datetime import date
from pathlib import Path

from core.federation_roster import parse_federation_roster
from repositories import matches as matches_repo
from repositories import scouting as repo

ROOT = Path(__file__).resolve().parents[1]


def _neutral_match(session):
    admin = repo.create_user(
        session, "Admin 407", "admin407@example.com", "ValidPass123!",
        role="admin", roles=["admin", "director", "scout", "reporter"], must_change_password=False,
    )
    season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    comp = repo.create_competition(session, "Regional Preferente", actor_id=admin.id)
    own = repo.create_team(session, "C.D. Noname", is_own_team=True, actor_id=admin.id)
    home = repo.create_team(session, "Sarego", actor_id=admin.id)
    away = repo.create_team(session, "Cubillos", actor_id=admin.id)
    repo.set_setting(session, "own_team_id", str(own.id), admin.id)
    match = matches_repo.create_match(
        session, season_id=season.id, competition_id=comp.id, round_name="Jornada 1",
        match_date=date(2026, 9, 13), home_team_id=home.id, away_team_id=away.id,
        created_by=admin.id, status="scheduled",
    )
    return admin, season, home, away, match


def test_release_407_contract():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.4.4"
    assert 'APP_VERSION = "4.4.4"' in (ROOT / "core/config.py").read_text(encoding="utf-8")
    assert 'REPORTS_PAGE_API_VERSION = "4.4.4"' in (ROOT / "views/reports.py").read_text(encoding="utf-8")


def test_parser_understands_starters_and_substitutes_sections():
    rows = parse_federation_roster(
        "TITULARES\n1;Portero;POR\n4;Central;DFC\nSUPLENTES\n12;Portero dos;POR\n14;Interior;MC"
    )
    assert [r.squad_role for r in rows] == ["starter", "starter", "substitute", "substitute"]
    assert [r.shirt_number for r in rows] == [1, 4, 12, 14]


def test_parser_plain_list_never_infers_match_role():
    rows = parse_federation_roster("1;Uno;POR\n2;Dos;LD\n3;Tres;DFC")
    assert all(r.squad_role is None for r in rows)


def test_federation_match_import_persists_explicit_squad_roles(session_factory):
    with session_factory.begin() as session:
        admin, season, home, _, match = _neutral_match(session)
        text = "TITULARES\n" + "\n".join(f"{n};Titular {n}" for n in range(1, 12))
        text += "\nSUPLENTES\n12;Suplente 12\n13;Suplente 13"
        result = matches_repo.import_federation_roster_text(
            session, team_id=home.id, season_id=season.id, actor_id=admin.id,
            match_id=match.id, text=text,
        )
        parts = matches_repo.get_participations(session, match.id, home.id)
        assert result["starters"] == 11
        assert result["substitutes"] == 2
        assert len([p for p in parts if p.starter]) == 11
        assert len([p for p in parts if not p.starter]) == 2


def test_known_formation_can_save_bench_and_reject_overlap(session_factory):
    with session_factory.begin() as session:
        admin, season, home, _, match = _neutral_match(session)
        matches_repo.import_federation_roster_text(
            session, team_id=home.id, season_id=season.id, actor_id=admin.id,
            text="\n".join(f"{n};Jugador {n}" for n in range(1, 15)),
        )
        roster = repo.get_roster(session, home.id, season.id)
        ids = [r.player_id for r in roster]
        parts = matches_repo.save_known_formation_lineup(
            session, match_id=match.id, team_id=home.id, actor_id=admin.id,
            formation="4-3-3", player_ids=ids[:11], substitute_ids=ids[11:14],
        )
        assert len([p for p in parts if p.starter]) == 11
        assert len([p for p in parts if not p.starter]) == 3


def test_jornada_labels_squad_status_and_42_flow():
    body = (ROOT / "views/jornada.py").read_text(encoding="utf-8")
    assert "🟢 TIT" in body
    assert "🟡 SUP" in body
    assert "⚪ PLANTILLA" in body
    assert "Estado del postpartido" in body
    assert "Estado de la lectura" in body
    assert "Seguimiento individual" in body
    assert "Dirección Deportiva · asignar seguimiento" not in body
    assert "TITULARES" in body and "SUPLENTES" in body
