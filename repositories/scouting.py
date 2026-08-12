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
    AppSetting,
    AuditLog,
    Competition,
    ConsolidatedPlayerEvaluation,
    ConsolidatedReport,
    Document,
    FollowUp,
    FollowUpHistory,
    LoginAttempt,
    LeaguePlayerProfile,
    Match,
    Participation,
    Player,
    PlayerAlias,
    PlayerEvaluation,
    PlayerMergeLog,
    PostMatchDraft,
    Report,
    ReportAssignment,
    ReportVersion,
    ScoutingList,
    ScoutingListItem,
    ScoutedPlayerProfile,
    ScoutReview,
    Season,
    Team,
    TeamRoster,
    User,
)

from repositories.common import UTC_NOW, FINAL_REPORT_STATUSES, LOCKED_REPORT_STATUSES, _snapshot, audit
from repositories.users import *
from repositories.players import *
from repositories.matches import *
from repositories.reports import *
# Private report/match helpers used internally in this compatibility facade.
from repositories.reports import _assert_report_owner_or_privileged, _report_snapshot_data
from repositories.matches import _own_team_id_for_match






# ---------------------------------------------------------------------------
# Users, authentication and authorization
# ---------------------------------------------------------------------------



















# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------







# ---------------------------------------------------------------------------
# Catalogue and player identity
# ---------------------------------------------------------------------------









































# ---------------------------------------------------------------------------
# Matches, lineups and assignments
# ---------------------------------------------------------------------------

























# ---------------------------------------------------------------------------
# Reports, evaluations, versions and documents
# ---------------------------------------------------------------------------















































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
    """Aggregate rival scouting in SQL instead of loading every evaluation into Python.

    This is the hot path for Dirección Deportiva. PostgreSQL/SQLite return one row
    per player; Python only derives dispersion from aggregate moments.
    """
    observed_position = func.coalesce(Participation.position, Player.primary_position)
    rating = PlayerEvaluation.general_rating
    stmt = (
        select(
            Player.id.label("player_id"),
            Player.full_name.label("full_name"),
            Player.date_of_birth.label("date_of_birth"),
            func.max(observed_position).label("primary_position"),
            func.count(PlayerEvaluation.id).label("observations"),
            func.avg(rating).label("avg_general"),
            func.avg(rating * rating).label("avg_rating_sq"),
            func.avg(PlayerEvaluation.technical_rating).label("avg_technical"),
            func.avg(PlayerEvaluation.tactical_rating).label("avg_tactical"),
            func.avg(PlayerEvaluation.physical_rating).label("avg_physical"),
            func.sum(case((PlayerEvaluation.standout.is_(True), 1), else_=0)).label("standouts"),
            func.count(func.distinct(Report.reporter_id)).label("reporter_count"),
            func.count(func.distinct(PlayerEvaluation.team_id)).label("team_count"),
            func.max(Match.match_date).label("last_observed"),
        )
        .select_from(PlayerEvaluation)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(Player, PlayerEvaluation.player_id == Player.id)
        .outerjoin(Participation, PlayerEvaluation.participation_id == Participation.id)
        .where(*_valid_rival_evaluation_predicates())
    )
    if position and position != "Todas":
        stmt = stmt.where(observed_position == position)
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
    stmt = (
        stmt.group_by(Player.id, Player.full_name, Player.date_of_birth)
        .having(func.count(PlayerEvaluation.id) >= int(min_observations))
        .order_by(desc(func.avg(rating)), desc(func.count(PlayerEvaluation.id)), Player.full_name)
        .offset(int(offset or 0))
    )
    if limit:
        stmt = stmt.limit(int(limit))
    result = []
    for row in session.execute(stmt).mappings().all():
        avg = float(row["avg_general"] or 0.0)
        avg_sq = float(row["avg_rating_sq"] or avg * avg)
        variance = max(0.0, avg_sq - (avg * avg))
        result.append({
            "player_id": int(row["player_id"]),
            "full_name": row["full_name"],
            "date_of_birth": row["date_of_birth"],
            "primary_position": row["primary_position"],
            "observations": int(row["observations"] or 0),
            "avg_general": avg,
            "rating_dispersion": math.sqrt(variance),
            "avg_technical": float(row["avg_technical"]) if row["avg_technical"] is not None else None,
            "avg_tactical": float(row["avg_tactical"]) if row["avg_tactical"] is not None else None,
            "avg_physical": float(row["avg_physical"]) if row["avg_physical"] is not None else None,
            "standouts": int(row["standouts"] or 0),
            "reporter_count": int(row["reporter_count"] or 0),
            "team_count": int(row["team_count"] or 0),
            "last_observed": row["last_observed"],
            "recommendation": None,
        })
    return result


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


