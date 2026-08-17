from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import and_, asc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from core.utils import normalize_name
from models.entities import Competition, Match, Season, Team
from repositories.common import UTC_NOW, audit
from repositories.users import assert_role


def _team_by_name(session: Session, name: str) -> Team | None:
    normalized = normalize_name(name)
    for team in session.scalars(select(Team).where(Team.active.is_(True))).all():
        if normalize_name(team.name) == normalized or (team.short_name and normalize_name(team.short_name) == normalized):
            return team
    return None


def ensure_team(session: Session, name: str, actor_id: int) -> Team:
    team = _team_by_name(session, name)
    if team:
        return team
    team = Team(name=name.strip(), short_name=None, country=None, is_own_team=False, active=True, created_at=UTC_NOW(), updated_at=UTC_NOW())
    session.add(team)
    session.flush()
    audit(session, actor_id, "calendar_create_team", "team", team.id, detail=name.strip())
    return team


def import_fixtures(
    session: Session,
    *,
    season_id: int,
    competition_id: int,
    rows: Sequence[dict],
    actor_id: int,
    fixture_type: str = "league",
) -> dict:
    assert_role(session, actor_id, "admin")
    season = session.get(Season, int(season_id))
    competition = session.get(Competition, int(competition_id))
    if not season or not competition:
        raise ValueError("Temporada o competición no disponible.")
    created = updated = 0
    touched_ids: list[int] = []
    for row in rows:
        home = ensure_team(session, row["home_team"], actor_id)
        away = ensure_team(session, row["away_team"], actor_id)
        if home.id == away.id:
            raise ValueError(f"Partido inválido: {home.name} contra sí mismo.")
        existing = session.scalar(
            select(Match).where(
                Match.season_id == int(season_id), Match.competition_id == int(competition_id),
                Match.round_name == str(row["round_name"]), Match.home_team_id == home.id, Match.away_team_id == away.id,
                Match.deleted_at.is_(None),
            )
        )
        if existing is None:
            existing = Match(
                season_id=int(season_id), competition_id=int(competition_id), round_name=str(row["round_name"]),
                match_date=row["match_date"], window_start=row.get("window_start"), window_end=row.get("window_end"),
                kickoff_at=row.get("kickoff_at"), schedule_status=row.get("schedule_status") or "window",
                fixture_type=fixture_type, home_team_id=home.id, away_team_id=away.id,
                venue=row.get("venue"), status="scheduled", created_by=int(actor_id), created_at=UTC_NOW(), updated_at=UTC_NOW(),
            )
            session.add(existing)
            session.flush()
            created += 1
        else:
            existing.match_date = row["match_date"]
            existing.window_start = row.get("window_start")
            existing.window_end = row.get("window_end")
            existing.kickoff_at = row.get("kickoff_at")
            existing.schedule_status = row.get("schedule_status") or existing.schedule_status
            existing.fixture_type = fixture_type
            if row.get("venue"):
                existing.venue = row.get("venue")
            existing.updated_at = UTC_NOW()
            existing.revision = int(existing.revision or 0) + 1
            updated += 1
        touched_ids.append(existing.id)
    audit(session, actor_id, "import_league_calendar", "match", detail=f"created={created}; updated={updated}; rows={len(rows)}")
    return {"created": created, "updated": updated, "rows": len(rows), "match_ids": touched_ids}


def list_calendar(
    session: Session,
    *,
    season_id: int | None = None,
    competition_id: int | None = None,
    team_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 500,
) -> list[Match]:
    stmt = select(Match).options(
        joinedload(Match.home_team), joinedload(Match.away_team), joinedload(Match.season), joinedload(Match.competition)
    ).where(Match.deleted_at.is_(None), Match.status != "archived")
    if season_id:
        stmt = stmt.where(Match.season_id == int(season_id))
    if competition_id:
        stmt = stmt.where(Match.competition_id == int(competition_id))
    if team_id:
        stmt = stmt.where(or_(Match.home_team_id == int(team_id), Match.away_team_id == int(team_id)))
    if date_from:
        stmt = stmt.where(func.coalesce(Match.window_end, Match.match_date) >= date_from)
    if date_to:
        stmt = stmt.where(func.coalesce(Match.window_start, Match.match_date) <= date_to)
    return list(session.scalars(stmt.order_by(asc(func.coalesce(Match.kickoff_at, Match.window_start, Match.match_date)), Match.id).limit(int(limit))).unique().all())


def schedule_label(match: Match) -> str:
    if match.schedule_status == "confirmed" and match.kickoff_at:
        return match.kickoff_at.strftime("%d/%m/%Y · %H:%M")
    if match.schedule_status == "date_confirmed":
        return f"{match.match_date.strftime('%d/%m/%Y')} · hora pendiente"
    if match.window_start and match.window_end and match.window_start != match.window_end:
        return f"{match.window_start.strftime('%d/%m')}–{match.window_end.strftime('%d/%m/%Y')} · horario pendiente"
    return f"{match.match_date.strftime('%d/%m/%Y')} · horario pendiente"


def schedule_issues(session: Session, *, season_id: int | None = None, today: date | None = None, horizon_days: int = 21) -> list[dict]:
    today = today or date.today()
    rows = list_calendar(session, season_id=season_id, date_from=today, date_to=today + timedelta(days=horizon_days), limit=300)
    result: list[dict] = []
    for match in rows:
        if match.schedule_status in {"confirmed", "cancelled"}:
            continue
        start = match.window_start or match.match_date
        days = (start - today).days
        urgency = "Urgente" if days <= 7 else "Pendiente"
        result.append({"match": match, "days": days, "urgency": urgency, "reason": "Horario sin confirmar" if match.schedule_status != "postponed" else "Partido aplazado"})
    return result


def update_schedule(
    session: Session,
    match_id: int,
    actor_id: int,
    *,
    definitive_date: date | None = None,
    kickoff_at: datetime | None = None,
    schedule_status: str | None = None,
    venue: str | None = None,
) -> Match:
    assert_role(session, actor_id, "admin")
    match = session.get(Match, int(match_id))
    if not match:
        raise ValueError("Partido no encontrado.")
    before = {"match_date": str(match.match_date), "kickoff_at": str(match.kickoff_at), "schedule_status": match.schedule_status, "venue": match.venue}
    if definitive_date:
        match.match_date = definitive_date
        match.window_start = definitive_date
        match.window_end = definitive_date
    if kickoff_at is not None:
        match.kickoff_at = kickoff_at
        match.match_date = kickoff_at.date()
        match.window_start = kickoff_at.date()
        match.window_end = kickoff_at.date()
        match.schedule_status = "confirmed"
    elif schedule_status:
        match.schedule_status = schedule_status
    elif definitive_date:
        match.schedule_status = "date_confirmed"
    if venue is not None:
        match.venue = venue.strip() or None
    match.revision = int(match.revision or 0) + 1
    match.updated_at = UTC_NOW()
    audit(session, actor_id, "update_fixture_schedule", "match", match.id, before=before, after={"match_date": str(match.match_date), "kickoff_at": str(match.kickoff_at), "schedule_status": match.schedule_status, "venue": match.venue})
    return match


def own_matches(session: Session, own_team_id: int, *, season_id: int | None = None, future_only: bool = False) -> list[Match]:
    return list_calendar(session, season_id=season_id, team_id=own_team_id, date_from=date.today() if future_only else None)
