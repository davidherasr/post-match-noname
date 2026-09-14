from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from core.permissions import can_admin, can_direct, can_scout, navigation_for
from core.security import verify_password
from repositories import planning as planning_repo
from repositories import scouting as repo

ROOT = Path(__file__).resolve().parents[1]


def _user_dict(*roles: str) -> dict:
    return {"id": 1, "role": roles[0] if roles else "reporter", "roles": list(roles)}


def test_release_411_contract_and_user_lifecycle_head():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.1.1"
    assert 'APP_VERSION = "4.1.1"' in (ROOT / "core/config.py").read_text(encoding="utf-8")
    assert 'REPORTS_PAGE_API_VERSION = "4.1.1"' in (ROOT / "views/reports.py").read_text(encoding="utf-8")
    migration = ROOT / "alembic/versions/0011_user_lifecycle_4_1_1.py"
    assert migration.exists()
    assert 'down_revision = "0010_core_workspace_schema_repair_4_0_4"' in migration.read_text(encoding="utf-8")


def test_roles_are_orthogonal_not_admin_hierarchy():
    admin = _user_dict("admin")
    director = _user_dict("director")
    scout = _user_dict("scout")
    multi = _user_dict("admin", "director", "scout")

    assert can_admin(admin)
    assert not can_direct(admin)
    assert not can_scout(admin)
    assert "Administración" in navigation_for(admin)
    assert "Plantilla" not in navigation_for(admin)
    assert can_direct(director)
    assert not can_scout(director)
    assert "Plantilla" in navigation_for(director)
    assert can_scout(scout)
    assert not can_direct(scout)
    assert can_admin(multi) and can_direct(multi) and can_scout(multi)


def test_simple_passwords_are_valid_and_never_force_change(session_factory):
    with session_factory.begin() as session:
        admin = repo.create_user(
            session, "Admin", "admin411@example.com", "1",
            role="admin", roles=["admin"], must_change_password=False,
        )
        user = repo.create_user(
            session, "Scout", "scout411@example.com", "1234",
            role="scout", roles=["scout"], actor_id=admin.id, must_change_password=True,
        )
        assert user.must_change_password is False
        assert verify_password("1234", user.password_hash)
        assert repo.authenticate(session, "scout411@example.com", "1234") is not None

        repo.update_user(session, user.id, password="x", actor_id=admin.id, force_password_change=True)
        assert user.must_change_password is False
        assert verify_password("x", user.password_hash)


def test_admin_can_edit_email_delete_and_restore_user(session_factory):
    with session_factory.begin() as session:
        admin = repo.create_user(session, "Admin", "admin-users411@example.com", "1234", role="admin", roles=["admin"])
        user = repo.create_user(session, "Info", "info411@example.com", "1", role="reporter", roles=["reporter"], actor_id=admin.id)
        repo.update_user(session, user.id, actor_id=admin.id, full_name="Informador Uno", email="nuevo411@example.com", roles=["reporter", "scout"], role="reporter")
        assert user.full_name == "Informador Uno"
        assert user.email == "nuevo411@example.com"
        assert set(repo.get_user_roles(session, user.id)) == {"reporter", "scout"}

        repo.delete_user(session, user.id, admin.id)
        assert user.deleted_at is not None
        assert user.active is False
        assert repo.authenticate(session, "nuevo411@example.com", "1") is None
        assert user not in repo.list_users(session)
        assert user in repo.list_users(session, include_deleted=True)

        repo.restore_user(session, user.id, admin.id, password="22")
        assert user.deleted_at is None
        assert user.active is True
        assert verify_password("22", user.password_hash)


def test_admin_cannot_delete_self(session_factory):
    with session_factory.begin() as session:
        admin = repo.create_user(session, "Admin", "admin-self411@example.com", "1", role="admin", roles=["admin"])
        with pytest.raises(ValueError):
            repo.delete_user(session, admin.id, admin.id)


def test_only_director_assigns_and_only_explicit_scout_receives(session_factory):
    with session_factory.begin() as session:
        admin = repo.create_user(
            session, "Admin", "admin-flow410@example.com", "1",
            role="admin", roles=["admin"], must_change_password=False,
        )
        director = repo.create_user(
            session, "DD", "dd410@example.com", "1",
            role="director", roles=["director"], actor_id=admin.id, must_change_password=False,
        )
        scout = repo.create_user(
            session, "Scout", "scout-flow410@example.com", "1",
            role="scout", roles=["scout"], actor_id=admin.id, must_change_password=False,
        )
        season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
        comp = repo.create_competition(session, "Liga 4.1", actor_id=admin.id)
        a = repo.create_team(session, "Equipo A", actor_id=admin.id)
        b = repo.create_team(session, "Equipo B", actor_id=admin.id)
        match = repo.create_match(
            session, season_id=season.id, competition_id=comp.id, round_name="J1",
            match_date=date(2026, 9, 20), kickoff_at=datetime(2026, 9, 20, 17, 0),
            schedule_status="confirmed", home_team_id=a.id, away_team_id=b.id,
            created_by=admin.id, status="scheduled",
        )

        with pytest.raises(PermissionError):
            planning_repo.create_mission(
                session, match_id=match.id, mission_type="spontaneous", title="Visionar",
                assigned_to=scout.id, requested_by=admin.id,
            )

        mission = planning_repo.create_mission(
            session, match_id=match.id, mission_type="spontaneous", title="Visionar",
            assigned_to=scout.id, requested_by=director.id,
        )
        assert mission.assigned_to == scout.id
        assert mission.requested_by == director.id

        with pytest.raises(ValueError):
            planning_repo.create_mission(
                session, match_id=match.id, mission_type="spontaneous", title="No válido",
                assigned_to=admin.id, requested_by=director.id,
            )


def test_jornada_uses_automatic_scout_depth_and_dd_assignment():
    body = (ROOT / "views/jornada.py").read_text(encoding="utf-8")
    assert "Dirección Deportiva · asignar seguimiento" in body
    assert "Asignar trabajo de scouting" in body
    assert "Scout · registrar lo observado" in body
    assert "varios = apuntes rápidos; uno = observación individual" in body
    assert "dossier 360 se construye automáticamente" in body
    assert "Tipo de seguimiento" not in body
    assert "Dossier completo" not in body


def test_admin_user_screen_has_full_crud_and_optional_password_copy():
    body = (ROOT / "views/admin.py").read_text(encoding="utf-8")
    for token in ["Listado", "Añadir", "Editar / eliminar", "Eliminados", "Eliminar usuario", "Restaurar usuario"]:
        assert token in body
    assert "Cambio obligatorio" not in body
    assert "obligar cambio" not in body
    assert "Puede mantener esa contraseña indefinidamente" in body

    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'if user.get("must_change_password")' not in app
    assert "Cambiar contraseña" in app
    assert "Cambiarla es opcional" in app
