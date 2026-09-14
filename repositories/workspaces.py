from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time
import re

from sqlalchemy import and_, asc, case as sa_case, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload, load_only

from core.clock import local_today

from models.entities import (
    Match, Player, PlayerEvaluation, PlayerSeasonDecision, Report, ReportAssignment,
    ScoutMission, ScoutMissionTarget, ScoutObservation, Season, SquadNeed, Team,
    TeamRoster,
)
from repositories import planning as planning_repo
from repositories import player_report as player_report_repo
from repositories import players as players_repo


def _round_key(value: str | None) -> tuple:
    text = str(value or "")
    nums = re.findall(r"\d+", text)
    return (int(nums[0]) if nums else 10**9, text.casefold())


def list_rounds(session: Session, season_id: int, competition_id: int | None = None) -> list[str]:
    stmt = select(Match.round_name).where(
        Match.season_id == int(season_id), Match.deleted_at.is_(None), Match.status != "archived"
    ).distinct()
    if competition_id:
        stmt = stmt.where(Match.competition_id == int(competition_id))
    return sorted([str(x) for x in session.scalars(stmt).all() if x], key=_round_key)


def default_round(session: Session, season_id: int, own_team_id: int | None = None) -> str | None:
    today = local_today()
    stmt = select(Match).where(
        Match.season_id == int(season_id), Match.deleted_at.is_(None), Match.status != "archived",
        Match.match_date >= today,
    )
    if own_team_id:
        stmt = stmt.where(or_(Match.home_team_id == int(own_team_id), Match.away_team_id == int(own_team_id)))
    row = session.scalar(stmt.order_by(Match.match_date, Match.kickoff_at.nullslast(), Match.id).limit(1))
    if row:
        return row.round_name
    row = session.scalar(
        select(Match).where(Match.season_id == int(season_id), Match.deleted_at.is_(None), Match.status != "archived")
        .order_by(desc(Match.match_date), desc(Match.id)).limit(1)
    )
    return row.round_name if row else None


def load_round_workspace(session: Session, *, season_id: int, round_name: str, user_id: int | None = None) -> dict:
    own = players_repo.get_own_team(session)
    matches = list(session.scalars(
        select(Match).options(
            joinedload(Match.home_team), joinedload(Match.away_team),
            joinedload(Match.competition), joinedload(Match.season),
        ).where(
            Match.season_id == int(season_id), Match.round_name == str(round_name),
            Match.deleted_at.is_(None), Match.status != "archived",
        ).order_by(Match.match_date, Match.kickoff_at.nullslast(), Match.id)
    ).unique().all())
    match_ids = [m.id for m in matches]
    mission_counts: dict[int, int] = defaultdict(int)
    my_mission_counts: dict[int, int] = defaultdict(int)
    assignment_counts: dict[int, dict] = defaultdict(lambda: {"total": 0, "pending": 0, "submitted": 0, "approved": 0})
    if match_ids:
        mission_rows = session.execute(
            select(ScoutMission.match_id, ScoutMission.assigned_to, func.count(ScoutMission.id))
            .where(ScoutMission.match_id.in_(match_ids), ScoutMission.status.in_(["pending", "in_progress"]))
            .group_by(ScoutMission.match_id, ScoutMission.assigned_to)
        ).all()
        for match_id, assignee, count in mission_rows:
            mission_counts[int(match_id)] += int(count or 0)
            if user_id and int(assignee) == int(user_id):
                my_mission_counts[int(match_id)] += int(count or 0)
        for match_id, status, required in session.execute(
            select(ReportAssignment.match_id, ReportAssignment.status, ReportAssignment.required)
            .where(ReportAssignment.match_id.in_(match_ids))
        ).all():
            bucket = assignment_counts[int(match_id)]
            if required:
                bucket["total"] += 1
            if status in bucket:
                bucket[status] += 1
            elif status in {"pending", "in_progress", "returned"}:
                bucket["pending"] += 1
    ordered = sorted(matches, key=lambda m: (0 if own and own.id in {m.home_team_id, m.away_team_id} else 1, m.match_date, m.id))
    return {
        "own_team": own,
        "matches": ordered,
        "mission_counts": dict(mission_counts),
        "my_mission_counts": dict(my_mission_counts),
        "assignment_counts": dict(assignment_counts),
    }


