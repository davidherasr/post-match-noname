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

from repositories.users import assert_role, user_has_role
from repositories.players import get_own_team

def create_match(session: Session, *, season_id: int, competition_id: int, round_name: str, match_date: date, home_team_id: int, away_team_id: int, created_by: int, home_score: int | None = None, away_score: int | None = None, venue: str | None = None, home_formation: str | None = None, away_formation: str | None = None, status: str = "draft", report_due_at: datetime | None = None, kickoff_at: datetime | None = None, schedule_status: str | None = None) -> Match:
    assert_role(session, created_by, "admin")
    if home_team_id == away_team_id:
        raise ValueError("Los equipos local y visitante deben ser diferentes.")
    item = Match(season_id=season_id, competition_id=competition_id, round_name=round_name.strip(), match_date=match_date, kickoff_at=kickoff_at, schedule_status=schedule_status or ("confirmed" if kickoff_at else "provisional"), window_start=None, window_end=None, home_team_id=home_team_id, away_team_id=away_team_id, home_score=home_score, away_score=away_score, venue=venue, home_formation=home_formation, away_formation=away_formation, status=status, report_due_at=report_due_at, created_by=created_by)
    session.add(item)
    session.flush()
    audit(session, created_by, "create_match", "match", item.id, after=_snapshot(item, ["round_name", "match_date", "kickoff_at", "schedule_status", "home_team_id", "away_team_id", "status"]))
    return item


def update_match(session: Session, match_id: int, actor_id: int | None = None, expected_revision: int | None = None, **values) -> Match:
    if actor_id is not None:
        assert_role(session, actor_id, "admin")
    item = session.get(Match, match_id)
    if not item:
        raise ValueError("Partido no encontrado.")
    if expected_revision is not None and item.revision != expected_revision:
        raise RuntimeError("El partido ha cambiado en otra sesión. Recarga antes de guardar.")
    before = _snapshot(item, ["season_id", "competition_id", "round_name", "match_date", "window_start", "window_end", "kickoff_at", "schedule_status", "home_team_id", "away_team_id", "home_score", "away_score", "venue", "home_formation", "away_formation", "status", "report_due_at", "revision"])
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
        if not user or not user.active or not user_has_role(session, user.id, "reporter", "admin", "director"):
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


def assignment_progress_many(session: Session, match_ids: Sequence[int]) -> dict[int, dict[str, int]]:
    """Return progress for many matches with one database roundtrip."""
    ids = [int(mid) for mid in match_ids]
    result = {mid: {"total": 0, "approved": 0, "submitted": 0, "pending": 0} for mid in ids}
    if not ids:
        return result
    rows = session.execute(
        select(ReportAssignment.match_id, ReportAssignment.status, ReportAssignment.required)
        .where(ReportAssignment.match_id.in_(ids))
    ).all()
    for match_id, status, required in rows:
        item = result.setdefault(int(match_id), {"total": 0, "approved": 0, "submitted": 0, "pending": 0})
        if required:
            item["total"] += 1
        if status == "approved":
            item["approved"] += 1
        elif status == "submitted":
            item["submitted"] += 1
        elif status in {"pending", "in_progress", "returned"}:
            item["pending"] += 1
    return result
