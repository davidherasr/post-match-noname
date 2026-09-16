from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from core.permissions import can_admin, can_direct, can_scout, can_track_players, navigation_for
from core.security import verify_password
from repositories import planning as planning_repo
from repositories import scouting as repo

ROOT = Path(__file__).resolve().parents[1]


def _user_dict(*roles: str, track: bool = False) -> dict:
    return {"id": 1, "role": roles[0] if roles else "reporter", "roles": list(roles), "can_track_players": track}


def test_release_411_contract_and_user_lifecycle_head():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.4"
    assert 'APP_VERSION = "4.4"' in (ROOT / "core/config.py").read_text(encoding="utf-8")
    assert 'REPORTS_PAGE_API_VERSION = "4.4"' in (ROOT / "views/reports.py").read_text(encoding="utf-8")
    migration = ROOT / "alembic/versions/0012_sporting_reading_4_2.py"
    assert migration.exists()
    assert 'down_revision = "0011_user_lifecycle_4_1_1"' in migration.read_text(encoding="utf-8")


def test_roles_are_orthogonal_and_tracking_is_capability():
    admin = _user_dict("admin")
    director = _user_dict("director")
    reporter = _user_dict("reporter")
    tracker = _user_dict("reporter", track=True)
    multi = _user_dict("admin", "director", "reporter", track=True)

    assert can_admin(admin)
    assert not can_direct(admin)
    assert not can_track_players(admin)
    assert "Administración" in navigation_for(admin)
    assert "Dirección Deportiva" not in navigation_for(admin)
    assert can_direct(director)
    assert "Dirección Deportiva" in navigation_for(director)
    assert not can_track_players(reporter)
    assert can_track_players(tracker) and can_scout(tracker)
    assert can_admin(multi) and can_direct(multi) and can_track_players(multi)

def test_simple_passwords_are_valid_and_never_force_change(session_factory):
    with session_factory.begin() as session:
        admin = repo.create_user(
            session, "Admin", "admin411@example.com", "1",
            role="admin", roles=["admin"], must_change_password=False,
        )
        user = repo.create_user(
            session, "Informador", "info411@example.com", "1234",
            role="reporter", roles=["reporter"], actor_id=admin.id, must_change_password=True, can_track_players=True,
        )
        assert user.must_change_password is False
        assert verify_password("1234", user.password_hash)
        assert repo.authenticate(session, "info411@example.com", "1234") is not None

        repo.update_user(session, user.id, password="x", actor_id=admin.id, force_password_change=True)
        assert user.must_change_password is False
        assert verify_password("x", user.password_hash)


def test_admin_can_edit_email_delete_and_restore_user(session_factory):
    with session_factory.begin() as session:
        admin = repo.create_user(session, "Admin", "admin-users411@example.com", "1234", role="admin", roles=["admin"])
        user = repo.create_user(session, "Info", "info411@example.com", "1", role="reporter", roles=["reporter"], actor_id=admin.id)
        repo.update_user(session, user.id, actor_id=admin.id, full_name="Informador Uno", email="nuevo411@example.com", roles=["reporter", "director"], role="director")
        assert user.full_name == "Informador Uno"
        assert user.email == "nuevo411@example.com"
        assert set(repo.get_user_roles(session, user.id)) == {"reporter", "director"}

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


def test_tracking_permission_is_independent_from_roles(session_factory):
    with session_factory.begin() as session:
        admin = repo.create_user(session, "Admin", "admin-flow420@example.com", "1", role="admin", roles=["admin"])
        reporter = repo.create_user(session, "Info", "info-flow420@example.com", "1", role="reporter", roles=["reporter"], actor_id=admin.id)
        tracker = repo.create_user(session, "David", "track-flow420@example.com", "1", role="reporter", roles=["reporter"], actor_id=admin.id, can_track_players=True)
        assert reporter.can_track_players is False
        assert tracker.can_track_players is True
        assert "scout" not in repo.get_user_roles(session, tracker.id)

def test_jornada_separates_own_postmatch_neutral_reading_and_tracking():
    body = (ROOT / "views/jornada.py").read_text(encoding="utf-8")
    assert "Estado del postpartido" in body
    assert "Estado de la lectura" in body
    assert "Dirección Deportiva · lectura conjunta" in body
    assert "Tu lectura del partido" in body
    assert "Seguimiento individual" in body
    assert "Iniciar seguimiento" in body
    assert "Dirección Deportiva · asignar seguimiento" not in body
    assert "Asignar trabajo de scouting" not in body
    assert "Scout · registrar lo observado" not in body

def test_admin_user_screen_has_full_crud_and_optional_password_copy():
    body = (ROOT / "views/admin.py").read_text(encoding="utf-8")
    for token in ["Listado", "Añadir", "Editar / eliminar", "Eliminados", "Eliminar usuario", "Restaurar usuario"]:
        assert token in body
    assert "Cambio obligatorio" not in body
    assert "obligar cambio" not in body
    assert "Nueva contraseña (opcional)" in body

    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'if user.get("must_change_password")' not in app
    assert "Cambiar contraseña" in app
    assert "Cambiarla es opcional" in app


def test_admin_does_not_expose_primary_role_selector():
    body = (ROOT / "views/admin.py").read_text(encoding="utf-8")
    assert 'selectbox("Rol principal"' not in body
    assert '"Rol principal":' not in body
    assert "no existe un rol principal" in body


def test_compatibility_role_is_automatic_and_permissions_stay_multirole():
    assert repo.compatibility_role_for(["reporter"]) == "reporter"
    assert repo.compatibility_role_for(["reporter", "scout"]) == "reporter"
    assert repo.compatibility_role_for(["reporter", "director"]) == "director"
    assert repo.compatibility_role_for(["scout", "director"]) == "director"
    assert repo.compatibility_role_for(["reporter", "admin"]) == "admin"