def load_match_workspace(session: Session, *, match_id: int, user_id: int | None = None) -> dict:
    match = session.scalar(
        select(Match).options(
            joinedload(Match.home_team), joinedload(Match.away_team), joinedload(Match.competition), joinedload(Match.season)
        ).where(Match.id == int(match_id), Match.deleted_at.is_(None))
    )
    if not match:
        raise ValueError("Partido no encontrado.")
    own = players_repo.get_own_team(session)
    missions = planning_repo.list_missions(session, match_id=match.id, limit=100)
    target_rows = list(session.scalars(
        select(ScoutMissionTarget).options(joinedload(ScoutMissionTarget.player))
        .where(ScoutMissionTarget.mission_id.in_([m.id for m in missions] or [-1]))
    ).unique().all())
    targets_by_mission: dict[int, list] = defaultdict(list)
    for target in target_rows:
        targets_by_mission[target.mission_id].append(target)
    assignments = list(session.scalars(
        select(ReportAssignment).options(joinedload(ReportAssignment.user))
        .where(ReportAssignment.match_id == match.id).order_by(ReportAssignment.id)
    ).unique().all())
    reports = list(session.scalars(
        select(Report).options(joinedload(Report.reporter)).where(Report.match_id == match.id).order_by(Report.id)
    ).unique().all())
    report_by_user = {r.reporter_id: r for r in reports}
    participations = []
    from models.entities import Participation
    participations = list(session.scalars(
        select(Participation).options(joinedload(Participation.player), joinedload(Participation.team))
        .where(Participation.match_id == match.id)
        .order_by(Participation.team_id, Participation.starter.desc(), Participation.order_index)
    ).unique().all())
    return {
        "match": match,
        "own_team": own,
        "is_own_match": bool(own and own.id in {match.home_team_id, match.away_team_id}),
        "missions": missions,
        "targets_by_mission": dict(targets_by_mission),
        "assignments": assignments,
        "reports": reports,
        "report_by_user": report_by_user,
        "participations": participations,
        "my_missions": [m for m in missions if user_id and m.assigned_to == int(user_id)],
        "my_assignment": next((a for a in assignments if user_id and a.user_id == int(user_id)), None),
    }


def _next_own_match(session: Session, own_team_id: int, season_id: int) -> Match | None:
    today = local_today()
    # Home needs only fixture identity/schedule/result and the two team names.
    # Do not hydrate every Match/Competition column here: production databases
    # upgraded across many historical releases may temporarily contain optional
    # legacy gaps, and an unnecessary joinedload used to turn those into a hard
    # startup ProgrammingError.
    return session.scalar(
        select(Match).options(
            load_only(
                Match.id, Match.season_id, Match.round_name, Match.match_date,
                Match.kickoff_at, Match.schedule_status, Match.home_team_id,
                Match.away_team_id, Match.home_score, Match.away_score,
                Match.status, Match.deleted_at,
            ),
            joinedload(Match.home_team).load_only(Team.id, Team.name),
            joinedload(Match.away_team).load_only(Team.id, Team.name),
        )
        .where(
            Match.season_id == int(season_id), Match.deleted_at.is_(None), Match.status != "archived",
            Match.match_date >= today,
            or_(Match.home_team_id == int(own_team_id), Match.away_team_id == int(own_team_id)),
        ).order_by(Match.match_date, Match.kickoff_at.nullslast(), Match.id).limit(1)
    )


