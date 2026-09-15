from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Sequence

from sqlalchemy import and_, case, delete, desc, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from core.config import settings
from core.security import hash_password, verify_password
from core.utils import json_dumps, normalize_name
from models.entities import (
    AppSetting, AuditLog, Competition, ConsolidatedPlayerEvaluation, ConsolidatedReport, Document, FollowUp, FollowUpHistory, LoginAttempt,
    LeaguePlayerProfile, Match, Participation, Player, PlayerAlias, PlayerEvaluation, PlayerMergeLog, PostMatchDraft, Report, ReportAssignment,
    ReportVersion, ScoutingList, ScoutingListItem, ScoutedPlayerProfile, ScoutReview, Season, Team, TeamRoster, User, UserRole,
)
from repositories.common import UTC_NOW, FINAL_REPORT_STATUSES, LOCKED_REPORT_STATUSES, _snapshot, audit

ROLE_COMPATIBILITY_PRIORITY = ("admin", "director", "reporter")


def compatibility_role_for(roles: Sequence[str] | None, fallback: str = "reporter") -> str:
    """Choose the legacy ``users.role`` value without exposing a primary-role concept.

    Real authorization is based on ``UserRole``. ``users.role`` is retained only for
    backwards compatibility with old screens/exports, so the choice must never remove
    or add capabilities. A deterministic precedence avoids accidental ``reporter``
    classification for a multi-role sporting user.
    """
    clean = list(dict.fromkeys(str(r) for r in (roles or []) if str(r)))
    for candidate in ROLE_COMPATIBILITY_PRIORITY:
        if candidate in clean:
            return candidate
    if clean:
        return clean[0]
    return fallback or "reporter"


def count_users(session: Session) -> int:
    return int(session.scalar(select(func.count(User.id)).where(User.deleted_at.is_(None))) or 0)


def create_user(
    session: Session,
    full_name: str,
    email: str,
    password: str,
    role: str = "reporter",
    active: bool = True,
    actor_id: int | None = None,
    must_change_password: bool = False,
    roles: Sequence[str] | None = None,
    can_track_players: bool = False,
) -> User:
    if actor_id is not None:
        assert_role(session, actor_id, "admin")
    email = email.strip().lower()
    if not full_name.strip():
        raise ValueError("El nombre no puede estar vacío.")
    if not email:
        raise ValueError("El correo no puede estar vacío.")
    existing = session.scalar(select(User).where(User.email == email))
    if existing:
        if existing.deleted_at is not None:
            raise ValueError("Ese correo pertenece a un usuario eliminado. Restáuralo desde la pestaña Eliminados.")
        raise ValueError("Ya existe un usuario con ese correo.")
    user = User(
        full_name=full_name.strip(),
        email=email,
        password_hash=hash_password(password),
        role=role,
        active=active,
        must_change_password=False,
        deleted_at=None,
        can_track_players=bool(can_track_players),
    )
    session.add(user)
    session.flush()
    role_values = list(dict.fromkeys([role] + list(roles or [])))
    for role_value in role_values:
        session.add(UserRole(user_id=user.id, role=role_value))
    session.flush()
    audit(session, actor_id, "create_user", "user", user.id, email, after={**_snapshot(user, ["full_name", "email", "role", "active"]), "roles": role_values})
    return user

def get_user_roles(session: Session, user_id: int) -> list[str]:
    user = session.get(User, int(user_id))
    if not user:
        return []
    rows = list(session.scalars(select(UserRole.role).where(UserRole.user_id == int(user_id))).all())
    values = list(dict.fromkeys([user.role] + rows))
    return [r for r in values if r]


def user_has_role(session: Session, user_id: int, *roles: str) -> bool:
    if not roles:
        return True
    current = set(get_user_roles(session, int(user_id)))
    return bool(current.intersection(set(roles)))


