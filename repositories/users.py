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

def count_users(session: Session) -> int:
    return int(session.scalar(select(func.count(User.id))) or 0)


def create_user(
    session: Session,
    full_name: str,
    email: str,
    password: str,
    role: str = "reporter",
    active: bool = True,
    actor_id: int | None = None,
    must_change_password: bool = True,
    roles: Sequence[str] | None = None,
) -> User:
    email = email.strip().lower()
    existing = session.scalar(select(User).where(User.email == email))
    if existing:
        raise ValueError("Ya existe un usuario con ese correo.")
    user = User(
        full_name=full_name.strip(),
        email=email,
        password_hash=hash_password(password),
        role=role,
        active=active,
        must_change_password=must_change_password,
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
    user = session.scalar(select(User).where(User.email == email))
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
    session.flush()
    audit(session, user.id, "login_success", "user", user.id)
    return user


def get_user(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def list_users(session: Session, active_only: bool = False) -> list[User]:
    stmt = select(User)
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
    roles: Sequence[str] | None = None,
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise ValueError("Usuario no encontrado.")
    before = _snapshot(user, ["full_name", "role", "active", "session_revision", "must_change_password"])
    if role is not None:
        user.role = role
    if active is not None:
        user.active = active
    if full_name is not None and full_name.strip():
        user.full_name = full_name.strip()
    if password:
        user.password_hash = hash_password(password)
        user.must_change_password = True
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
    if not user or not verify_password(current_password, user.password_hash):
        raise ValueError("La contraseña actual no es correcta.")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.session_revision = (user.session_revision or 0) + 1
    audit(session, user_id, "change_password", "user", user_id)
    return user


def assert_role(session: Session, actor_id: int, *roles: str) -> User:
    actor = session.get(User, actor_id)
    if not actor or not actor.active:
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