def load_home_workspace(session: Session, *, user_id: int, roles: set[str]) -> dict:
    active = players_repo.get_active_season(session)
    own = players_repo.get_own_team(session)
    next_match = _next_own_match(session, own.id, active.id) if active and own else None

    tasks: list[dict] = []
    if "admin" in roles and active:
        # One focused query: only future provisional matches in the next 21 days.
        today = local_today()
        end = date.fromordinal(today.toordinal() + 21)
        issues = list(session.scalars(
            select(Match).options(joinedload(Match.home_team), joinedload(Match.away_team))
            .where(
                Match.season_id == active.id, Match.deleted_at.is_(None), Match.match_date >= today, Match.match_date <= end,
                Match.schedule_status.notin_(["confirmed", "cancelled"]),
            ).order_by(Match.match_date, Match.id).limit(20)
        ).unique().all())
        for m in issues:
            tasks.append({"kind": "schedule", "severity": "action" if (m.match_date-today).days <= 7 else "pending", "title": f"Confirmar horario · {m.home_team.name} - {m.away_team.name}", "match_id": m.id, "due": m.match_date})

    if "scout" in roles:
        missions = planning_repo.list_missions(session, assigned_to=user_id, limit=30)
        for m in missions:
            if m.status not in {"pending", "in_progress"}:
                continue
            targets = planning_repo.mission_targets(session, m.id)
            target_name = targets[0].player.full_name if len(targets) == 1 else (f"{len(targets)} jugadores" if targets else m.target_team.name if m.target_team else "partido")
            tasks.append({"kind": "scout", "severity": "action" if m.status == "in_progress" else "pending", "title": f"Observar · {target_name}", "match_id": m.match_id, "mission_id": m.id, "due": m.due_at or m.match.match_date})

    if roles.intersection({"reporter", "director", "admin"}):
        assignments = list(session.scalars(
            select(ReportAssignment).options(joinedload(ReportAssignment.match).joinedload(Match.home_team), joinedload(ReportAssignment.match).joinedload(Match.away_team))
            .where(ReportAssignment.user_id == int(user_id), ReportAssignment.status.in_(["pending", "in_progress", "returned"]))
            .order_by(ReportAssignment.due_at.nullslast(), desc(ReportAssignment.created_at)).limit(20)
        ).unique().all())
        for a in assignments:
            tasks.append({"kind": "report", "severity": "action" if a.status == "returned" else "pending", "title": f"Informe · {a.match.home_team.name} - {a.match.away_team.name}", "match_id": a.match_id, "due": a.due_at or a.match.match_date})

    director = {"decision_count": 0, "high_needs": 0, "new_scout": 0}
    if active and "director" in roles:
        director["decision_count"] = int(session.scalar(
            select(func.count(PlayerSeasonDecision.id)).where(PlayerSeasonDecision.season_id == active.id, PlayerSeasonDecision.status.in_(["Base", "Observado", "Interesante"]))
        ) or 0)
        director["high_needs"] = int(session.scalar(
            select(func.count(SquadNeed.id)).where(SquadNeed.season_id == active.id, SquadNeed.need_level == "Alta")
        ) or 0)
        director["new_scout"] = int(session.scalar(
            select(func.count(ScoutObservation.id)).join(Match, ScoutObservation.match_id == Match.id, isouter=True)
            .where(ScoutObservation.status == "submitted", or_(Match.season_id == active.id, ScoutObservation.match_id.is_(None)))
        ) or 0)

    def due_key(row: dict):
        value = row.get("due")
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.max)
        return datetime.max

    tasks.sort(key=lambda row: (0 if row["severity"] == "action" else 1, due_key(row), row["title"]))
    return {"active_season": active, "own_team": own, "next_match": next_match, "is_matchday": bool(next_match and next_match.match_date == local_today()), "tasks": tasks[:25], "director": director}


