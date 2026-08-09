from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Sequence

from sqlalchemy import and_, case, delete, desc, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from core.config import settings
from core.security import hash_password, verify_password
from core.utils import json_dumps, normalize_name
from models.entities import (
    AppSetting,
    AuditLog,
    Competition,
    ConsolidatedPlayerEvaluation,
    ConsolidatedReport,
    Document,
    FollowUp,
    FollowUpHistory,
    LoginAttempt,
    Match,
    Participation,
    Player,
    PlayerAlias,
    PlayerEvaluation,
    PlayerMergeLog,
    Report,
    ReportAssignment,
    ReportVersion,
    Season,
    Team,
    TeamRoster,
    User,
)

UTC_NOW = lambda: datetime.now(timezone.utc).replace(tzinfo=None)
FINAL_REPORT_STATUSES = {"approved", "final"}
LOCKED_REPORT_STATUSES = {"submitted", "approved", "final"}


def _snapshot(obj, fields: Sequence[str]) -> dict:
    return {field: getattr(obj, field, None) for field in fields}


def audit(
    session: Session,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    detail: str | None = None,
    before: object | None = None,
    after: object | None = None,
) -> None:
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
            before_json=json_dumps(before) if before is not None else None,
            after_json=json_dumps(after) if after is not None else None,
        )
    )


# ---------------------------------------------------------------------------
# Users, authentication and authorization
# ---------------------------------------------------------------------------

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
    audit(session, actor_id, "create_user", "user", user.id, email, after=_snapshot(user, ["full_name", "email", "role", "active"]))
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
    if roles and actor.role not in roles:
        raise PermissionError("No tienes permisos para realizar esta acción.")
    return actor


def _assert_report_owner_or_privileged(session: Session, report: Report, actor_id: int) -> User:
    actor = assert_role(session, actor_id)
    if actor.id != report.reporter_id and actor.role not in {"admin", "director"}:
        raise PermissionError("No puedes modificar un informe de otro usuario.")
    return actor


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Catalogue and player identity
# ---------------------------------------------------------------------------

def list_seasons(session: Session, active_only: bool = False) -> list[Season]:
    stmt = select(Season)
    if active_only:
        stmt = stmt.where(Season.active.is_(True))
    return list(session.scalars(stmt.order_by(desc(Season.name))).all())


def create_season(session: Session, name: str, start_date: date | None = None, end_date: date | None = None, actor_id: int | None = None) -> Season:
    existing = session.scalar(select(Season).where(Season.name == name.strip()))
    if existing:
        return existing
    item = Season(name=name.strip(), start_date=start_date, end_date=end_date)
    session.add(item)
    session.flush()
    audit(session, actor_id, "create_season", "season", item.id, after=_snapshot(item, ["name", "start_date", "end_date"]))
    return item


def update_season(session: Session, season_id: int, actor_id: int, **values) -> Season:
    assert_role(session, actor_id, "admin")
    item = session.get(Season, season_id)
    if not item:
        raise ValueError("Temporada no encontrada.")
    before = _snapshot(item, ["name", "start_date", "end_date", "active"])
    for key in before:
        if key in values and values[key] is not None:
            setattr(item, key, values[key])
    audit(session, actor_id, "update_season", "season", item.id, before=before, after=_snapshot(item, before.keys()))
    return item


def list_competitions(session: Session, active_only: bool = False) -> list[Competition]:
    stmt = select(Competition)
    if active_only:
        stmt = stmt.where(Competition.active.is_(True))
    return list(session.scalars(stmt.order_by(Competition.name)).all())


def create_competition(session: Session, name: str, country: str | None = None, actor_id: int | None = None) -> Competition:
    country_clean = country.strip() if country else None
    existing = session.scalar(select(Competition).where(and_(Competition.name == name.strip(), Competition.country == country_clean)))
    if existing:
        return existing
    item = Competition(name=name.strip(), country=country_clean)
    session.add(item)
    session.flush()
    audit(session, actor_id, "create_competition", "competition", item.id, after=_snapshot(item, ["name", "country"]))
    return item


def update_competition(session: Session, competition_id: int, actor_id: int, **values) -> Competition:
    assert_role(session, actor_id, "admin")
    item = session.get(Competition, competition_id)
    if not item:
        raise ValueError("Competición no encontrada.")
    before = _snapshot(item, ["name", "country", "active"])
    for key in before:
        if key in values and values[key] is not None:
            setattr(item, key, values[key])
    audit(session, actor_id, "update_competition", "competition", item.id, before=before, after=_snapshot(item, before.keys()))
    return item


def list_teams(session: Session, active_only: bool = False) -> list[Team]:
    stmt = select(Team)
    if active_only:
        stmt = stmt.where(Team.active.is_(True))
    return list(session.scalars(stmt.order_by(Team.name)).all())


def create_team(session: Session, name: str, short_name: str | None = None, country: str | None = None, is_own_team: bool = False, actor_id: int | None = None) -> Team:
    existing = session.scalar(select(Team).where(Team.name == name.strip()))
    if existing:
        if is_own_team:
            set_own_team(session, existing.id, actor_id)
        return existing
    if is_own_team:
        for team in session.scalars(select(Team).where(Team.is_own_team.is_(True))).all():
            team.is_own_team = False
    item = Team(name=name.strip(), short_name=short_name.strip() if short_name else None, country=country.strip() if country else None, is_own_team=is_own_team)
    session.add(item)
    session.flush()
    if is_own_team:
        set_setting(session, "own_team_id", str(item.id), actor_id)
    audit(session, actor_id, "create_team", "team", item.id, after=_snapshot(item, ["name", "short_name", "country", "is_own_team"]))
    return item


def update_team(session: Session, team_id: int, actor_id: int, **values) -> Team:
    assert_role(session, actor_id, "admin")
    item = session.get(Team, team_id)
    if not item:
        raise ValueError("Equipo no encontrado.")
    before = _snapshot(item, ["name", "short_name", "country", "active", "is_own_team", "logo_mime"])
    for key in ["name", "short_name", "country", "active", "logo_b64", "logo_mime"]:
        if key in values:
            setattr(item, key, values[key])
    if values.get("is_own_team"):
        set_own_team(session, item.id, actor_id)
    audit(session, actor_id, "update_team", "team", item.id, before=before, after=_snapshot(item, before.keys()))
    return item


def set_own_team(session: Session, team_id: int, actor_id: int | None = None) -> None:
    for team in session.scalars(select(Team)).all():
        team.is_own_team = team.id == team_id
    set_setting(session, "own_team_id", str(team_id), actor_id)


def add_player_alias(session: Session, player_id: int, alias: str, actor_id: int | None = None) -> PlayerAlias:
    normalized = normalize_name(alias)
    if not normalized:
        raise ValueError("El alias no puede estar vacío.")
    existing = session.scalar(select(PlayerAlias).where(PlayerAlias.normalized_alias == normalized))
    if existing:
        if existing.player_id != player_id:
            raise ValueError("Ese alias ya está asociado a otro jugador.")
        return existing
    item = PlayerAlias(player_id=player_id, alias=alias.strip(), normalized_alias=normalized)
    session.add(item)
    session.flush()
    audit(session, actor_id, "add_player_alias", "player", player_id, alias)
    return item


def find_player_candidates(session: Session, full_name: str, date_of_birth: date | None = None, limit: int = 10) -> list[Player]:
    normalized = normalize_name(full_name)
    alias_ids = select(PlayerAlias.player_id).where(PlayerAlias.normalized_alias == normalized)
    stmt = select(Player).where(or_(Player.normalized_name == normalized, Player.id.in_(alias_ids)))
    if date_of_birth:
        stmt = stmt.where(or_(Player.date_of_birth == date_of_birth, Player.date_of_birth.is_(None)))
    return list(session.scalars(stmt.order_by(Player.active.desc(), Player.id).limit(limit)).all())