def get_follow_up_for_player(session: Session, player_id: int) -> FollowUp | None:
    """Load one player's tracking record without materialising the full follow-up agenda."""
    return session.scalar(
        select(FollowUp)
        .options(joinedload(FollowUp.player), joinedload(FollowUp.assignee), joinedload(FollowUp.target_match))
        .where(FollowUp.player_id == int(player_id))
    )


def follow_up_history(session: Session, follow_up_id: int) -> list[FollowUpHistory]:
    return list(session.scalars(select(FollowUpHistory).where(FollowUpHistory.follow_up_id == follow_up_id).order_by(desc(FollowUpHistory.created_at))).all())



# ---------------------------------------------------------------------------
# No Name Edition 3.0 convenience workflows
# ---------------------------------------------------------------------------







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
    identity_resolutions: dict[str, int] | None = None,
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

# ---------------------------------------------------------------------------
# No Name 3.2 · fast postmatch drafts and league intelligence
# ---------------------------------------------------------------------------

LEAGUE_DECISION_STATUSES = ["Base", "Interesante", "Seguimiento", "Prioritario", "Descartado"]


def save_postmatch_draft(
    session: Session,
    *,
    actor_id: int,
    payload: dict,
    draft_id: int | None = None,
    season_id: int | None = None,
    title: str | None = None,
) -> PostMatchDraft:
    assert_role(session, actor_id, "admin")
    item = session.get(PostMatchDraft, int(draft_id)) if draft_id else None
    if item and item.created_by != actor_id:
        raise PermissionError("Este borrador pertenece a otro usuario.")
    if not item:
        item = PostMatchDraft(
            created_by=actor_id,
            season_id=season_id,
            title=title,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
            status="draft",
            created_at=UTC_NOW(),
            updated_at=UTC_NOW(),
        )
        session.add(item)
    else:
        item.season_id = season_id
        item.title = title
        item.payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        item.updated_at = UTC_NOW()
    session.flush()
    audit(session, actor_id, "save_postmatch_draft", "postmatch_draft", item.id, detail=title)
    return item


def list_postmatch_drafts(session: Session, actor_id: int, *, limit: int = 20) -> list[PostMatchDraft]:
    return list(session.scalars(
        select(PostMatchDraft)
        .where(PostMatchDraft.created_by == actor_id, PostMatchDraft.status == "draft")
        .order_by(desc(PostMatchDraft.updated_at))
        .limit(limit)
    ).all())


def load_postmatch_draft(session: Session, draft_id: int, actor_id: int) -> dict:
    item = session.get(PostMatchDraft, int(draft_id))
    if not item or item.status != "draft" or item.created_by != actor_id:
        raise ValueError("Borrador no encontrado.")
    try:
        return json.loads(item.payload_json)
    except Exception as exc:
        raise ValueError("El borrador guardado no se puede leer.") from exc


def close_postmatch_draft(session: Session, draft_id: int | None, actor_id: int) -> None:
    if not draft_id:
        return
    item = session.get(PostMatchDraft, int(draft_id))
    if item and item.created_by == actor_id:
        item.status = "published"
        item.updated_at = UTC_NOW()
        audit(session, actor_id, "publish_postmatch_draft", "postmatch_draft", item.id)


def latest_player_team_map(session: Session, player_ids: Sequence[int]) -> dict[int, dict]:
    ids = [int(x) for x in player_ids]
    if not ids:
        return {}
    stmt = (
        select(PlayerEvaluation.player_id, Team.id, Team.name, Match.match_date)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(Team, PlayerEvaluation.team_id == Team.id)
        .where(*_valid_rival_evaluation_predicates(), PlayerEvaluation.player_id.in_(ids))
        .order_by(desc(Match.match_date), desc(PlayerEvaluation.id))
    )
    result: dict[int, dict] = {}
    for player_id, team_id, team_name, observed_at in session.execute(stmt).all():
        pid = int(player_id)
        if pid not in result:
            result[pid] = {"team_id": int(team_id), "team_name": team_name, "last_observed": observed_at}
    return result