def load_player_workspace(session: Session, *, player_id: int, season_id: int | None) -> dict:
    payload = player_report_repo.build_player_report_360(session, int(player_id), season_id=season_id)
    missions = []
    if season_id:
        missions = list(session.scalars(
            select(ScoutMission).options(
                joinedload(ScoutMission.match).joinedload(Match.home_team),
                joinedload(ScoutMission.match).joinedload(Match.away_team),
                joinedload(ScoutMission.assignee),
            ).join(ScoutMissionTarget, ScoutMissionTarget.mission_id == ScoutMission.id)
            .where(ScoutMissionTarget.player_id == int(player_id), ScoutMission.status.in_(["pending", "in_progress"]))
            .order_by(ScoutMission.due_at.nullslast(), ScoutMission.id)
        ).unique().all())
    payload["next_action"] = missions[0] if missions else None
    return payload


def candidate_next_matches(session: Session, *, player_id: int, season_id: int, limit: int = 12) -> list[Match]:
    roster = session.scalar(
        select(TeamRoster).where(
            TeamRoster.player_id == int(player_id), TeamRoster.season_id == int(season_id), TeamRoster.active.is_(True)
        ).order_by(desc(TeamRoster.updated_at)).limit(1)
    )
    if not roster:
        return []
    return list(session.scalars(
        select(Match).options(joinedload(Match.home_team), joinedload(Match.away_team))
        .where(
            Match.season_id == int(season_id), Match.deleted_at.is_(None), Match.match_date >= local_today(),
            or_(Match.home_team_id == roster.team_id, Match.away_team_id == roster.team_id),
        ).order_by(Match.match_date, Match.kickoff_at.nullslast(), Match.id).limit(int(limit))
    ).unique().all())


def list_player_cards(
    session: Session, *, season_id: int | None, search: str | None = None,
    position: str | None = None, state_filter: str = "Todos", limit: int = 120,
) -> list[dict]:
    from models.entities import ScoutedPlayerProfile
    from repositories.common import FINAL_REPORT_STATUSES

    stmt = select(Player).where(Player.active.is_(True), Player.merged_into_id.is_(None))
    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Player.full_name.ilike(q), Player.display_name.ilike(q)))
    if position:
        stmt = stmt.where(Player.primary_position == position)
    players = list(session.scalars(stmt.order_by(Player.full_name).limit(max(int(limit) * 3, 200))).all())
    ids = [p.id for p in players]
    if not ids:
        return []

    decisions: dict[int, PlayerSeasonDecision] = {}
    if season_id:
        decisions = {d.player_id: d for d in session.scalars(
            select(PlayerSeasonDecision).options(joinedload(PlayerSeasonDecision.model_role))
            .where(PlayerSeasonDecision.season_id == int(season_id), PlayerSeasonDecision.player_id.in_(ids))
        ).unique().all()}

    roster_map: dict[int, TeamRoster] = {}
    roster_stmt = select(TeamRoster).options(joinedload(TeamRoster.team)).where(TeamRoster.player_id.in_(ids), TeamRoster.active.is_(True))
    if season_id:
        roster_stmt = roster_stmt.where(TeamRoster.season_id == int(season_id))
    for roster in session.scalars(roster_stmt.order_by(desc(TeamRoster.updated_at))).unique().all():
        roster_map.setdefault(roster.player_id, roster)

    scout_counts: dict[int, int] = defaultdict(int)
    scout_rows = session.execute(
        select(ScoutedPlayerProfile.player_id, func.count(ScoutObservation.id))
        .join(ScoutObservation, ScoutObservation.profile_id == ScoutedPlayerProfile.id)
        .where(ScoutedPlayerProfile.player_id.in_(ids), ScoutObservation.status == "submitted")
        .group_by(ScoutedPlayerProfile.player_id)
    ).all()
    for pid, count in scout_rows:
        scout_counts[int(pid)] = int(count or 0)

    rating_map: dict[int, tuple[float | None, int, int]] = {}
    rating_rows = session.execute(
        select(
            PlayerEvaluation.player_id, func.avg(PlayerEvaluation.general_rating),
            func.count(PlayerEvaluation.id),
            func.sum(sa_case((PlayerEvaluation.standout.is_(True), 1), else_=0)),
        )
        .join(Report, Report.id == PlayerEvaluation.report_id)
        .join(Match, Match.id == Report.match_id)
        .where(
            PlayerEvaluation.player_id.in_(ids), PlayerEvaluation.evaluation_scope == "rival",
            PlayerEvaluation.observation_status == "evaluated", PlayerEvaluation.general_rating.is_not(None),
            Report.status.in_(FINAL_REPORT_STATUSES),
        )
        .group_by(PlayerEvaluation.player_id)
    ).all()
    for pid, avg, count, standouts in rating_rows:
        rating_map[int(pid)] = (round(float(avg), 2) if avg is not None else None, int(count or 0), int(standouts or 0))

    from core.presentation import normalize_player_state
    rows = []
    for player in players:
        decision = decisions.get(player.id)
        state = normalize_player_state(decision.status if decision else None)
        avg, obs_count, standout_count = rating_map.get(player.id, (None, 0, 0))
        scouts = scout_counts.get(player.id, 0)
        if state_filter == "Destacados" and standout_count <= 0:
            continue
        if state_filter == "Seguimiento" and state != "Seguimiento":
            continue
        if state_filter == "Scout" and scouts <= 0:
            continue
        if state_filter == "Prioritarios" and state != "Prioritario":
            continue
        if state_filter == "Descartados" and state != "Descartado":
            continue
        roster = roster_map.get(player.id)
        rows.append({
            "player": player, "decision": decision, "state": state,
            "team": roster.team if roster else None, "rating": avg,
            "postmatch_count": obs_count, "scout_count": scouts,
            "standouts": standout_count,
        })
        if len(rows) >= int(limit):
            break
    return rows


