from __future__ import annotations

from repositories.data_governance import official_match_clause

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

from repositories.users import assert_role, get_all_settings, get_setting, user_has_role
from repositories.matches import _own_team_id_for_match, get_match, get_participations

def _assert_report_owner_or_privileged(session: Session, report: Report, actor_id: int) -> User:
    actor = assert_role(session, actor_id)
    # 4.2.2: writing/rating a postmatch is an Informador capability. Admin and
    # Dirección Deportiva may review/approve through their dedicated actions,
    # but they do not inherit report-writing rights merely from those roles.
    if not user_has_role(session, actor_id, "reporter"):
        raise PermissionError("Para valorar o editar un postpartido necesitas el rol Informador.")
    if actor.id != report.reporter_id and not user_has_role(session, actor_id, "admin", "director"):
        raise PermissionError("No puedes modificar un informe de otro usuario.")
    return actor


def report_for_user(session: Session, match_id: int, reporter_id: int) -> Report | None:
    return session.scalar(select(Report).options(joinedload(Report.match), joinedload(Report.reporter), joinedload(Report.own_team), joinedload(Report.rival_team)).where(and_(Report.match_id == match_id, Report.reporter_id == reporter_id)))


def get_or_create_report(session: Session, match_id: int, reporter_id: int, actor_role: str | None = None) -> Report:
    user = session.get(User, reporter_id)
    if not user or not user.active:
        raise ValueError("Partido o usuario no válido.")
    if not user_has_role(session, reporter_id, "reporter"):
        raise PermissionError("Para crear o completar un postpartido necesitas el rol Informador.")
    existing = report_for_user(session, match_id, reporter_id)
    if existing:
        return existing
    match = get_match(session, match_id)
    if not match:
        raise ValueError("Partido o usuario no válido.")
    # New 3.7 workflows cannot start an evaluation from a merely provisional fixture.
    # Historical/published legacy reports remain readable because existing reports
    # return above and old published data is not invalidated retroactively.
    if match.status in {"draft", "scheduled"} and (match.schedule_status != "confirmed" or not match.kickoff_at):
        raise ValueError("El horario del partido todavía no está confirmado. Administración debe fijar fecha y hora antes de iniciar el informe.")
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