def confidence_from_sample(observations: int, reporter_count: int, dispersion: float) -> str:
    if observations >= 4 and reporter_count >= 2 and dispersion <= 0.75:
        return "Alta"
    if observations >= 2 and dispersion <= 1.25:
        return "Media"
    return "Baja"


def get_league_profile(session: Session, player_id: int) -> LeaguePlayerProfile | None:
    return session.scalar(
        select(LeaguePlayerProfile)
        .options(joinedload(LeaguePlayerProfile.player), joinedload(LeaguePlayerProfile.updater))
        .where(LeaguePlayerProfile.player_id == int(player_id))
    )


def list_league_profiles(session: Session) -> list[LeaguePlayerProfile]:
    return list(session.scalars(
        select(LeaguePlayerProfile)
        .options(joinedload(LeaguePlayerProfile.player), joinedload(LeaguePlayerProfile.updater))
        .order_by(LeaguePlayerProfile.priority, desc(LeaguePlayerProfile.updated_at))
    ).all())


def upsert_league_profile(
    session: Session,
    player_id: int,
    actor_id: int,
    *,
    decision_status: str,
    priority: int = 3,
    director_note: str | None = None,
    expected_revision: int | None = None,
) -> LeaguePlayerProfile:
    assert_role(session, actor_id, "admin", "director")
    if decision_status not in LEAGUE_DECISION_STATUSES:
        raise ValueError("Estado de dirección deportiva no válido.")
    item = session.scalar(select(LeaguePlayerProfile).where(LeaguePlayerProfile.player_id == int(player_id)))
    before = None
    if item:
        before = _snapshot(item, ["decision_status", "priority", "director_note", "revision"])
        if expected_revision is not None and item.revision != expected_revision:
            raise ValueError("La ficha cambió en otra sesión. Recarga antes de guardar.")
        item.decision_status = decision_status
        item.priority = int(priority)
        item.director_note = director_note
        item.updated_by = actor_id
        item.revision += 1
        item.updated_at = UTC_NOW()
    else:
        item = LeaguePlayerProfile(
            player_id=int(player_id),
            decision_status=decision_status,
            priority=int(priority),
            director_note=director_note,
            updated_by=actor_id,
            created_at=UTC_NOW(),
            updated_at=UTC_NOW(),
        )
        session.add(item)
    session.flush()
    audit(
        session,
        actor_id,
        "update_league_profile",
        "player",
        int(player_id),
        before=before,
        after=_snapshot(item, ["decision_status", "priority", "director_note", "revision"]),
    )
    return item


def list_scouting_lists(session: Session, *, active_only: bool = True) -> list[ScoutingList]:
    stmt = select(ScoutingList).options(joinedload(ScoutingList.season)).order_by(desc(ScoutingList.updated_at))
    if active_only:
        stmt = stmt.where(ScoutingList.active.is_(True))
    return list(session.scalars(stmt).all())


def create_scouting_list(
    session: Session,
    actor_id: int,
    *,
    name: str,
    description: str | None = None,
    list_type: str = "custom",
    formation: str | None = None,
    season_id: int | None = None,
) -> ScoutingList:
    assert_role(session, actor_id, "admin", "director")
    item = ScoutingList(
        name=name.strip(),
        description=description,
        list_type=list_type,
        formation=formation,
        season_id=season_id,
        created_by=actor_id,
        active=True,
        created_at=UTC_NOW(),
        updated_at=UTC_NOW(),
    )
    session.add(item)
    session.flush()
    audit(session, actor_id, "create_scouting_list", "scouting_list", item.id, detail=item.name)
    return item


def list_scouting_list_items(session: Session, list_id: int) -> list[ScoutingListItem]:
    return list(session.scalars(
        select(ScoutingListItem)
        .options(joinedload(ScoutingListItem.player))
        .where(ScoutingListItem.list_id == int(list_id))
        .order_by(ScoutingListItem.order_index, ScoutingListItem.id)
    ).all())