def match_candidate_players(session: Session, match_id: int) -> list[Player]:
    from models.entities import Participation
    match = session.get(Match, int(match_id))
    if not match:
        return []
    participation_players = list(session.scalars(
        select(Player).join(Participation, Participation.player_id == Player.id)
        .where(Participation.match_id == match.id).order_by(Player.full_name)
    ).unique().all())
    if participation_players:
        return participation_players
    return list(session.scalars(
        select(Player).join(TeamRoster, TeamRoster.player_id == Player.id)
        .where(
            TeamRoster.season_id == match.season_id, TeamRoster.active.is_(True),
            TeamRoster.team_id.in_([match.home_team_id, match.away_team_id]),
            Player.active.is_(True), Player.merged_into_id.is_(None),
        ).order_by(Player.full_name)
    ).unique().all())


def load_team_workspace(session: Session, *, team_id: int, season_id: int | None) -> dict:
    from models.entities import Participation
    team = session.get(Team, int(team_id))
    if not team:
        raise ValueError("Equipo no encontrado.")
    own = players_repo.get_own_team(session)
    roster = []
    if season_id:
        roster = players_repo.get_roster(session, team.id, int(season_id))
    player_ids = [r.player_id for r in roster]
    decisions = {}
    if season_id and player_ids:
        decisions = {d.player_id:d for d in session.scalars(
            select(PlayerSeasonDecision).where(PlayerSeasonDecision.season_id==int(season_id), PlayerSeasonDecision.player_id.in_(player_ids))
        ).all()}
    next_vs_own = None
    if own and season_id:
        next_vs_own = session.scalar(
            select(Match).options(joinedload(Match.home_team),joinedload(Match.away_team),joinedload(Match.competition))
            .where(Match.season_id==int(season_id),Match.deleted_at.is_(None),Match.match_date>=local_today(),
                   or_(and_(Match.home_team_id==own.id,Match.away_team_id==team.id),and_(Match.home_team_id==team.id,Match.away_team_id==own.id)))
            .order_by(Match.match_date,Match.kickoff_at.nullslast()).limit(1)
        )
    last_match = session.scalar(
        select(Match).options(joinedload(Match.home_team),joinedload(Match.away_team))
        .where(Match.deleted_at.is_(None),Match.match_date<=local_today(),or_(Match.home_team_id==team.id,Match.away_team_id==team.id))
        .order_by(desc(Match.match_date),desc(Match.id)).limit(1)
    )
    last_lineup=[]
    if last_match:
        last_lineup=list(session.scalars(
            select(Participation).options(joinedload(Participation.player)).where(Participation.match_id==last_match.id,Participation.team_id==team.id)
            .order_by(Participation.starter.desc(),Participation.order_index)
        ).unique().all())
    analyses=list(session.scalars(
        select(ScoutMission).options(joinedload(ScoutMission.assignee),joinedload(ScoutMission.match).joinedload(Match.home_team),joinedload(ScoutMission.match).joinedload(Match.away_team))
        .where(ScoutMission.status=="completed",ScoutMission.mission_type.in_(["team","rival_analysis"]),
               or_(ScoutMission.target_team_id==team.id,
                   ScoutMission.match_id.in_(select(Match.id).where(or_(Match.home_team_id==team.id,Match.away_team_id==team.id)))))
        .order_by(desc(ScoutMission.completed_at),desc(ScoutMission.id)).limit(10)
    ).unique().all())
    return {"team":team,"own_team":own,"roster":roster,"decisions":decisions,"next_vs_own":next_vs_own,"last_match":last_match,"last_lineup":last_lineup,"analyses":analyses}