def set_user_roles(session: Session, user_id: int, roles: Sequence[str], actor_id: int | None = None, primary_role: str | None = None) -> User:
    if actor_id is not None:
        assert_role(session, actor_id, "admin")
    user = session.get(User, int(user_id))
    if not user:
        raise ValueError("Usuario no encontrado.")
    clean = list(dict.fromkeys([str(r) for r in roles if str(r)]))
    if not clean:
        clean = [primary_role or user.role or "reporter"]
    primary = primary_role if primary_role in clean else clean[0]
    session.execute(delete(UserRole).where(UserRole.user_id == int(user_id)))
    for value in clean:
        session.add(UserRole(user_id=int(user_id), role=value))
    user.role = primary
    user.session_revision = (user.session_revision or 0) + 1
    audit(session, actor_id, "set_user_roles", "user", user.id, after={"primary": primary, "roles": clean})
    return user

def authenticate(session: Session, email: str, password: str) -> User | None:
    email = email.strip().lower()
    now = UTC_NOW()
    user = session.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user and user.locked_until and user.locked_until > now:
        session.add(LoginAttempt(email=email, user_id=user.id, success=False, detail="locked"))
        audit(session, user.id, "login_blocked", "user", user.id, "Cuenta bloqueada temporalmente")
        return None
    success = bool(user and user.active and verify_password(password, user.password_hash))
    session.add(LoginAttempt(email=email, user_id=user.id if user else None, success=success))
    if not success:
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_max_attempts:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                user.failed_login_count = 0
            audit(session, user.id, "login_failed", "user", user.id)
        return None
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    # 4.1.1: old provisional-password flags never block access anymore.
    if user.must_change_password:
        user.must_change_password = False
    session.flush()
    audit(session, user.id, "login_success", "user", user.id)
    return user


def get_user(session: Session, user_id: int) -> User | None:
    user = session.get(User, user_id)
    if not user or user.deleted_at is not None:
        return None
    return user