def find_or_create_player(
    session: Session,
    full_name: str,
    date_of_birth: date | None = None,
    primary_position: str | None = None,
    nationality: str | None = None,
    display_name: str | None = None,
    actor_id: int | None = None,
) -> Player:
    normalized = normalize_name(full_name)
    if not normalized:
        raise ValueError("Nombre de jugador no válido.")
    candidates = find_player_candidates(session, full_name, date_of_birth)
    exact = [p for p in candidates if p.date_of_birth == date_of_birth] if date_of_birth else [p for p in candidates if p.date_of_birth is None]
    player = exact[0] if exact else (candidates[0] if len(candidates) == 1 and not date_of_birth else None)
    if player:
        if player.merged_into_id:
            player = session.get(Player, player.merged_into_id) or player
        if primary_position and not player.primary_position:
            player.primary_position = primary_position
        if nationality and not player.nationality:
            player.nationality = nationality
        return player
    player = Player(
        full_name=full_name.strip(),
        normalized_name=normalized,
        display_name=display_name.strip() if display_name else None,
        date_of_birth=date_of_birth,
        primary_position=primary_position,
        nationality=nationality,
    )
    session.add(player)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("Posible jugador duplicado. Revisa la herramienta de duplicados.") from exc
    audit(session, actor_id, "create_player", "player", player.id, after=_snapshot(player, ["full_name", "date_of_birth", "primary_position", "nationality"]))
    return player


def update_player(session: Session, player_id: int, actor_id: int, **values) -> Player:
    assert_role(session, actor_id, "admin", "director")
    player = session.get(Player, player_id)
    if not player:
        raise ValueError("Jugador no encontrado.")
    before = _snapshot(player, ["full_name", "display_name", "date_of_birth", "nationality", "preferred_foot", "primary_position", "active"])
    for key in ["full_name", "display_name", "date_of_birth", "nationality", "preferred_foot", "primary_position", "active", "photo_b64", "photo_mime"]:
        if key in values:
            setattr(player, key, values[key])
    if "full_name" in values:
        player.normalized_name = normalize_name(player.full_name)
    audit(session, actor_id, "update_player", "player", player.id, before=before, after=_snapshot(player, before.keys()))
    return player


def list_players(session: Session, search: str | None = None, position: str | None = None, active_only: bool = True, limit: int | None = None, offset: int = 0) -> list[Player]:
    stmt = select(Player).where(Player.merged_into_id.is_(None))
    if active_only:
        stmt = stmt.where(Player.active.is_(True))
    if search:
        needle = f"%{normalize_name(search)}%"
        alias_ids = select(PlayerAlias.player_id).where(PlayerAlias.normalized_alias.like(needle))
        stmt = stmt.where(or_(Player.normalized_name.like(needle), Player.id.in_(alias_ids)))
    if position and position != "Todas":
        stmt = stmt.where(Player.primary_position == position)
    stmt = stmt.order_by(Player.full_name).offset(offset)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt).all())


def duplicate_player_groups(session: Session, limit: int = 100) -> list[dict]:
    players = list(session.scalars(select(Player).where(Player.merged_into_id.is_(None)).order_by(Player.normalized_name, Player.id)).all())
    groups: dict[str, list[Player]] = defaultdict(list)
    for p in players:
        groups[p.normalized_name].append(p)
    result = []
    for key, items in groups.items():
        if len(items) > 1:
            result.append({"normalized_name": key, "players": items})
    return result[:limit]


def merge_players(session: Session, source_player_id: int, target_player_id: int, actor_id: int) -> Player:
    assert_role(session, actor_id, "admin")
    if source_player_id == target_player_id:
        raise ValueError("Selecciona dos jugadores distintos.")
    source = session.get(Player, source_player_id)
    target = session.get(Player, target_player_id)
    if not source or not target:
        raise ValueError("Jugador no encontrado.")
    # Resolve collisions conservatively before bulk updates.
    for roster in list(session.scalars(select(TeamRoster).where(TeamRoster.player_id == source.id)).all()):
        existing = session.scalar(select(TeamRoster).where(and_(TeamRoster.team_id == roster.team_id, TeamRoster.season_id == roster.season_id, TeamRoster.player_id == target.id)))
        if existing:
            existing.active = existing.active or roster.active
            if existing.shirt_number is None:
                existing.shirt_number = roster.shirt_number
            session.delete(roster)
        else:
            roster.player_id = target.id
    for part in list(session.scalars(select(Participation).where(Participation.player_id == source.id)).all()):
        existing = session.scalar(select(Participation).where(and_(Participation.match_id == part.match_id, Participation.player_id == target.id)))
        if existing:
            session.delete(part)
        else:
            part.player_id = target.id
    for ev in list(session.scalars(select(PlayerEvaluation).where(PlayerEvaluation.player_id == source.id)).all()):
        existing = session.scalar(select(PlayerEvaluation).where(and_(PlayerEvaluation.report_id == ev.report_id, PlayerEvaluation.player_id == target.id)))
        if existing:
            # Preserve the richer evaluation.
            if existing.general_rating is None and ev.general_rating is not None:
                for field in ["general_rating", "technical_rating", "tactical_rating", "physical_rating", "confidence", "recommendation", "strengths", "short_note", "detailed_note", "standout", "pdf_include"]:
                    setattr(existing, field, getattr(ev, field))
            session.delete(ev)
        else:
            ev.player_id = target.id
    for follow in list(session.scalars(select(FollowUp).where(FollowUp.player_id == source.id)).all()):
        existing = session.scalar(select(FollowUp).where(FollowUp.player_id == target.id))
        if existing:
            existing.note = "\n".join(filter(None, [existing.note, follow.note])) or None
            existing.priority = min(existing.priority, follow.priority)
            session.delete(follow)
        else:
            follow.player_id = target.id
    session.execute(update(Report).where(Report.standout_player_id == source.id).values(standout_player_id=target.id))
    session.execute(update(ConsolidatedPlayerEvaluation).where(ConsolidatedPlayerEvaluation.player_id == source.id).values(player_id=target.id))
    add_player_alias(session, target.id, source.full_name, actor_id)
    source.active = False
    source.merged_into_id = target.id
    session.add(PlayerMergeLog(source_player_id=source.id, target_player_id=target.id, actor_id=actor_id, detail=f"{source.full_name} -> {target.full_name}"))
    audit(session, actor_id, "merge_players", "player", target.id, detail=f"Origen {source.id}")
    return target


def assign_player_to_roster(session: Session, team_id: int, season_id: int, player_id: int, shirt_number: int | None = None, actor_id: int | None = None) -> TeamRoster:
    roster = session.scalar(select(TeamRoster).where(and_(TeamRoster.team_id == team_id, TeamRoster.season_id == season_id, TeamRoster.player_id == player_id)))
    if roster:
        roster.shirt_number = shirt_number
        roster.active = True
        return roster
    roster = TeamRoster(team_id=team_id, season_id=season_id, player_id=player_id, shirt_number=shirt_number)
    session.add(roster)
    session.flush()
    audit(session, actor_id, "assign_roster", "team_roster", roster.id)
    return roster


def update_roster_entry(session: Session, roster_id: int, actor_id: int, *, shirt_number: int | None = None, active: bool | None = None, joined_at: date | None = None, left_at: date | None = None) -> TeamRoster:
    assert_role(session, actor_id, "admin")
    roster = session.get(TeamRoster, roster_id)
    if not roster:
        raise ValueError("Registro de plantilla no encontrado.")
    before = _snapshot(roster, ["shirt_number", "active", "joined_at", "left_at"])
    roster.shirt_number = shirt_number
    if active is not None:
        roster.active = active
    roster.joined_at = joined_at
    roster.left_at = left_at
    audit(session, actor_id, "update_roster", "team_roster", roster.id, before=before, after=_snapshot(roster, before.keys()))
    return roster