def add_scouting_list_item(
    session: Session,
    list_id: int,
    player_id: int,
    actor_id: int,
    *,
    position: str | None = None,
    order_index: int = 0,
    note: str | None = None,
) -> ScoutingListItem:
    assert_role(session, actor_id, "admin", "director")
    item = session.scalar(select(ScoutingListItem).where(
        ScoutingListItem.list_id == int(list_id), ScoutingListItem.player_id == int(player_id)
    ))
    if not item:
        item = ScoutingListItem(
            list_id=int(list_id), player_id=int(player_id), position=position,
            order_index=int(order_index), note=note, created_at=UTC_NOW(),
        )
        session.add(item)
    else:
        item.position = position or item.position
        item.order_index = int(order_index)
        item.note = note
    session.flush()
    audit(session, actor_id, "add_scouting_list_item", "scouting_list", int(list_id), detail=f"player={player_id}")
    return item


def remove_scouting_list_item(session: Session, list_id: int, player_id: int, actor_id: int) -> None:
    assert_role(session, actor_id, "admin", "director")
    item = session.scalar(select(ScoutingListItem).where(
        ScoutingListItem.list_id == int(list_id), ScoutingListItem.player_id == int(player_id)
    ))
    if item:
        session.delete(item)
        audit(session, actor_id, "remove_scouting_list_item", "scouting_list", int(list_id), detail=f"player={player_id}")


def global_catalog_search(session: Session, query: str, *, limit: int = 30) -> dict[str, list]:
    q = str(query or "").strip()
    if len(q) < 2:
        return {"players": [], "teams": []}
    pattern = f"%{q}%"
    players = list(session.scalars(
        select(Player).where(
            Player.active.is_(True),
            or_(Player.full_name.ilike(pattern), Player.display_name.ilike(pattern), Player.aliases.ilike(pattern)),
        ).order_by(Player.full_name).limit(limit)
    ).all())
    teams = list(session.scalars(
        select(Team).where(Team.active.is_(True), or_(Team.name.ilike(pattern), Team.short_name.ilike(pattern)))
        .order_by(Team.name).limit(limit)
    ).all())
    return {"players": players, "teams": teams}


def league_panorama(session: Session, *, season_id: int | None = None) -> dict[str, int]:
    base = (
        select(
            func.count(func.distinct(PlayerEvaluation.player_id)).label("players"),
            func.count(func.distinct(PlayerEvaluation.team_id)).label("teams"),
            func.count(func.distinct(Match.id)).label("matches"),
        )
        .select_from(PlayerEvaluation)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .where(*_valid_rival_evaluation_predicates())
    )
    if season_id:
        base = base.where(Match.season_id == season_id)
    row = session.execute(base).mappings().one()

    multi_sub = (
        select(PlayerEvaluation.player_id)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .where(*_valid_rival_evaluation_predicates())
    )
    if season_id:
        multi_sub = multi_sub.where(Match.season_id == season_id)
    multi_sub = multi_sub.group_by(PlayerEvaluation.player_id).having(func.count(PlayerEvaluation.id) >= 2).subquery()

    return {
        "players_observed": int(row["players"] or 0),
        "teams_observed": int(row["teams"] or 0),
        "matches_analyzed": int(row["matches"] or 0),
        "players_repeated": int(session.scalar(select(func.count()).select_from(multi_sub)) or 0),
        "followups_active": int(session.scalar(select(func.count(FollowUp.id)).where(~FollowUp.status.in_({"Descartado", "Cerrado"}))) or 0),
        "priority_players": int(session.scalar(select(func.count(LeaguePlayerProfile.id)).where(LeaguePlayerProfile.decision_status == "Prioritario")) or 0),
        "reports_pending_review": int(session.scalar(select(func.count(Report.id)).where(Report.status == "submitted")) or 0),
    }


