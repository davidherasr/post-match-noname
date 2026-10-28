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
    ReportVersion, ScoutingList, ScoutingListItem, ScoutedPlayerProfile, ScoutReview, Season, Team, TeamRoster, User,
)
from repositories.common import UTC_NOW, FINAL_REPORT_STATUSES, LOCKED_REPORT_STATUSES, _snapshot, audit

from repositories.users import assert_role, get_setting, set_setting

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
    item = Team(name=name.strip(), short_name=short_name.strip() if short_name else None, country=country.strip() if country else None, is_own_team=is_own_team)
    session.add(item)
    session.flush()
    if is_own_team:
        set_own_team(session, item.id, actor_id)
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
            if key == "active" and not values[key] and item.is_own_team:
                raise ValueError("No se puede desactivar el equipo propio.")
            if key == "active" and values[key] and item.archived_at is not None:
                raise ValueError("Usa Restaurar equipo: no es posible activar directamente un archivo.")
            setattr(item, key, values[key])
    if values.get("is_own_team"):
        set_own_team(session, item.id, actor_id)
    audit(session, actor_id, "update_team", "team", item.id, before=before, after=_snapshot(item, before.keys()))
    return item


def set_own_team(session: Session, team_id: int, actor_id: int | None = None) -> None:
    if actor_id is not None:
        assert_role(session, actor_id, "admin")
    target = session.get(Team, int(team_id))
    if not target or not target.active or target.is_test or target.archived_at is not None:
        raise ValueError("El equipo propio debe existir, estar activo y no ser de prueba/archivado.")
    old = get_setting(session, "own_team_id")
    for team in session.scalars(select(Team).where(Team.is_own_team.is_(True))).all():
        team.is_own_team = False
    target.is_own_team = True
    set_setting(session, "own_team_id", str(target.id), actor_id)
    audit(session, actor_id, "set_own_team", "team", target.id,
          before={"own_team_id": old}, after={"own_team_id": target.id})


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


def get_own_team(session: Session) -> Team | None:
    """Return the configured own team without creating any catalogue data."""
    configured = get_setting(session, "own_team_id")
    if configured:
        try:
            item = session.get(Team, int(configured))
            if item and item.active and not item.is_test and item.archived_at is None:
                return item
        except (TypeError, ValueError):
            pass
    candidates = list(session.scalars(
        select(Team).where(and_(Team.is_own_team.is_(True), Team.active.is_(True),
                                Team.is_test.is_(False), Team.archived_at.is_(None)))
    ).all())
    return candidates[0] if len(candidates) == 1 else None


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