def get_roster(session: Session, team_id: int, season_id: int, active_only: bool = True) -> list[TeamRoster]:
    stmt = select(TeamRoster).options(joinedload(TeamRoster.player)).where(and_(TeamRoster.team_id == team_id, TeamRoster.season_id == season_id))
    if active_only:
        stmt = stmt.where(TeamRoster.active.is_(True))
    stmt = stmt.order_by(TeamRoster.shirt_number.nullslast(), TeamRoster.id)
    return list(session.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Matches, lineups and assignments
# ---------------------------------------------------------------------------

def create_match(session: Session, *, season_id: int, competition_id: int, round_name: str, match_date: date, home_team_id: int, away_team_id: int, created_by: int, home_score: int | None = None, away_score: int | None = None, venue: str | None = None, home_formation: str | None = None, away_formation: str | None = None, status: str = "draft", report_due_at: datetime | None = None) -> Match:
    assert_role(session, created_by, "admin")
    if home_team_id == away_team_id:
        raise ValueError("Los equipos local y visitante deben ser diferentes.")
    item = Match(season_id=season_id, competition_id=competition_id, round_name=round_name.strip(), match_date=match_date, home_team_id=home_team_id, away_team_id=away_team_id, home_score=home_score, away_score=away_score, venue=venue, home_formation=home_formation, away_formation=away_formation, status=status, report_due_at=report_due_at, created_by=created_by)
    session.add(item)
    session.flush()
    audit(session, created_by, "create_match", "match", item.id, after=_snapshot(item, ["round_name", "match_date", "home_team_id", "away_team_id", "status"]))
    return item


def update_match(session: Session, match_id: int, actor_id: int | None = None, expected_revision: int | None = None, **values) -> Match:
    if actor_id is not None:
        assert_role(session, actor_id, "admin")
    item = session.get(Match, match_id)
    if not item:
        raise ValueError("Partido no encontrado.")
    if expected_revision is not None and item.revision != expected_revision:
        raise RuntimeError("El partido ha cambiado en otra sesión. Recarga antes de guardar.")
    before = _snapshot(item, ["season_id", "competition_id", "round_name", "match_date", "home_team_id", "away_team_id", "home_score", "away_score", "venue", "home_formation", "away_formation", "status", "report_due_at", "revision"])
    allowed = set(before) - {"revision"}
    for key, value in values.items():
        if key in allowed:
            setattr(item, key, value)
    if item.home_team_id == item.away_team_id:
        raise ValueError("Los equipos deben ser diferentes.")
    item.revision = (item.revision or 0) + 1
    audit(session, actor_id, "update_match", "match", item.id, before=before, after=_snapshot(item, before.keys()))
    return item


def archive_match(session: Session, match_id: int, actor_id: int) -> Match:
    assert_role(session, actor_id, "admin")
    match = session.get(Match, match_id)
    if not match:
        raise ValueError("Partido no encontrado.")
    match.status = "archived"
    match.deleted_at = UTC_NOW()
    match.revision = (match.revision or 0) + 1
    audit(session, actor_id, "archive_match", "match", match.id)
    return match


def list_matches(session: Session, status: str | None = None, limit: int | None = None, season_id: int | None = None, competition_id: int | None = None, include_archived: bool = False, offset: int = 0) -> list[Match]:
    stmt = select(Match).options(joinedload(Match.season), joinedload(Match.competition), joinedload(Match.home_team), joinedload(Match.away_team))
    if not include_archived:
        stmt = stmt.where(Match.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Match.status == status)
    if season_id:
        stmt = stmt.where(Match.season_id == season_id)
    if competition_id:
        stmt = stmt.where(Match.competition_id == competition_id)
    stmt = stmt.order_by(desc(Match.match_date), desc(Match.id)).offset(offset)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt).unique().all())


def get_match(session: Session, match_id: int) -> Match | None:
    return session.scalar(select(Match).options(joinedload(Match.season), joinedload(Match.competition), joinedload(Match.home_team), joinedload(Match.away_team)).where(Match.id == match_id))


def get_participations(session: Session, match_id: int, team_id: int | None = None) -> list[Participation]:
    stmt = select(Participation).options(joinedload(Participation.player), joinedload(Participation.team)).where(Participation.match_id == match_id)
    if team_id:
        stmt = stmt.where(Participation.team_id == team_id)
    stmt = stmt.order_by(Participation.team_id, Participation.starter.desc(), Participation.order_index, Participation.shirt_number.nullslast())
    return list(session.scalars(stmt).unique().all())


def replace_participations(session: Session, match_id: int, team_id: int, rows: Iterable[dict], actor_id: int) -> list[Participation]:
    assert_role(session, actor_id, "admin")
    match = session.get(Match, match_id)
    if not match:
        raise ValueError("Partido no encontrado.")
    locked = int(session.scalar(select(func.count(Report.id)).where(and_(Report.match_id == match_id, Report.status.in_(LOCKED_REPORT_STATUSES)))) or 0)
    if locked:
        raise ValueError("No se puede cambiar la alineación: existen informes entregados o aprobados.")
    selected_rows = [r for r in rows if bool(r.get("selected", True))]
    starters = [r for r in selected_rows if bool(r.get("starter"))]
    if len(starters) > 11:
        raise ValueError("No puede haber más de 11 titulares.")
    player_ids = [int(r["player_id"]) for r in selected_rows]
    if len(player_ids) != len(set(player_ids)):
        raise ValueError("Hay jugadores duplicados en la alineación.")
    for row in selected_rows:
        minute_in = int(row.get("minute_in", 0) or 0)
        minute_out = int(row.get("minute_out", 90) or 90)
        if minute_out < minute_in:
            raise ValueError("La salida no puede ser anterior a la entrada.")
    previous = get_participations(session, match_id, team_id)
    previous_by_player = {p.player_id: p for p in previous}
    result: list[Participation] = []
    for index, row in enumerate(selected_rows):
        pid = int(row["player_id"])
        item = previous_by_player.pop(pid, None)
        if item is None:
            item = Participation(match_id=match_id, team_id=team_id, player_id=pid)
            session.add(item)
        item.shirt_number = int(row["shirt_number"]) if row.get("shirt_number") not in (None, "") else None
        item.starter = bool(row.get("starter"))
        item.position = row.get("position") or None
        item.minute_in = int(row.get("minute_in", 0) or 0)
        item.minute_out = int(row.get("minute_out", 90) or 90)
        item.captain = bool(row.get("captain"))
        item.order_index = index
        item.revision = (item.revision or 0) + 1
        session.flush()
        result.append(item)
        # Rebind draft evaluations after lineup edits.
        session.execute(update(PlayerEvaluation).where(and_(PlayerEvaluation.report_id.in_(select(Report.id).where(and_(Report.match_id == match_id, Report.status.in_({"draft", "returned"})))), PlayerEvaluation.player_id == pid)).values(participation_id=item.id, team_id=team_id, evaluation_scope="rival" if team_id != _own_team_id_for_match(session, match) else "own"))
    removed_ids = [p.player_id for p in previous_by_player.values()]
    if removed_ids:
        draft_report_ids = select(Report.id).where(and_(Report.match_id == match_id, Report.status.in_({"draft", "returned"})))
        session.execute(delete(PlayerEvaluation).where(and_(PlayerEvaluation.report_id.in_(draft_report_ids), PlayerEvaluation.player_id.in_(removed_ids))))
        for item in previous_by_player.values():
            session.delete(item)
    match.revision = (match.revision or 0) + 1
    audit(session, actor_id, "replace_lineup", "match", match_id, detail=f"team={team_id}; rows={len(result)}; removed={len(removed_ids)}")
    return result


def _own_team_id_for_match(session: Session, match: Match) -> int:
    own = session.scalar(select(Team.id).where(Team.is_own_team.is_(True)).limit(1))
    if own in {match.home_team_id, match.away_team_id}:
        return int(own)
    configured = get_setting(session, "own_team_id")
    return int(configured) if configured else match.home_team_id


def assign_reporters(session: Session, match_id: int, user_ids: Sequence[int], actor_id: int, due_at: datetime | None = None, required: bool = True) -> list[ReportAssignment]:
    assert_role(session, actor_id, "admin")
    current = {a.user_id: a for a in session.scalars(select(ReportAssignment).where(ReportAssignment.match_id == match_id)).all()}
    result = []
    for uid in user_ids:
        user = session.get(User, int(uid))
        if not user or not user.active or user.role not in {"reporter", "admin", "director"}:
            continue
        item = current.pop(user.id, None)
        if item is None:
            item = ReportAssignment(match_id=match_id, user_id=user.id, assigned_by=actor_id)
            session.add(item)
        item.due_at = due_at
        item.required = required
        if item.status == "waived":
            item.status = "pending"
        result.append(item)
    for item in current.values():
        if item.status not in {"submitted", "approved"}:
            item.status = "waived"
    audit(session, actor_id, "assign_reporters", "match", match_id, detail=",".join(map(str, user_ids)))
    return result


def list_assignments(session: Session, match_id: int | None = None, user_id: int | None = None) -> list[ReportAssignment]:
    stmt = select(ReportAssignment).options(joinedload(ReportAssignment.match).joinedload(Match.home_team), joinedload(ReportAssignment.match).joinedload(Match.away_team), joinedload(ReportAssignment.user))
    if match_id:
        stmt = stmt.where(ReportAssignment.match_id == match_id)
    if user_id:
        stmt = stmt.where(ReportAssignment.user_id == user_id)
    return list(session.scalars(stmt.order_by(desc(ReportAssignment.created_at))).unique().all())


