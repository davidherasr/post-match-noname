from __future__ import annotations

from datetime import date
from pathlib import Path

from core.federation_roster import parse_federation_roster
from repositories import matches as matches_repo
from repositories import scouting as repo


def _neutral_match(session):
    admin = repo.create_user(
        session, "Admin 40", "admin40@example.com", "ValidPass123!",
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


def test_federation_roster_parser_accepts_realistic_formats():
    rows = parse_federation_roster("1;Ángel Pérez;POR\n7 Mario López\n10 - Carlos Gómez\nPedro García\n7 Mario López")
    assert [(r.shirt_number, r.name, r.position) for r in rows] == [
        (1, "Ángel Pérez", "POR"),
        (7, "Mario López", None),
        (10, "Carlos Gómez", None),
        (None, "Pedro García", None),
    ]


def test_neutral_match_can_mix_known_and_unknown_formations(session_factory):
    with session_factory.begin() as session:
        admin, _, _, _, match = _neutral_match(session)
        matches_repo.update_match_study_context(
            session, match.id, admin.id,
            video_available=True, video_reference="Federación / vídeo 1",
            home_formation_known=True, away_formation_known=False,
            home_formation="4-3-3", away_formation=None,
            study_notes="Sarego identificado; Cubillos sin estructura fiable.",
        )
        stored = matches_repo.get_match(session, match.id)
        assert stored.video_available is True
        assert stored.home_formation_known is True
        assert stored.home_formation == "4-3-3"
        assert stored.away_formation_known is False
        assert stored.away_formation is None
        assert "Cubillos" in stored.study_notes


def test_federation_roster_import_does_not_create_match_participations(session_factory):
    with session_factory.begin() as session:
        admin, season, _, away, match = _neutral_match(session)
        result = matches_repo.import_federation_roster_text(
            session, team_id=away.id, season_id=season.id, actor_id=admin.id,
            text="1;Portero Cubillos;POR\n4;Central Cubillos;DFC\n9;Delantero Cubillos;DC",
        )
        roster = repo.get_roster(session, away.id, season.id)
        assert result["rows"] == 3
        assert [r.shirt_number for r in roster] == [1, 4, 9]
        assert matches_repo.get_participations(session, match.id, away.id) == []


def test_known_formation_lineup_is_saved_in_slot_order(session_factory):
    with session_factory.begin() as session:
        admin, season, home, _, match = _neutral_match(session)
        matches_repo.import_federation_roster_text(
            session, team_id=home.id, season_id=season.id, actor_id=admin.id,
            text="\n".join(f"{n};Jugador {n}" for n in range(1, 12)),
        )
        roster = repo.get_roster(session, home.id, season.id)
        matches_repo.update_match_study_context(
            session, match.id, admin.id, video_available=False,
            home_formation_known=True, away_formation_known=False,
            home_formation="4-3-3", away_formation=None,
        )
        matches_repo.save_known_formation_lineup(
            session, match_id=match.id, team_id=home.id, actor_id=admin.id,
            formation="4-3-3", player_ids=[r.player_id for r in roster],
        )
        parts = matches_repo.get_participations(session, match.id, home.id)
        assert len(parts) == 11
        assert [p.order_index for p in parts] == list(range(11))
        assert parts[0].position == "POR"
        assert parts[-1].position == "EI"


def test_match_hub_contains_independent_study_controls():
    source = Path("views/jornada.py").read_text(encoding="utf-8")
    assert "Vídeo disponible" in source
    assert "home_formation_known" in source
    assert "away_formation_known" in source
    assert "Formación desconocida" in source
    assert "render_campogram" in source