def get_user_including_deleted(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def list_users(session: Session, active_only: bool = False, include_deleted: bool = False) -> list[User]:
    stmt = select(User)
    if not include_deleted:
        stmt = stmt.where(User.deleted_at.is_(None))
    if active_only:
        stmt = stmt.where(User.active.is_(True))
    return list(session.scalars(stmt.order_by(User.full_name)).all())

def update_user(
    session: Session,
    user_id: int,
    role: str | None = None,
    active: bool | None = None,
    password: str | None = None,
    actor_id: int | None = None,
    full_name: str | None = None,
    email: str | None = None,
    roles: Sequence[str] | None = None,
    force_password_change: bool = False,
    can_track_players: bool | None = None,
) -> User:
    if actor_id is not None:
        assert_role(session, actor_id, "admin")
    user = session.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise ValueError("Usuario no encontrado.")
    before = _snapshot(user, ["full_name", "email", "role", "active", "session_revision", "must_change_password", "can_track_players"])
    current_roles = set(get_user_roles(session, user.id))
    requested_roles = set(str(r) for r in roles if str(r)) if roles is not None else current_roles
    requested_active = user.active if active is None else bool(active)
    if actor_id is not None and int(actor_id) == int(user_id) and not requested_active:
        raise ValueError("No puedes desactivar tu propia cuenta durante la sesión.")
    if "admin" in current_roles and user.active and ("admin" not in requested_roles or not requested_active):
        if len(_active_admin_ids(session)) <= 1:
            raise ValueError("Debe quedar al menos un administrador activo.")
    if role is not None:
        user.role = role
    if active is not None:
        user.active = active
    if full_name is not None:
        if not full_name.strip():
            raise ValueError("El nombre no puede estar vacío.")
        user.full_name = full_name.strip()
    if email is not None:
        clean_email = email.strip().lower()
        if not clean_email:
            raise ValueError("El correo no puede estar vacío.")
        duplicate = session.scalar(select(User).where(User.email == clean_email, User.id != user.id))
        if duplicate:
            raise ValueError("Ya existe otro usuario con ese correo.")
        user.email = clean_email
    if password is not None and password != "":
        user.password_hash = hash_password(password)
    if can_track_players is not None:
        user.can_track_players = bool(can_track_players)
    # 4.1.1: changing a password is always optional; no forced-change state.
    user.must_change_password = False
    if roles is not None:
        clean = list(dict.fromkeys([str(r) for r in roles if str(r)])) or [user.role]
        primary = role if role in clean else (user.role if user.role in clean else clean[0])
        session.execute(delete(UserRole).where(UserRole.user_id == int(user_id)))
        for value in clean:
            session.add(UserRole(user_id=int(user_id), role=value))
        user.role = primary
    user.session_revision = (user.session_revision or 0) + 1
    audit(session, actor_id, "update_user", "user", user.id, before=before, after=_snapshot(user, before.keys()))
    return user


def change_own_password(session: Session, user_id: int, current_password: str, new_password: str) -> User:
    user = session.get(User, user_id)
    if not user or user.deleted_at is not None or not verify_password(current_password, user.password_hash):
        raise ValueError("La contraseña actual no es correcta.")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.session_revision = (user.session_revision or 0) + 1
    audit(session, user_id, "change_password", "user", user_id)
    return user


def _active_admin_ids(session: Session) -> list[int]:
    ids: list[int] = []
    for candidate in list_users(session, active_only=True):
        if "admin" in get_user_roles(session, candidate.id):
            ids.append(candidate.id)
    return ids


def delete_user(session: Session, user_id: int, actor_id: int) -> User:
    """Soft-delete an account while preserving sporting/audit history."""
    assert_role(session, actor_id, "admin")
    if int(user_id) == int(actor_id):
        raise ValueError("No puedes eliminar tu propio usuario durante la sesión.")
    user = session.get(User, int(user_id))
    if not user or user.deleted_at is not None:
        raise ValueError("Usuario no encontrado.")
    if user.active and "admin" in get_user_roles(session, user.id):
        admins = _active_admin_ids(session)
        if len(admins) <= 1:
            raise ValueError("No puedes eliminar el último administrador activo.")
    before = _snapshot(user, ["full_name", "email", "role", "active", "session_revision"])
    user.active = False
    user.must_change_password = False
    user.locked_until = None
    user.deleted_at = UTC_NOW()
    user.session_revision = (user.session_revision or 0) + 1
    audit(session, actor_id, "delete_user", "user", user.id, before=before, after={"deleted_at": user.deleted_at, "active": False})
    return user


def restore_user(session: Session, user_id: int, actor_id: int, password: str | None = None) -> User:
    assert_role(session, actor_id, "admin")
    user = session.get(User, int(user_id))
    if not user or user.deleted_at is None:
        raise ValueError("Usuario eliminado no encontrado.")
    user.deleted_at = None
    user.active = True
    user.must_change_password = False
    user.failed_login_count = 0
    user.locked_until = None
    if password is not None and password != "":
        user.password_hash = hash_password(password)
    user.session_revision = (user.session_revision or 0) + 1
    audit(session, actor_id, "restore_user", "user", user.id, after={"active": True})
    return user

def assert_role(session: Session, actor_id: int, *roles: str) -> User:
    actor = session.get(User, actor_id)
    if not actor or not actor.active or actor.deleted_at is not None:
        raise PermissionError("Sesión no válida o usuario desactivado.")
    if roles and not user_has_role(session, actor_id, *roles):
        raise PermissionError("No tienes permisos para realizar esta acción.")
    return actor


def get_setting(session: Session, key: str, default: str | None = None) -> str | None:
    item = session.scalar(select(AppSetting).where(AppSetting.key == key))
    return item.value if item else default


def set_setting(session: Session, key: str, value: str | None, actor_id: int | None = None) -> None:
    item = session.scalar(select(AppSetting).where(AppSetting.key == key))
    before = item.value if item else None
    if not item:
        item = AppSetting(key=key, value=value)
        session.add(item)
    else:
        item.value = value
    audit(session, actor_id, "set_setting", "app_setting", item.id, key, before=before, after=value)


def get_all_settings(session: Session) -> dict[str, str | None]:
    return {x.key: x.value for x in session.scalars(select(AppSetting)).all()}


def list_audit_logs(session: Session, limit: int = 100, action: str | None = None) -> list[AuditLog]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return list(session.scalars(stmt.order_by(desc(AuditLog.created_at)).limit(limit)).all())