def league_team_summaries(session: Session, *, season_id: int | None = None) -> list[dict]:
    stmt = (
        select(
            Team.id.label("team_id"), Team.name.label("team_name"),
            func.count(func.distinct(Match.id)).label("matches"),
            func.count(func.distinct(PlayerEvaluation.player_id)).label("players"),
            func.avg(PlayerEvaluation.general_rating).label("avg_rating"),
            func.sum(case((PlayerEvaluation.standout.is_(True), 1), else_=0)).label("standouts"),
            func.max(Match.match_date).label("last_observed"),
        )
        .select_from(PlayerEvaluation)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(Team, PlayerEvaluation.team_id == Team.id)
        .where(*_valid_rival_evaluation_predicates())
    )
    if season_id:
        stmt = stmt.where(Match.season_id == season_id)
    stmt = stmt.group_by(Team.id, Team.name).order_by(desc(func.avg(PlayerEvaluation.general_rating)), Team.name)
    return [dict(r) for r in session.execute(stmt).mappings().all()]


def league_trends(session: Session, *, season_id: int | None = None, min_observations: int = 2, limit: int = 15) -> list[dict]:
    stmt = (
        select(PlayerEvaluation.player_id, Player.full_name, PlayerEvaluation.general_rating, Match.match_date)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(Player, PlayerEvaluation.player_id == Player.id)
        .where(*_valid_rival_evaluation_predicates())
        .order_by(PlayerEvaluation.player_id, Match.match_date, PlayerEvaluation.id)
    )
    if season_id:
        stmt = stmt.where(Match.season_id == season_id)
    grouped: dict[int, dict] = {}
    for pid, name, rating, observed_at in session.execute(stmt).all():
        row = grouped.setdefault(int(pid), {"player_id": int(pid), "full_name": name, "values": []})
        row["values"].append((observed_at, float(rating)))
    result = []
    for row in grouped.values():
        values = row.pop("values")
        if len(values) < min_observations:
            continue
        first = values[0][1]
        last = values[-1][1]
        result.append({**row, "observations": len(values), "first_rating": first, "last_rating": last, "delta": last - first})
    result.sort(key=lambda x: x["delta"], reverse=True)
    return result[:limit]


def load_review_queue(session: Session, *, limit: int = 30) -> list[dict]:
    reports = list_reports(session, status="submitted", limit=limit)
    if not reports:
        return []
    ids = [r.id for r in reports]
    evals = list(session.scalars(
        select(PlayerEvaluation)
        .options(joinedload(PlayerEvaluation.player), joinedload(PlayerEvaluation.participation))
        .where(PlayerEvaluation.report_id.in_(ids))
        .order_by(PlayerEvaluation.report_id, desc(PlayerEvaluation.general_rating))
    ).all())
    docs = list(session.scalars(select(Document).where(Document.report_id.in_(ids))).all())
    ev_map: dict[int, list] = defaultdict(list)
    doc_map: dict[int, list] = defaultdict(list)
    for item in evals:
        ev_map[item.report_id].append(item)
    for item in docs:
        doc_map[item.report_id].append(item)
    return [{"report": r, "evaluations": ev_map.get(r.id, []), "documents": doc_map.get(r.id, [])} for r in reports]


def league_decision_queue(session: Session, *, season_id: int | None = None, limit: int = 20) -> list[dict]:
    ranked = player_rankings(session, min_observations=2, season_id=season_id, limit=100)
    profiles = {p.player_id: p for p in list_league_profiles(session)}
    team_map = latest_player_team_map(session, [int(r["player_id"]) for r in ranked])
    result = []
    for row in ranked:
        profile = profiles.get(int(row["player_id"]))
        status = profile.decision_status if profile else "Base"
        if status in {"Descartado", "Prioritario"}:
            continue
        if row["avg_general"] < 7.5 and row["standouts"] < 2:
            continue
        confidence = confidence_from_sample(row["observations"], row["reporter_count"], row["rating_dispersion"])
        result.append({**row, **team_map.get(int(row["player_id"]), {}), "decision_status": status, "confidence": confidence, "profile": profile})
    result.sort(key=lambda x: (x["confidence"] == "Alta", x["avg_general"], x["observations"]), reverse=True)
    return result[:limit]