def assignment_progress(session: Session, match_id: int) -> dict:
    rows = list_assignments(session, match_id=match_id)
    return {"total": len([a for a in rows if a.required]), "approved": len([a for a in rows if a.status == "approved"]), "submitted": len([a for a in rows if a.status == "submitted"]), "pending": len([a for a in rows if a.status in {"pending", "in_progress", "returned"}])}


# ---------------------------------------------------------------------------
# Reports, evaluations, versions and documents
# ---------------------------------------------------------------------------

def report_for_user(session: Session, match_id: int, reporter_id: int) -> Report | None:
    return session.scalar(select(Report).options(joinedload(Report.match), joinedload(Report.reporter), joinedload(Report.own_team), joinedload(Report.rival_team)).where(and_(Report.match_id == match_id, Report.reporter_id == reporter_id)))


def get_or_create_report(session: Session, match_id: int, reporter_id: int, actor_role: str | None = None) -> Report:
    existing = report_for_user(session, match_id, reporter_id)
    if existing:
        return existing
    match = get_match(session, match_id)
    user = session.get(User, reporter_id)
    if not match or not user or not user.active:
        raise ValueError("Partido o usuario no válido.")
    assignments = list(session.scalars(select(ReportAssignment).where(and_(ReportAssignment.match_id == match_id, ReportAssignment.status != "waived"))).all())
    if assignments and reporter_id not in {a.user_id for a in assignments} and actor_role not in {"admin", "director"}:
        raise PermissionError("Este partido no está asignado a tu usuario.")
    own_team_id = _own_team_id_for_match(session, match)
    rival_team_id = match.away_team_id if own_team_id == match.home_team_id else match.home_team_id
    report = Report(match_id=match_id, reporter_id=reporter_id, own_team_id=own_team_id, rival_team_id=rival_team_id)
    session.add(report)
    session.flush()
    assignment = session.scalar(select(ReportAssignment).where(and_(ReportAssignment.match_id == match_id, ReportAssignment.user_id == reporter_id)))
    if assignment:
        assignment.status = "in_progress"
    audit(session, reporter_id, "create_report", "report", report.id)
    return report


def get_report(session: Session, report_id: int) -> Report | None:
    return session.scalar(select(Report).options(joinedload(Report.match).joinedload(Match.home_team), joinedload(Report.match).joinedload(Match.away_team), joinedload(Report.match).joinedload(Match.season), joinedload(Report.match).joinedload(Match.competition), joinedload(Report.reporter), joinedload(Report.reviewer), joinedload(Report.own_team), joinedload(Report.rival_team)).where(Report.id == report_id))