def load_operational_readiness(session: Session) -> dict:
    """Read-only snapshot used to verify that the real season is ready for matchday work."""
    active = players_repo.get_active_season(session)
    own = players_repo.get_own_team(session)
    result = {
        "active_season": active,
        "own_team": own,
        "fixture_count": 0,
        "round_count": 0,
        "own_roster_count": 0,
        "today_match": None,
        "next_match": None,
        "warnings": [],
    }
    if not active:
        result["warnings"].append("No hay temporada activa.")
        return result
    if not own:
        result["warnings"].append("No está configurado el equipo propio.")
        return result

    result["fixture_count"] = int(session.scalar(
        select(func.count(Match.id)).where(
            Match.season_id == active.id,
            Match.deleted_at.is_(None),
            Match.status != "archived",
        )
    ) or 0)
    result["round_count"] = int(session.scalar(
        select(func.count(func.distinct(Match.round_name))).where(
            Match.season_id == active.id,
            Match.deleted_at.is_(None),
            Match.status != "archived",
        )
    ) or 0)
    result["own_roster_count"] = int(session.scalar(
        select(func.count(TeamRoster.id)).where(
            TeamRoster.team_id == own.id,
            TeamRoster.season_id == active.id,
            TeamRoster.active.is_(True),
        )
    ) or 0)

    own_filter = or_(Match.home_team_id == own.id, Match.away_team_id == own.id)
    result["today_match"] = session.scalar(
        select(Match).options(
            joinedload(Match.home_team), joinedload(Match.away_team), joinedload(Match.competition)
        ).where(
            Match.season_id == active.id,
            Match.deleted_at.is_(None),
            Match.status != "archived",
            Match.match_date == local_today(),
            own_filter,
        ).order_by(Match.kickoff_at.nullslast(), Match.id).limit(1)
    )
    result["next_match"] = _next_own_match(session, own.id, active.id)

    if result["fixture_count"] == 0:
        result["warnings"].append("La temporada activa no tiene calendario cargado.")
    if result["own_roster_count"] == 0:
        result["warnings"].append("La plantilla de No Name está vacía para la temporada activa.")
    if result["today_match"] and not result["today_match"].kickoff_at:
        result["warnings"].append("El partido de hoy existe, pero su hora real sigue pendiente de confirmar.")
    return result