def load_report_workspace(session: Session, report_id: int) -> dict | None:
    """Load the editable report with two SQL round trips instead of three+ per rerun."""
    report = session.scalar(
        select(Report)
        .options(
            joinedload(Report.match).joinedload(Match.home_team),
            joinedload(Report.match).joinedload(Match.away_team),
            joinedload(Report.match).joinedload(Match.competition),
            joinedload(Report.match).joinedload(Match.season),
            joinedload(Report.own_team),
            joinedload(Report.rival_team),
            joinedload(Report.reporter),
        )
        .where(Report.id == int(report_id))
    )
    if not report:
        return None
    rows = session.execute(
        select(Participation, PlayerEvaluation)
        .outerjoin(
            PlayerEvaluation,
            and_(
                PlayerEvaluation.report_id == int(report_id),
                PlayerEvaluation.player_id == Participation.player_id,
            ),
        )
        .options(
            joinedload(Participation.player),
            joinedload(Participation.team),
            joinedload(PlayerEvaluation.player),
            joinedload(PlayerEvaluation.team),
        )
        .where(Participation.match_id == report.match_id)
        .order_by(desc(Participation.starter), Participation.order_index, Participation.id)
    ).all()
    participations = []
    evaluations = []
    seen_eval: set[int] = set()
    for part, ev in rows:
        participations.append(part)
        if ev and ev.id not in seen_eval:
            evaluations.append(ev)
            seen_eval.add(ev.id)
    return {"report": report, "participations": participations, "evaluations": evaluations}


def bulk_update_roster_entries_fast(session: Session, rows: Sequence[dict], actor_id: int) -> int:
    assert_role(session, actor_id, "admin")
    ids = [int(r["id"]) for r in rows if r.get("id") is not None]
    if not ids:
        return 0
    items = list(session.scalars(select(TeamRoster).where(TeamRoster.id.in_(ids))).all())
    by_id = {x.id: x for x in items}
    touched = 0
    for row in rows:
        item = by_id.get(int(row.get("id") or 0))
        if not item:
            continue
        item.shirt_number = row.get("shirt_number")
        item.active = bool(row.get("active", item.active))
        item.joined_at = row.get("joined_at")
        item.left_at = row.get("left_at")
        touched += 1
    audit(session, actor_id, "bulk_update_roster", "team_roster", detail=f"rows={touched}")
    session.flush()
    return touched



def lineup_identity_conflicts(
    session: Session,
    rows: Sequence[dict],
    *,
    team_id: int | None = None,
    season_id: int | None = None,
) -> list[dict]:
    """Return only ambiguous rival identities; normal lineups cost no extra UI steps.

    Context order: current team+season roster -> exact DOB when supplied -> alias/name.
    Multiple plausible global players are never silently merged.
    """
    prepared: dict[str, dict] = {}
    for raw in rows:
        name = str(raw.get("name") or raw.get("player") or "").strip()
        normalized = normalize_name(name)
        if name and normalized:
            prepared.setdefault(normalized, {"name": name, "date_of_birth": raw.get("date_of_birth")})
    if not prepared:
        return []
    names = list(prepared)
    roster_ids: set[int] = set()
    roster_by_name: dict[str, list[Player]] = defaultdict(list)
    if team_id and season_id:
        roster_rows = session.execute(
            select(TeamRoster, Player).join(Player, TeamRoster.player_id == Player.id).where(
                TeamRoster.team_id == int(team_id), TeamRoster.season_id == int(season_id), Player.active.is_(True),
                Player.normalized_name.in_(names),
            )
        ).all()
        for _, player in roster_rows:
            roster_ids.add(player.id)
            roster_by_name[player.normalized_name].append(player)
    alias_rows = session.execute(
        select(PlayerAlias.normalized_alias, Player).join(Player, PlayerAlias.player_id == Player.id).where(
            Player.active.is_(True), PlayerAlias.normalized_alias.in_(names)
        )
    ).all()
    alias_by_name: dict[str, list[Player]] = defaultdict(list)
    for alias, player in alias_rows:
        alias_by_name[str(alias)].append(player)
    global_players = list(session.scalars(select(Player).where(Player.active.is_(True), Player.normalized_name.in_(names))).all())
    global_by_name: dict[str, list[Player]] = defaultdict(list)
    for player in global_players:
        global_by_name[player.normalized_name].append(player)

    team_rows = []
    candidate_ids = {p.id for p in global_players}
    if candidate_ids:
        team_rows = session.execute(
            select(TeamRoster.player_id, Team.name, Season.name)
            .join(Team, TeamRoster.team_id == Team.id)
            .join(Season, TeamRoster.season_id == Season.id)
            .where(TeamRoster.player_id.in_(candidate_ids))
            .order_by(TeamRoster.player_id, Season.id.desc())
        ).all()
    contexts: dict[int, list[str]] = defaultdict(list)
    for pid, team_name, season_name in team_rows:
        label = f"{team_name} · {season_name}"
        if label not in contexts[int(pid)]:
            contexts[int(pid)].append(label)

    conflicts = []
    for normalized, info in prepared.items():
        contextual = roster_by_name.get(normalized, [])
        if len(contextual) == 1:
            continue
        candidates: dict[int, Player] = {}
        for player in alias_by_name.get(normalized, []) + global_by_name.get(normalized, []):
            candidates[player.id] = player
        dob = info.get("date_of_birth")
        if dob:
            try:
                dob = date.fromisoformat(str(dob)) if not isinstance(dob, date) else dob
            except Exception:
                dob = None
        if dob:
            dob_matches = [p for p in candidates.values() if p.date_of_birth == dob]
            if len(dob_matches) == 1:
                continue
            if dob_matches:
                candidates = {p.id: p for p in dob_matches}
        if len(candidates) <= 1:
            continue
        conflicts.append({
            "normalized": normalized,
            "name": info["name"],
            "candidates": [{
                "id": p.id, "full_name": p.full_name, "display_name": p.display_name,
                "date_of_birth": p.date_of_birth, "primary_position": p.primary_position,
                "contexts": contexts.get(p.id, []),
            } for p in sorted(candidates.values(), key=lambda x: x.id)],
        })
    return conflicts