def save_report_summary(session: Session, report_id: int, *, rival_level: str | None, opponent_overview: str | None, own_team_note: str | None, key_takeaways: str | None, standout_player_id: int | None, actor_id: int | None = None, expected_revision: int | None = None) -> Report:
    report = session.get(Report, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    actor_id = actor_id or report.reporter_id
    _assert_report_owner_or_privileged(session, report, actor_id)
    if report.status not in {"draft", "returned"}:
        raise ValueError("El informe está bloqueado.")
    if expected_revision is not None and report.revision != expected_revision:
        raise RuntimeError("El informe se ha modificado en otra pestaña. Recarga antes de guardar.")
    before = _snapshot(report, ["rival_level", "opponent_overview", "own_team_note", "key_takeaways", "standout_player_id", "revision"])
    report.rival_level = rival_level
    report.opponent_overview = opponent_overview
    report.own_team_note = own_team_note
    report.key_takeaways = key_takeaways
    report.standout_player_id = standout_player_id
    report.revision = (report.revision or 0) + 1
    if standout_player_id:
        ev = get_evaluation(session, report_id, standout_player_id)
        if ev:
            ev.standout = True
            ev.pdf_include = True
            ev.revision = (ev.revision or 0) + 1
    audit(session, actor_id, "save_report_summary", "report", report.id, before=before, after=_snapshot(report, before.keys()))
    return report


def get_evaluation(session: Session, report_id: int, player_id: int) -> PlayerEvaluation | None:
    return session.scalar(select(PlayerEvaluation).options(joinedload(PlayerEvaluation.player), joinedload(PlayerEvaluation.participation)).where(and_(PlayerEvaluation.report_id == report_id, PlayerEvaluation.player_id == player_id)))


def upsert_evaluation(session: Session, report_id: int, player_id: int, team_id: int, participation_id: int | None, actor_id: int | None = None, expected_revision: int | None = None, **values) -> PlayerEvaluation:
    report = session.get(Report, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    actor_id = actor_id or report.reporter_id
    _assert_report_owner_or_privileged(session, report, actor_id)
    if report.status not in {"draft", "returned"}:
        raise ValueError("El informe está bloqueado y no puede editarse.")
    scope = "rival" if team_id == report.rival_team_id else "own"
    item = get_evaluation(session, report_id, player_id)
    before = None
    if not item:
        item = PlayerEvaluation(report_id=report_id, player_id=player_id, team_id=team_id, participation_id=participation_id, evaluation_scope=scope)
        session.add(item)
        session.flush()
    else:
        if expected_revision is not None and item.revision != expected_revision:
            raise RuntimeError("La evaluación se ha modificado en otra sesión. Recarga antes de guardar.")
        before = _snapshot(item, ["observation_status", "general_rating", "technical_rating", "tactical_rating", "physical_rating", "confidence", "recommendation", "strengths", "short_note", "detailed_note", "standout", "pdf_include", "revision"])
        item.team_id = team_id
        item.participation_id = participation_id
        item.evaluation_scope = scope
    for key, value in values.items():
        if key == "strengths" and isinstance(value, (list, tuple)):
            value = json.dumps(list(value), ensure_ascii=False)
        if hasattr(item, key):
            setattr(item, key, value)
    if item.observation_status != "evaluated":
        item.general_rating = None
        item.technical_rating = None
        item.tactical_rating = None
        item.physical_rating = None
        item.recommendation = None
        item.standout = False
    item.revision = (item.revision or 0) + 1
    report.revision = (report.revision or 0) + 1
    session.flush()
    audit(session, actor_id, "upsert_evaluation", "player_evaluation", item.id, detail=f"report={report_id}; player={player_id}", before=before, after=_snapshot(item, ["observation_status", "general_rating", "recommendation", "standout", "pdf_include", "revision"]))
    return item


def sync_report_standout(session: Session, report_id: int, actor_id: int) -> Report:
    """Keep the report MVP aligned with the highest-rated standout rival.

    The lightweight editor can mark several players as standout. The report-level
    MVP is derived automatically from the highest score among those players.
    """
    report = session.get(Report, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    _assert_report_owner_or_privileged(session, report, actor_id)
    best = session.scalar(
        select(PlayerEvaluation)
        .where(
            and_(
                PlayerEvaluation.report_id == report_id,
                PlayerEvaluation.evaluation_scope == "rival",
                PlayerEvaluation.team_id == report.rival_team_id,
                PlayerEvaluation.observation_status == "evaluated",
                PlayerEvaluation.general_rating.is_not(None),
                PlayerEvaluation.standout.is_(True),
            )
        )
        .order_by(desc(PlayerEvaluation.general_rating), PlayerEvaluation.id)
        .limit(1)
    )
    report.standout_player_id = best.player_id if best else None
    return report


def bulk_upsert_evaluations(session: Session, report_id: int, rows: Sequence[dict], actor_id: int) -> int:
    report = session.get(Report, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    _assert_report_owner_or_privileged(session, report, actor_id)
    saved = 0
    for row in rows:
        upsert_evaluation(session, report_id, int(row["player_id"]), int(row["team_id"]), row.get("participation_id"), actor_id=actor_id, **{k: v for k, v in row.items() if k not in {"player_id", "team_id", "participation_id"}})
        saved += 1
    return saved


def list_evaluations(session: Session, report_id: int, scope: str | None = None) -> list[PlayerEvaluation]:
    stmt = select(PlayerEvaluation).options(joinedload(PlayerEvaluation.player), joinedload(PlayerEvaluation.team), joinedload(PlayerEvaluation.participation)).where(PlayerEvaluation.report_id == report_id)
    if scope:
        stmt = stmt.where(PlayerEvaluation.evaluation_scope == scope)
    stmt = stmt.order_by(desc(PlayerEvaluation.general_rating), PlayerEvaluation.player_id)
    return list(session.scalars(stmt).unique().all())


def validate_report_for_finalization(session: Session, report_id: int) -> list[str]:
    report = session.get(Report, report_id)
    if not report:
        return ["Informe no encontrado."]
    errors: list[str] = []
    evaluated = int(session.scalar(select(func.count(PlayerEvaluation.id)).where(and_(PlayerEvaluation.report_id == report_id, PlayerEvaluation.evaluation_scope == "rival", PlayerEvaluation.team_id == report.rival_team_id, PlayerEvaluation.observation_status == "evaluated", PlayerEvaluation.general_rating.is_not(None)))) or 0)
    if evaluated < 1:
        errors.append("Evalúa al menos a un jugador rival con nota general.")
    return errors


def _report_snapshot_data(session: Session, report_id: int) -> dict:
    report = get_report(session, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    participations = get_participations(session, report.match_id)
    evaluations = list_evaluations(session, report.id)
    return {
        "report": {k: getattr(report, k) for k in ["id", "match_id", "reporter_id", "own_team_id", "rival_team_id", "status", "rival_level", "opponent_overview", "own_team_note", "key_takeaways", "standout_player_id", "version", "created_at", "updated_at", "submitted_at", "approved_at"]},
        "reporter": {"id": report.reporter.id, "full_name": report.reporter.full_name, "email": report.reporter.email},
        "match": {"id": report.match.id, "round_name": report.match.round_name, "match_date": report.match.match_date, "home_team_id": report.match.home_team_id, "away_team_id": report.match.away_team_id, "home_score": report.match.home_score, "away_score": report.match.away_score, "venue": report.match.venue, "home_formation": report.match.home_formation, "away_formation": report.match.away_formation, "competition": report.match.competition.name, "season": report.match.season.name, "home_team": {"id": report.match.home_team.id, "name": report.match.home_team.name, "short_name": report.match.home_team.short_name, "logo_b64": report.match.home_team.logo_b64, "logo_mime": report.match.home_team.logo_mime}, "away_team": {"id": report.match.away_team.id, "name": report.match.away_team.name, "short_name": report.match.away_team.short_name, "logo_b64": report.match.away_team.logo_b64, "logo_mime": report.match.away_team.logo_mime}},
        "participations": [{"id": p.id, "team_id": p.team_id, "player_id": p.player_id, "player_name": p.player.display_name or p.player.full_name, "shirt_number": p.shirt_number, "starter": p.starter, "position": p.position or p.player.primary_position, "minute_in": p.minute_in, "minute_out": p.minute_out, "captain": p.captain, "photo_b64": p.player.photo_b64, "photo_mime": p.player.photo_mime} for p in participations],
        "evaluations": [{"id": e.id, "player_id": e.player_id, "player_name": e.player.display_name or e.player.full_name, "team_id": e.team_id, "participation_id": e.participation_id, "evaluation_scope": e.evaluation_scope, "observation_status": e.observation_status, "general_rating": e.general_rating, "technical_rating": e.technical_rating, "tactical_rating": e.tactical_rating, "physical_rating": e.physical_rating, "confidence": e.confidence, "recommendation": e.recommendation, "strengths": e.strengths, "short_note": e.short_note, "detailed_note": e.detailed_note, "standout": e.standout, "pdf_include": e.pdf_include} for e in evaluations],
        "settings": get_all_settings(session),
    }


def create_report_version(session: Session, report_id: int, actor_id: int, status: str = "submitted") -> ReportVersion:
    report = session.get(Report, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    existing = session.scalar(select(ReportVersion).where(and_(ReportVersion.report_id == report_id, ReportVersion.version == report.version)))
    if existing:
        return existing
    snapshot = _report_snapshot_data(session, report_id)
    snapshot["report"]["status"] = status
    item = ReportVersion(report_id=report_id, version=report.version, status=status, snapshot_json=json_dumps(snapshot), created_by=actor_id)
    session.add(item)
    session.flush()
    audit(session, actor_id, "create_report_version", "report_version", item.id, detail=f"report={report_id}; v={report.version}")
    return item


def submit_report(session: Session, report_id: int, actor_id: int) -> tuple[Report, ReportVersion]:
    errors = validate_report_for_finalization(session, report_id)
    if errors:
        raise ValueError(" | ".join(errors))
    report = session.get(Report, report_id)
    _assert_report_owner_or_privileged(session, report, actor_id)
    if report.status not in {"draft", "returned"}:
        raise ValueError("El informe ya está entregado o aprobado.")
    require_approval = str(get_setting(session, "require_report_approval", "true" if settings.require_report_approval else "false")).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}
    report.status = "submitted" if require_approval else "approved"
    report.submitted_at = UTC_NOW()
    if report.status == "approved":
        report.approved_at = report.submitted_at
        report.finalized_at = report.submitted_at
        report.reviewer_id = actor_id
    version = create_report_version(session, report_id, actor_id, report.status)
    assignment = session.scalar(select(ReportAssignment).where(and_(ReportAssignment.match_id == report.match_id, ReportAssignment.user_id == report.reporter_id)))
    if assignment:
        assignment.status = "submitted" if report.status == "submitted" else "approved"
    audit(session, actor_id, "submit_report", "report", report.id, detail=f"V{report.version}; status={report.status}")
    return report, version


def finalize_report(session: Session, report_id: int, actor_id: int) -> Report:
    report, _ = submit_report(session, report_id, actor_id)
    return report


def approve_report(session: Session, report_id: int, actor_id: int, review_note: str | None = None) -> Report:
    assert_role(session, actor_id, "admin", "director")
    report = session.get(Report, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    if report.status != "submitted":
        raise ValueError("Solo se pueden aprobar informes entregados.")
    report.status = "approved"
    report.reviewer_id = actor_id
    report.review_note = review_note
    report.approved_at = UTC_NOW()
    report.finalized_at = report.approved_at
    version = session.scalar(select(ReportVersion).where(and_(ReportVersion.report_id == report.id, ReportVersion.version == report.version)))
    if version:
        version.status = "approved"
    assignment = session.scalar(select(ReportAssignment).where(and_(ReportAssignment.match_id == report.match_id, ReportAssignment.user_id == report.reporter_id)))
    if assignment:
        assignment.status = "approved"
    audit(session, actor_id, "approve_report", "report", report.id, detail=review_note)
    return report


def return_report(session: Session, report_id: int, actor_id: int, review_note: str) -> Report:
    assert_role(session, actor_id, "admin", "director")
    report = session.get(Report, report_id)
    if not report or report.status not in {"submitted", "approved", "final"}:
        raise ValueError("Informe no válido para devolución.")
    report.status = "returned"
    report.reviewer_id = actor_id
    report.review_note = review_note.strip() or "Revisión solicitada."
    report.version += 1
    report.revision = (report.revision or 0) + 1
    report.submitted_at = None
    report.approved_at = None
    report.finalized_at = None
    assignment = session.scalar(select(ReportAssignment).where(and_(ReportAssignment.match_id == report.match_id, ReportAssignment.user_id == report.reporter_id)))
    if assignment:
        assignment.status = "returned"
    audit(session, actor_id, "return_report", "report", report.id, detail=review_note)
    return report


def reopen_report(session: Session, report_id: int, actor_id: int) -> Report:
    return return_report(session, report_id, actor_id, "Reabierto por administración.")


def list_reports(session: Session, reporter_id: int | None = None, status: str | None = None, limit: int | None = None, match_id: int | None = None, season_id: int | None = None, competition_id: int | None = None, offset: int = 0) -> list[Report]:
    stmt = select(Report).options(joinedload(Report.match).joinedload(Match.home_team), joinedload(Report.match).joinedload(Match.away_team), joinedload(Report.match).joinedload(Match.competition), joinedload(Report.match).joinedload(Match.season), joinedload(Report.reporter), joinedload(Report.reviewer), joinedload(Report.rival_team), joinedload(Report.own_team))
    if reporter_id:
        stmt = stmt.where(Report.reporter_id == reporter_id)
    if status:
        stmt = stmt.where(Report.status == status)
    if match_id:
        stmt = stmt.where(Report.match_id == match_id)
    if season_id:
        stmt = stmt.join(Match, Report.match_id == Match.id).where(Match.season_id == season_id)
    if competition_id:
        if not season_id:
            stmt = stmt.join(Match, Report.match_id == Match.id)
        stmt = stmt.where(Match.competition_id == competition_id)
    stmt = stmt.order_by(desc(Report.updated_at)).offset(offset)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt).unique().all())


def list_report_versions(session: Session, report_id: int) -> list[ReportVersion]:
    return list(session.scalars(select(ReportVersion).where(ReportVersion.report_id == report_id).order_by(desc(ReportVersion.version))).all())


def get_report_version(session: Session, report_id: int, version: int) -> ReportVersion | None:
    return session.scalar(select(ReportVersion).where(and_(ReportVersion.report_id == report_id, ReportVersion.version == version)))


def save_document(session: Session, report_id: int, version: int, storage_path: str | None = None, public_url: str | None = None, checksum: str | None = None, *, report_version_id: int | None = None, document_type: str = "full", storage_bucket: str | None = None, local_path: str | None = None, size_bytes: int | None = None, storage_status: str = "stored", error_message: str | None = None) -> Document:
    item = session.scalar(select(Document).where(and_(Document.report_id == report_id, Document.version == version, Document.document_type == document_type)))
    if not item:
        item = Document(report_id=report_id, report_version_id=report_version_id, version=version, document_type=document_type)
        session.add(item)
    item.storage_bucket = storage_bucket
    item.storage_path = storage_path
    item.local_path = local_path
    item.checksum = checksum
    item.size_bytes = size_bytes
    item.storage_status = storage_status
    item.error_message = error_message
    session.flush()
    return item


def list_documents(session: Session, report_id: int | None = None, storage_status: str | None = None) -> list[Document]:
    stmt = select(Document)
    if report_id:
        stmt = stmt.where(Document.report_id == report_id)
    if storage_status:
        stmt = stmt.where(Document.storage_status == storage_status)
    return list(session.scalars(stmt.order_by(desc(Document.created_at))).all())


# ---------------------------------------------------------------------------
# Analytics, history and consensus
# ---------------------------------------------------------------------------

def _valid_rival_evaluation_predicates():
    return [
        Report.status.in_(FINAL_REPORT_STATUSES),
        PlayerEvaluation.evaluation_scope == "rival",
        PlayerEvaluation.team_id == Report.rival_team_id,
        PlayerEvaluation.observation_status == "evaluated",
        PlayerEvaluation.general_rating.is_not(None),
    ]


def dashboard_counts(session: Session, user_id: int | None = None) -> dict[str, int]:
    published_matches = int(session.scalar(select(func.count(Match.id)).where(and_(Match.status == "published", Match.deleted_at.is_(None)))) or 0)
    drafts_stmt = select(func.count(Report.id)).where(Report.status.in_({"draft", "returned"}))
    if user_id:
        drafts_stmt = drafts_stmt.where(Report.reporter_id == user_id)
    valid_join = select(func.count(func.distinct(PlayerEvaluation.player_id))).join(Report, PlayerEvaluation.report_id == Report.id).where(*_valid_rival_evaluation_predicates())
    assignment_stmt = select(func.count(ReportAssignment.id)).where(ReportAssignment.status.in_({"pending", "in_progress", "returned"}))
    if user_id:
        assignment_stmt = assignment_stmt.where(ReportAssignment.user_id == user_id)
    return {
        "published_matches": published_matches,
        "draft_reports": int(session.scalar(drafts_stmt) or 0),
        "final_reports": int(session.scalar(select(func.count(Report.id)).where(Report.status.in_(FINAL_REPORT_STATUSES))) or 0),
        "players_observed": int(session.scalar(valid_join) or 0),
        "pending_assignments": int(session.scalar(assignment_stmt) or 0),
    }


def player_rankings(session: Session, min_observations: int = 1, position: str | None = None, recommendation: str | None = None, *, season_id: int | None = None, competition_id: int | None = None, team_id: int | None = None, reporter_id: int | None = None, confidence: str | None = None, date_from: date | None = None, date_to: date | None = None, minimum_minutes: int | None = None, limit: int | None = None, offset: int = 0) -> list[dict]:
    stmt = select(PlayerEvaluation, Report, Match, Player, Participation).join(Report, PlayerEvaluation.report_id == Report.id).join(Match, Report.match_id == Match.id).join(Player, PlayerEvaluation.player_id == Player.id).outerjoin(Participation, PlayerEvaluation.participation_id == Participation.id).where(*_valid_rival_evaluation_predicates())
    if position and position != "Todas":
        stmt = stmt.where(or_(Participation.position == position, and_(Participation.position.is_(None), Player.primary_position == position)))
    if recommendation and recommendation != "Todas":
        stmt = stmt.where(PlayerEvaluation.recommendation == recommendation)
    if season_id:
        stmt = stmt.where(Match.season_id == season_id)
    if competition_id:
        stmt = stmt.where(Match.competition_id == competition_id)
    if team_id:
        stmt = stmt.where(PlayerEvaluation.team_id == team_id)
    if reporter_id:
        stmt = stmt.where(Report.reporter_id == reporter_id)
    if confidence and confidence != "Todas":
        stmt = stmt.where(PlayerEvaluation.confidence == confidence)
    if date_from:
        stmt = stmt.where(Match.match_date >= date_from)
    if date_to:
        stmt = stmt.where(Match.match_date <= date_to)
    if minimum_minutes:
        stmt = stmt.where((Participation.minute_out - Participation.minute_in) >= minimum_minutes)
    rows = session.execute(stmt).all()
    grouped: dict[int, dict] = {}
    for ev, report, match, player, participation in rows:
        row = grouped.setdefault(player.id, {"player_id": player.id, "full_name": player.full_name, "primary_position": participation.position if participation and participation.position else player.primary_position, "ratings": [], "technical": [], "tactical": [], "physical": [], "standouts": 0, "recommendations": [], "last_observed": None, "reporters": set(), "teams": set()})
        row["ratings"].append(float(ev.general_rating))
        for key, value in [("technical", ev.technical_rating), ("tactical", ev.tactical_rating), ("physical", ev.physical_rating)]:
            if value is not None:
                row[key].append(float(value))
        row["standouts"] += int(bool(ev.standout))
        if ev.recommendation:
            row["recommendations"].append(ev.recommendation)
        row["reporters"].add(report.reporter_id)
        row["teams"].add(ev.team_id)
        if row["last_observed"] is None or match.match_date > row["last_observed"]:
            row["last_observed"] = match.match_date
    result = []
    for row in grouped.values():
        ratings = row.pop("ratings")
        if len(ratings) < min_observations:
            continue
        avg = sum(ratings) / len(ratings)
        variance = sum((x - avg) ** 2 for x in ratings) / len(ratings) if len(ratings) > 1 else 0.0
        result.append({
            **{k: v for k, v in row.items() if k not in {"technical", "tactical", "physical", "recommendations", "reporters", "teams"}},
            "observations": len(ratings),
            "avg_general": avg,
            "rating_dispersion": math.sqrt(variance),
            "avg_technical": sum(row["technical"]) / len(row["technical"]) if row["technical"] else None,
            "avg_tactical": sum(row["tactical"]) / len(row["tactical"]) if row["tactical"] else None,
            "avg_physical": sum(row["physical"]) / len(row["physical"]) if row["physical"] else None,
            "reporter_count": len(row["reporters"]),
            "team_count": len(row["teams"]),
            "recommendation": max(set(row["recommendations"]), key=row["recommendations"].count) if row["recommendations"] else None,
        })
    result.sort(key=lambda x: (x["avg_general"], x["observations"]), reverse=True)
    return result[offset: offset + limit if limit else None]


def player_history(session: Session, player_id: int, include_non_final: bool = False) -> list[dict]:
    stmt = select(PlayerEvaluation, Report, Match, User, Team, Competition, Participation).join(Report, PlayerEvaluation.report_id == Report.id).join(Match, Report.match_id == Match.id).join(User, Report.reporter_id == User.id).join(Team, PlayerEvaluation.team_id == Team.id).join(Competition, Match.competition_id == Competition.id).outerjoin(Participation, PlayerEvaluation.participation_id == Participation.id).where(and_(PlayerEvaluation.player_id == player_id, PlayerEvaluation.evaluation_scope == "rival", PlayerEvaluation.team_id == Report.rival_team_id))
    if not include_non_final:
        stmt = stmt.where(Report.status.in_(FINAL_REPORT_STATUSES))
    stmt = stmt.options(joinedload(Match.home_team), joinedload(Match.away_team)).order_by(desc(Match.match_date))
    result = []
    for ev, report, match, user, team, competition, participation in session.execute(stmt).all():
        result.append({"evaluation": ev, "report": report, "match": match, "reporter": user, "team": team, "competition": competition, "participation": participation})
    return result


def match_consensus(session: Session, match_id: int) -> list[dict]:
    reports = list_reports(session, match_id=match_id)
    approved_ids = [r.id for r in reports if r.status in FINAL_REPORT_STATUSES]
    if not approved_ids:
        return []
    evals = list(session.scalars(select(PlayerEvaluation).options(joinedload(PlayerEvaluation.player)).where(and_(PlayerEvaluation.report_id.in_(approved_ids), PlayerEvaluation.evaluation_scope == "rival", PlayerEvaluation.observation_status == "evaluated", PlayerEvaluation.general_rating.is_not(None)))).all())
    grouped: dict[int, list[PlayerEvaluation]] = defaultdict(list)
    for ev in evals:
        grouped[ev.player_id].append(ev)
    result = []
    for pid, items in grouped.items():
        values = [float(x.general_rating) for x in items]
        avg = sum(values) / len(values)
        dispersion = math.sqrt(sum((x - avg) ** 2 for x in values) / len(values)) if len(values) > 1 else 0.0
        result.append({"player_id": pid, "player_name": items[0].player.full_name, "sample_size": len(items), "average": avg, "dispersion": dispersion, "recommendations": [x.recommendation for x in items if x.recommendation], "notes": [x.short_note for x in items if x.short_note], "confidence": [x.confidence for x in items if x.confidence]})
    return sorted(result, key=lambda x: x["average"], reverse=True)


def get_or_create_consolidation(session: Session, match_id: int, actor_id: int) -> ConsolidatedReport:
    assert_role(session, actor_id, "admin", "director")
    match = get_match(session, match_id)
    if not match:
        raise ValueError("Partido no encontrado.")
    own_id = _own_team_id_for_match(session, match)
    rival_id = match.away_team_id if own_id == match.home_team_id else match.home_team_id
    item = session.scalar(select(ConsolidatedReport).where(and_(ConsolidatedReport.match_id == match_id, ConsolidatedReport.rival_team_id == rival_id)))
    if not item:
        item = ConsolidatedReport(match_id=match_id, rival_team_id=rival_id, created_by=actor_id)
        session.add(item)
        session.flush()
    return item


def save_consolidation(session: Session, consolidation_id: int, actor_id: int, overview: str | None, key_takeaways: str | None, player_rows: Sequence[dict], approve: bool = False) -> ConsolidatedReport:
    assert_role(session, actor_id, "admin", "director")
    item = session.get(ConsolidatedReport, consolidation_id)
    if not item:
        raise ValueError("Consolidación no encontrada.")
    item.overview = overview
    item.key_takeaways = key_takeaways
    item.revision = (item.revision or 0) + 1
    for row in player_rows:
        ev = session.scalar(select(ConsolidatedPlayerEvaluation).where(and_(ConsolidatedPlayerEvaluation.consolidated_report_id == item.id, ConsolidatedPlayerEvaluation.player_id == int(row["player_id"]))))
        if not ev:
            ev = ConsolidatedPlayerEvaluation(consolidated_report_id=item.id, player_id=int(row["player_id"]))
            session.add(ev)
        ev.final_rating = row.get("final_rating")
        ev.final_recommendation = row.get("final_recommendation")
        ev.consensus_note = row.get("consensus_note")
        ev.sample_size = int(row.get("sample_size") or 0)
        ev.dispersion = row.get("dispersion")
        ev.confidence_summary = row.get("confidence_summary")
    if approve:
        item.status = "approved"
        item.approved_by = actor_id
        item.approved_at = UTC_NOW()
    audit(session, actor_id, "save_consolidation", "consolidated_report", item.id, detail=f"approve={approve}")
    return item


def list_consolidated_evaluations(session: Session, consolidation_id: int) -> list[ConsolidatedPlayerEvaluation]:
    return list(session.scalars(select(ConsolidatedPlayerEvaluation).options(joinedload(ConsolidatedPlayerEvaluation.player)).where(ConsolidatedPlayerEvaluation.consolidated_report_id == consolidation_id).order_by(desc(ConsolidatedPlayerEvaluation.final_rating))).all())


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

def upsert_follow_up(session: Session, player_id: int, status: str, priority: int, note: str | None, actor_id: int, assigned_to: int | None = None, next_review_date: date | None = None, target_match_id: int | None = None, closed_reason: str | None = None, expected_revision: int | None = None) -> FollowUp:
    assert_role(session, actor_id, "admin", "director")
    item = session.scalar(select(FollowUp).where(FollowUp.player_id == player_id))
    if not item:
        item = FollowUp(player_id=player_id, status=status, priority=priority, note=note, created_by=actor_id, assigned_to=assigned_to, next_review_date=next_review_date, target_match_id=target_match_id, closed_reason=closed_reason)
        session.add(item)
        session.flush()
    else:
        if expected_revision is not None and item.revision != expected_revision:
            raise RuntimeError("El seguimiento cambió en otra sesión. Recarga antes de guardar.")
        item.status = status
        item.priority = priority
        item.note = note
        item.assigned_to = assigned_to
        item.next_review_date = next_review_date
        item.target_match_id = target_match_id
        item.closed_reason = closed_reason
        item.revision = (item.revision or 0) + 1
    session.add(FollowUpHistory(follow_up_id=item.id, actor_id=actor_id, status=status, note=note))
    audit(session, actor_id, "upsert_follow_up", "player", player_id, detail=f"status={status}; priority={priority}")
    return item


def list_follow_ups(session: Session, status: str | None = None, assigned_to: int | None = None) -> list[FollowUp]:
    stmt = select(FollowUp).options(joinedload(FollowUp.player), joinedload(FollowUp.assignee), joinedload(FollowUp.target_match))
    if status and status != "Todos":
        stmt = stmt.where(FollowUp.status == status)
    if assigned_to:
        stmt = stmt.where(FollowUp.assigned_to == assigned_to)
    return list(session.scalars(stmt.order_by(FollowUp.priority, FollowUp.next_review_date.nullslast(), FollowUp.updated_at.desc())).unique().all())


def follow_up_history(session: Session, follow_up_id: int) -> list[FollowUpHistory]:
    return list(session.scalars(select(FollowUpHistory).where(FollowUpHistory.follow_up_id == follow_up_id).order_by(desc(FollowUpHistory.created_at))).all())


def list_audit_logs(session: Session, limit: int = 100, action: str | None = None) -> list[AuditLog]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return list(session.scalars(stmt.order_by(desc(AuditLog.created_at)).limit(limit)).all())

# ---------------------------------------------------------------------------
# No Name Edition 3.0 convenience workflows
# ---------------------------------------------------------------------------

def get_own_team(session: Session) -> Team | None:
    """Return the configured own team without creating any catalogue data."""
    configured = get_setting(session, "own_team_id")
    if configured:
        try:
            item = session.get(Team, int(configured))
            if item and item.active:
                return item
        except (TypeError, ValueError):
            pass
    return session.scalar(
        select(Team).where(and_(Team.is_own_team.is_(True), Team.active.is_(True))).order_by(Team.id).limit(1)
    )


def get_active_season(session: Session) -> Season | None:
    """Return the season explicitly selected as active, or the newest active season."""
    configured = get_setting(session, "active_season_id")
    if configured:
        try:
            item = session.get(Season, int(configured))
            if item and item.active:
                return item
        except (TypeError, ValueError):
            pass
    return session.scalar(select(Season).where(Season.active.is_(True)).order_by(desc(Season.name)).limit(1))


def set_active_season(session: Session, season_id: int, actor_id: int | None = None) -> Season:
    season = session.get(Season, int(season_id))
    if not season or not season.active:
        raise ValueError("Temporada activa no válida.")
    set_setting(session, "active_season_id", str(season.id), actor_id)
    return season


def previous_match_with_team(
    session: Session,
    team_id: int,
    *,
    before_date: date | None = None,
    exclude_match_id: int | None = None,
    opponent_id: int | None = None,
) -> Match | None:
    stmt = (
        select(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team), joinedload(Match.season), joinedload(Match.competition))
        .where(
            Match.deleted_at.is_(None),
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        )
    )
    if before_date:
        stmt = stmt.where(Match.match_date <= before_date)
    if exclude_match_id:
        stmt = stmt.where(Match.id != exclude_match_id)
    if opponent_id:
        stmt = stmt.where(
            or_(
                and_(Match.home_team_id == team_id, Match.away_team_id == opponent_id),
                and_(Match.away_team_id == team_id, Match.home_team_id == opponent_id),
            )
        )
    stmt = stmt.order_by(desc(Match.match_date), desc(Match.id)).limit(1)
    return session.scalar(stmt)


def copy_lineup_from_match(
    session: Session,
    *,
    source_match_id: int,
    target_match_id: int,
    team_id: int,
    actor_id: int,
) -> list[Participation]:
    """Copy a prior lineup into a draft match, preserving player, role and minutes."""
    source_rows = get_participations(session, source_match_id, team_id)
    if not source_rows:
        raise ValueError("El partido anterior no tiene una alineación guardada para este equipo.")
    target_match = get_match(session, target_match_id)
    if not target_match:
        raise ValueError("Partido destino no encontrado.")
    data = []
    for p in source_rows:
        # Keep the season roster in sync when reusing players.
        assign_player_to_roster(
            session,
            team_id,
            target_match.season_id,
            p.player_id,
            p.shirt_number,
            actor_id,
        )
        data.append({
            "selected": True,
            "player_id": p.player_id,
            "shirt_number": p.shirt_number,
            "starter": p.starter,
            "position": p.position or p.player.primary_position or "Otro",
            "minute_in": p.minute_in,
            "minute_out": p.minute_out,
            "captain": p.captain,
        })
    result = replace_participations(session, target_match_id, team_id, data, actor_id)
    audit(
        session,
        actor_id,
        "copy_lineup",
        "match",
        target_match_id,
        detail=f"source={source_match_id}; team={team_id}; rows={len(result)}",
    )
    return result


def save_named_lineup(
    session: Session,
    *,
    match_id: int,
    team_id: int,
    season_id: int,
    rows: Sequence[dict],
    actor_id: int,
    sync_roster: bool = True,
) -> list[Participation]:
    """Resolve/create players from a quick named lineup and save participations.

    This removes the old requirement for a rival roster to exist before the match.
    A rival player typed into the post-match wizard can become a catalogue player and
    roster member as a natural consequence of the participation itself.
    """
    prepared: list[dict] = []
    errors: list[str] = []
    for index, raw in enumerate(rows, start=1):
        name = str(raw.get("name") or raw.get("player") or raw.get("Jugador") or "").strip()
        if not name:
            continue
        position = str(raw.get("position") or raw.get("Posición") or "Otro").strip() or "Otro"
        try:
            player = find_or_create_player(
                session,
                name,
                primary_position=position,
                actor_id=actor_id,
            )
            shirt_raw = raw.get("shirt_number", raw.get("Dorsal"))
            shirt = int(shirt_raw) if shirt_raw not in (None, "") and not (isinstance(shirt_raw, float) and math.isnan(shirt_raw)) else None
            if sync_roster:
                assign_player_to_roster(session, team_id, season_id, player.id, shirt, actor_id)
            starter = bool(raw.get("starter", raw.get("Titular", False)))
            minute_in = int(raw.get("minute_in", raw.get("Entrada", 0)) or 0)
            minute_out = int(raw.get("minute_out", raw.get("Salida", 90)) or 90)
            if starter:
                minute_in = 0
            prepared.append({
                "selected": True,
                "player_id": player.id,
                "shirt_number": shirt,
                "starter": starter,
                "position": position,
                "minute_in": minute_in,
                "minute_out": minute_out,
                "captain": bool(raw.get("captain", raw.get("Capitán", False))),
            })
        except Exception as exc:
            errors.append(f"Fila {index} · {name}: {exc}")
    if errors:
        raise ValueError("\n".join(errors))
    if not prepared:
        raise ValueError("Añade al menos un jugador antes de guardar la alineación.")
    return replace_participations(session, match_id, team_id, prepared, actor_id)


def own_player_rankings(
    session: Session,
    min_observations: int = 1,
    *,
    season_id: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Aggregate only approved/final internal evaluations of the own team."""
    stmt = (
        select(PlayerEvaluation, Report, Match, Player, Participation)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(Player, PlayerEvaluation.player_id == Player.id)
        .outerjoin(Participation, PlayerEvaluation.participation_id == Participation.id)
        .where(
            Report.status.in_(FINAL_REPORT_STATUSES),
            PlayerEvaluation.evaluation_scope == "own",
            PlayerEvaluation.team_id == Report.own_team_id,
            PlayerEvaluation.observation_status == "evaluated",
            PlayerEvaluation.general_rating.is_not(None),
        )
    )
    if season_id:
        stmt = stmt.where(Match.season_id == season_id)
    rows = session.execute(stmt).all()
    grouped: dict[int, dict] = {}
    for ev, report, match, player, participation in rows:
        row = grouped.setdefault(
            player.id,
            {
                "player_id": player.id,
                "full_name": player.full_name,
                "primary_position": (participation.position if participation and participation.position else player.primary_position),
                "ratings": [],
                "standouts": 0,
                "reporters": set(),
                "last_observed": None,
            },
        )
        row["ratings"].append(float(ev.general_rating))
        row["standouts"] += int(bool(ev.standout))
        row["reporters"].add(report.reporter_id)
        if row["last_observed"] is None or match.match_date > row["last_observed"]:
            row["last_observed"] = match.match_date
    result: list[dict] = []
    for row in grouped.values():
        values = row.pop("ratings")
        if len(values) < min_observations:
            continue
        avg = sum(values) / len(values)
        dispersion = math.sqrt(sum((x - avg) ** 2 for x in values) / len(values)) if len(values) > 1 else 0.0
        result.append({
            **{k: v for k, v in row.items() if k != "reporters"},
            "observations": len(values),
            "avg_general": avg,
            "rating_dispersion": dispersion,
            "reporter_count": len(row["reporters"]),
        })
    result.sort(key=lambda x: (x["avg_general"], x["observations"]), reverse=True)
    return result[:limit] if limit else result


def player_history_by_scope(
    session: Session,
    player_id: int,
    *,
    scope: str = "rival",
    include_non_final: bool = False,
) -> list[dict]:
    if scope not in {"rival", "own", "all"}:
        raise ValueError("Ámbito de historial no válido.")
    stmt = (
        select(PlayerEvaluation, Report, Match, User, Team, Competition, Participation)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(User, Report.reporter_id == User.id)
        .join(Team, PlayerEvaluation.team_id == Team.id)
        .join(Competition, Match.competition_id == Competition.id)
        .outerjoin(Participation, PlayerEvaluation.participation_id == Participation.id)
        .where(PlayerEvaluation.player_id == player_id)
    )
    if scope == "rival":
        stmt = stmt.where(PlayerEvaluation.evaluation_scope == "rival", PlayerEvaluation.team_id == Report.rival_team_id)
    elif scope == "own":
        stmt = stmt.where(PlayerEvaluation.evaluation_scope == "own", PlayerEvaluation.team_id == Report.own_team_id)
    if not include_non_final:
        stmt = stmt.where(Report.status.in_(FINAL_REPORT_STATUSES))
    stmt = stmt.options(joinedload(Match.home_team), joinedload(Match.away_team)).order_by(desc(Match.match_date), desc(Report.id))
    result = []
    for ev, report, match, user, team, competition, participation in session.execute(stmt).all():
        result.append({
            "evaluation": ev,
            "report": report,
            "match": match,
            "reporter": user,
            "team": team,
            "competition": competition,
            "participation": participation,
        })
    return result


def recent_rival_highlights(session: Session, *, limit: int = 12, minimum_rating: float = 8.0) -> list[dict]:
    stmt = (
        select(PlayerEvaluation, Report, Match, Player, Participation)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(Player, PlayerEvaluation.player_id == Player.id)
        .outerjoin(Participation, PlayerEvaluation.participation_id == Participation.id)
        .where(
            *_valid_rival_evaluation_predicates(),
            PlayerEvaluation.general_rating >= minimum_rating,
        )
        .order_by(desc(Match.match_date), desc(PlayerEvaluation.general_rating))
        .limit(limit)
    )
    result = []
    for ev, report, match, player, participation in session.execute(stmt).all():
        result.append({
            "evaluation": ev,
            "report": report,
            "match": match,
            "player": player,
            "participation": participation,
        })
    return result