def save_report_summary(session: Session, report_id: int, *, rival_level: str | None, opponent_overview: str | None, own_team_note: str | None, key_takeaways: str | None, standout_player_id: int | None, actor_id: int | None = None, expected_revision: int | None = None, own_team_rating: float | None = None, rival_team_rating: float | None = None) -> Report:
    report = session.get(Report, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    actor_id = actor_id or report.reporter_id
    _assert_report_owner_or_privileged(session, report, actor_id)
    if report.status not in {"draft", "returned"}:
        raise ValueError("El informe está bloqueado.")
    if expected_revision is not None and report.revision != expected_revision:
        raise RuntimeError("El informe se ha modificado en otra pestaña. Recarga antes de guardar.")
    before = _snapshot(report, ["rival_level", "own_team_rating", "rival_team_rating", "opponent_overview", "own_team_note", "key_takeaways", "standout_player_id", "revision"])
    report.rival_level = rival_level
    report.own_team_rating = float(own_team_rating) if own_team_rating is not None and float(own_team_rating) > 0 else None
    report.rival_team_rating = float(rival_team_rating) if rival_team_rating is not None and float(rival_team_rating) > 0 else None
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


def bulk_upsert_evaluations_fast(session: Session, report_id: int, rows: Sequence[dict], actor_id: int) -> int:
    """Persist a complete team with a single SQL UPSERT on PostgreSQL/SQLite.

    Concurrency revisions are checked once, then every evaluation is inserted/updated
    in one statement. This removes the ORM-per-player flush pattern on the hottest
    remote-write path while preserving audit and report revision semantics.
    """
    report = session.get(Report, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    _assert_report_owner_or_privileged(session, report, actor_id)
    if report.status not in {"draft", "returned"}:
        raise ValueError("El informe está bloqueado y no puede editarse.")
    if not rows:
        return 0

    player_ids = [int(r["player_id"]) for r in rows]
    existing = {
        int(pid): int(rev or 0)
        for pid, rev in session.execute(
            select(PlayerEvaluation.player_id, PlayerEvaluation.revision).where(
                PlayerEvaluation.report_id == int(report_id),
                PlayerEvaluation.player_id.in_(player_ids),
            )
        ).all()
    }
    now = UTC_NOW()
    values = []
    for row in rows:
        player_id = int(row["player_id"])
        current_revision = existing.get(player_id, 0)
        expected = row.get("expected_revision")
        if expected is not None and current_revision != int(expected):
            raise RuntimeError("Una valoración ha cambiado en otra sesión. Recarga el informe antes de guardar el bloque.")
        team_id = int(row["team_id"])
        status = str(row.get("observation_status") or "not_observed")
        evaluated = status == "evaluated"
        values.append({
            "report_id": int(report_id),
            "player_id": player_id,
            "team_id": team_id,
            "participation_id": row.get("participation_id"),
            "evaluation_scope": "rival" if team_id == int(report.rival_team_id) else "own",
            "observation_status": status,
            "general_rating": row.get("general_rating") if evaluated else None,
            "technical_rating": row.get("technical_rating") if evaluated else None,
            "tactical_rating": row.get("tactical_rating") if evaluated else None,
            "physical_rating": row.get("physical_rating") if evaluated else None,
            "confidence": row.get("confidence") if evaluated else None,
            "recommendation": row.get("recommendation") if evaluated else None,
            "strengths": json.dumps(row.get("strengths"), ensure_ascii=False) if isinstance(row.get("strengths"), (list, tuple)) else row.get("strengths"),
            "short_note": row.get("short_note"),
            "detailed_note": row.get("detailed_note"),
            "standout": bool(row.get("standout", False)) if evaluated else False,
            "pdf_include": bool(row.get("pdf_include", True)),
            "revision": current_revision + 1,
            "created_at": now,
            "updated_at": now,
        })

    table = PlayerEvaluation.__table__
    dialect = session.get_bind().dialect.name
    insert_factory = pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert_factory is None:
        # Conservative fallback for any unsupported SQLAlchemy dialect.
        for value in values:
            item = session.scalar(select(PlayerEvaluation).where(PlayerEvaluation.report_id == report_id, PlayerEvaluation.player_id == value["player_id"]))
            if item is None:
                item = PlayerEvaluation(**value)
                session.add(item)
            else:
                for key, val in value.items():
                    if key not in {"report_id", "player_id", "created_at"}:
                        setattr(item, key, val)
    else:
        stmt = insert_factory(table).values(values)
        excluded = stmt.excluded
        update_cols = {
            key: getattr(excluded, key)
            for key in values[0]
            if key not in {"report_id", "player_id", "created_at"}
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.report_id, table.c.player_id],
            set_=update_cols,
        )
        session.execute(stmt)

    # When the rival block is saved it contains the whole rival squad, so MVP can
    # be resolved directly from the submitted payload without another SELECT.
    rival_rows = [v for v in values if v["evaluation_scope"] == "rival"]
    if rival_rows:
        candidates = [v for v in rival_rows if v["observation_status"] == "evaluated" and v["general_rating"] is not None and v["standout"]]
        candidates.sort(key=lambda v: (float(v["general_rating"]), -int(v["player_id"])), reverse=True)
        report.standout_player_id = candidates[0]["player_id"] if candidates else None
    report.revision = int(report.revision or 0) + 1
    report.updated_at = now
    audit(session, actor_id, "bulk_upsert_evaluations", "report", report_id, detail=f"players={len(values)}; sql_upsert=true")
    session.flush()
    return len(values)


def bulk_upsert_evaluations(session: Session, report_id: int, rows: Sequence[dict], actor_id: int) -> int:
    # Backward-compatible entrypoint now uses the optimized batch implementation.
    return bulk_upsert_evaluations_fast(session, report_id, rows, actor_id)


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
        "report": {k: getattr(report, k) for k in ["id", "match_id", "reporter_id", "own_team_id", "rival_team_id", "status", "rival_level", "own_team_rating", "rival_team_rating", "opponent_overview", "own_team_note", "key_takeaways", "standout_player_id", "version", "created_at", "updated_at", "submitted_at", "approved_at"]},
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
    # 4.2.3: a delivered report becomes official immediately, no DD approval.
    # Historical submitted/approved/final records are never bulk-mutated.
    report.status = "incorporated"
    report.submitted_at = UTC_NOW()
    report.finalized_at = report.submitted_at
    report.approved_at = None
    report.reviewer_id = None
    version = create_report_version(session, report_id, actor_id, report.status)
    assignment = session.scalar(select(ReportAssignment).where(and_(ReportAssignment.match_id == report.match_id, ReportAssignment.user_id == report.reporter_id)))
    if assignment:
        assignment.status = "incorporated"
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
    if report.status not in {"submitted", "incorporated"}:
        raise ValueError("Solo se pueden revisar informes históricos entregados o incorporados.")
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
    if not report or report.status not in {"submitted", "approved", "final", "incorporated"}:
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


def reopen_report(session: Session, report_id: int, actor_id: int, reason: str) -> Report:
    assert_role(session, actor_id, "admin")
    if not reason or not reason.strip():
        raise ValueError("Indica el motivo de la corrección.")
    return return_report(session, report_id, actor_id, reason.strip())


def list_reports(session: Session, reporter_id: int | None = None, status: str | None = None, limit: int | None = None, match_id: int | None = None, season_id: int | None = None, competition_id: int | None = None, rival_team_id: int | None = None, offset: int = 0) -> list[Report]:
    stmt = select(Report).options(joinedload(Report.match).joinedload(Match.home_team), joinedload(Report.match).joinedload(Match.away_team), joinedload(Report.match).joinedload(Match.competition), joinedload(Report.match).joinedload(Match.season), joinedload(Report.reporter), joinedload(Report.reviewer), joinedload(Report.rival_team), joinedload(Report.own_team))
    stmt = stmt.where(Report.match_id.in_(select(Match.id).where(official_match_clause())))
    if reporter_id:
        stmt = stmt.where(Report.reporter_id == reporter_id)
    if status:
        stmt = stmt.where(Report.status == status)
    if match_id:
        stmt = stmt.where(Report.match_id == match_id)
    if rival_team_id:
        stmt = stmt.where(Report.rival_team_id == rival_team_id)
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