def save_named_lineup_fast(
    session: Session,
    *,
    match_id: int,
    team_id: int,
    season_id: int,
    rows: Sequence[dict],
    actor_id: int,
    sync_roster: bool = True,
    identity_resolutions: dict[str, int] | None = None,
) -> list[Participation]:
    """Resolve a whole named lineup with bulk prefetches instead of one SELECT per player."""
    identity_resolutions = identity_resolutions or {}
    prepared_raw = []
    for raw in rows:
        name = str(raw.get("name") or raw.get("player") or "").strip()
        if not name:
            continue
        normalized = normalize_name(name)
        if not normalized:
            continue
        prepared_raw.append((raw, name, normalized))
    if not prepared_raw:
        raise ValueError("Añade al menos un jugador.")

    normalized_names = sorted({n for _, _, n in prepared_raw})

    # Resolve identities in the safest context first: same team + same season. This
    # avoids silently merging two homonyms from different clubs just because their
    # normalized names are equal.
    roster_candidates = list(session.execute(
        select(TeamRoster, Player)
        .join(Player, TeamRoster.player_id == Player.id)
        .where(
            TeamRoster.team_id == int(team_id),
            TeamRoster.season_id == int(season_id),
            Player.active.is_(True),
            Player.normalized_name.in_(normalized_names),
        )
    ).all())
    roster_by_name: dict[str, Player] = {player.normalized_name: player for _, player in roster_candidates}

    alias_rows = list(session.execute(
        select(PlayerAlias.normalized_alias, Player)
        .join(Player, PlayerAlias.player_id == Player.id)
        .where(Player.active.is_(True), PlayerAlias.normalized_alias.in_(normalized_names))
    ).all())
    alias_by_name: dict[str, list[Player]] = defaultdict(list)
    for alias, player in alias_rows:
        alias_by_name[str(alias)].append(player)

    global_rows = list(session.scalars(
        select(Player).where(Player.active.is_(True), Player.normalized_name.in_(normalized_names)).order_by(Player.id)
    ).all())
    global_by_name: dict[str, list[Player]] = defaultdict(list)
    for player in global_rows:
        global_by_name[player.normalized_name].append(player)

    by_normalized: dict[str, Player] = {}
    ambiguous_created: list[str] = []
    missing = []
    for raw, name, normalized in prepared_raw:
        if normalized in by_normalized:
            continue
        resolution = identity_resolutions.get(normalized)
        player = None
        if resolution is not None and int(resolution) > 0:
            player = session.get(Player, int(resolution))
            if not player or not player.active:
                raise ValueError(f"La identidad seleccionada para {name} ya no está disponible.")
        elif resolution is not None and int(resolution) == -1:
            player = None
        if player is None and resolution != -1:
            player = roster_by_name.get(normalized)
        if player is None and resolution != -1:
            alias_candidates = alias_by_name.get(normalized, [])
            if len(alias_candidates) == 1:
                player = alias_candidates[0]
        if player is None and resolution != -1:
            candidates = global_by_name.get(normalized, [])
            if len(candidates) == 1:
                player = candidates[0]
            elif len(candidates) > 1:
                # Ambiguous homonym: create a team-context record instead of merging
                # silently. Administration can merge later when identity is confirmed.
                ambiguous_created.append(name)
        if player is None:
            position = str(raw.get("position") or "Otro")
            player = Player(
                full_name=name, normalized_name=normalized, display_name=None,
                primary_position=position, active=True, created_at=UTC_NOW(), updated_at=UTC_NOW(),
            )
            session.add(player)
            missing.append(player)
        by_normalized[normalized] = player
    if missing:
        session.flush()
        detail = f"count={len(missing)}"
        if ambiguous_created:
            detail += "; ambiguous=" + ", ".join(ambiguous_created[:8])
        audit(session, actor_id, "bulk_create_players", "player", detail=detail)

    player_ids = [by_normalized[n].id for _, _, n in prepared_raw]
    existing_roster: dict[int, TeamRoster] = {}
    if sync_roster:
        roster_rows = list(session.scalars(select(TeamRoster).where(
            TeamRoster.team_id == int(team_id),
            TeamRoster.season_id == int(season_id),
            TeamRoster.player_id.in_(player_ids),
        )).all())
        existing_roster = {r.player_id: r for r in roster_rows}

    participation_rows = []
    roster_new = []
    for raw, name, normalized in prepared_raw:
        player = by_normalized[normalized]
        shirt = raw.get("shirt_number")
        if shirt == "":
            shirt = None
        try:
            shirt = int(shirt) if shirt is not None else None
        except (TypeError, ValueError):
            shirt = None
        if sync_roster:
            roster = existing_roster.get(player.id)
            if roster:
                if shirt is not None:
                    roster.shirt_number = shirt
                roster.active = True
            else:
                roster = TeamRoster(
                    team_id=int(team_id),
                    season_id=int(season_id),
                    player_id=player.id,
                    shirt_number=shirt,
                    active=True,
                )
                session.add(roster)
                existing_roster[player.id] = roster
                roster_new.append(roster)
        starter = bool(raw.get("starter", False))
        minute_in = int(raw.get("minute_in", 0) or 0)
        minute_out = int(raw.get("minute_out", 90) or 90)
        if starter:
            minute_in = 0
        participation_rows.append({
            "selected": True,
            "player_id": player.id,
            "shirt_number": shirt,
            "starter": starter,
            "position": str(raw.get("position") or player.primary_position or "Otro"),
            "minute_in": minute_in,
            "minute_out": minute_out,
            "captain": bool(raw.get("captain", False)),
        })
    if roster_new:
        session.flush()
    return replace_participations(session, match_id, team_id, participation_rows, actor_id)


def bulk_update_scouting_list_items(session: Session, list_id: int, rows: Sequence[dict], actor_id: int) -> int:
    assert_role(session, actor_id, "director", "admin")
    items = list(session.scalars(select(ScoutingListItem).where(ScoutingListItem.list_id == int(list_id))).all())
    by_player = {int(i.player_id): i for i in items}
    touched = 0
    for row in rows:
        item = by_player.get(int(row.get("player_id") or 0))
        if not item:
            continue
        item.position = row.get("position") or item.position
        item.order_index = int(row.get("order_index") or 0)
        item.note = str(row.get("note") or "").strip() or None
        touched += 1
    audit(session, actor_id, "bulk_update_scouting_list", "scouting_list", int(list_id), detail=f"rows={touched}")
    session.flush()
    return touched
