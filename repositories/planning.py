from __future__ import annotations

from repositories import players as players_repo

from repositories.data_governance import official_match_clause

import json
from datetime import date, datetime
from typing import Sequence

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from models.entities import (
    GameModelCriterion, GameModelRole, Match, Player, PlayerSeasonDecision, ScoutMission,
    ScoutMissionTarget, ScoutObservation, ScoutedPlayerProfile, Season, SquadNeed, Team,
    TeamRoster, User,
)
from core.schedule import require_schedule_confirmed
from core.presentation import normalize_need_state, normalize_player_state
from repositories.common import UTC_NOW, audit
from repositories.users import assert_role, user_has_role

MISSION_TYPES = {"player", "multi_player", "team", "rival_analysis", "spontaneous"}


def _assert_tracker(session: Session, user_id: int) -> User:
    user = session.get(User, int(user_id))
    if not user or not user.active:
        raise PermissionError("Usuario no válido.")
    if not bool(getattr(user, "can_track_players", False)):
        raise PermissionError("Tu usuario no tiene permiso de seguimiento individual de jugadores.")
    return user


def list_scout_users(session: Session, *, include_privileged: bool = False) -> list[User]:
    """Compatibility helper: return users allowed to perform individual tracking."""
    users = list(session.scalars(select(User).where(User.active.is_(True)).order_by(User.full_name)).all())
    return [u for u in users if bool(getattr(u, "can_track_players", False))]


def create_mission(
    session: Session,
    *,
    match_id: int,
    mission_type: str,
    title: str,
    assigned_to: int,
    requested_by: int,
    target_team_id: int | None = None,
    player_ids: Sequence[int] | None = None,
    purpose: str | None = None,
    focus: Sequence[str] | None = None,
    priority: int = 2,
    due_at: datetime | None = None,
) -> ScoutMission:
    assert_role(session, requested_by, "director")
    if mission_type not in MISSION_TYPES:
        raise ValueError("Tipo de misión no válido.")
    match = session.get(Match, int(match_id))
    assignee = session.get(User, int(assigned_to))
    if not match or not assignee or not assignee.active or not bool(getattr(assignee, "can_track_players", False)):
        raise ValueError("Partido o responsable no disponible. El usuario debe tener permiso de seguimiento individual.")
    item = ScoutMission(
        match_id=int(match_id), mission_type=mission_type, target_team_id=target_team_id,
        title=title.strip() or "Observación", purpose=(purpose or "").strip() or None,
        focus_json=json.dumps(list(focus or []), ensure_ascii=False), priority=max(1, min(3, int(priority))),
        status="pending", assigned_to=assignee.id, requested_by=int(requested_by), due_at=due_at,
        created_at=UTC_NOW(), updated_at=UTC_NOW(),
    )
    session.add(item)
    session.flush()
    for player_id in dict.fromkeys(int(x) for x in (player_ids or []) if x):
        if session.get(Player, player_id):
            session.add(ScoutMissionTarget(mission_id=item.id, player_id=player_id, created_at=UTC_NOW()))
    audit(session, requested_by, "create_scout_mission", "scout_mission", item.id, detail=f"type={mission_type}; assigned={assigned_to}; players={len(player_ids or [])}")
    return item


def list_missions(
    session: Session,
    *,
    assigned_to: int | None = None,
    match_id: int | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[ScoutMission]:
    stmt = select(ScoutMission).options(
        joinedload(ScoutMission.match).joinedload(Match.home_team),
        joinedload(ScoutMission.match).joinedload(Match.away_team),
        joinedload(ScoutMission.assignee), joinedload(ScoutMission.requester), joinedload(ScoutMission.target_team),
    )
    if assigned_to is not None:
        stmt = stmt.where(ScoutMission.assigned_to == int(assigned_to))
    if match_id is not None:
        stmt = stmt.where(ScoutMission.match_id == int(match_id))
    if status and status != "Todos":
        stmt = stmt.where(ScoutMission.status == status)
    return list(session.scalars(stmt.order_by(ScoutMission.status, desc(ScoutMission.priority), ScoutMission.due_at.nullslast(), desc(ScoutMission.updated_at)).limit(int(limit))).unique().all())


def mission_targets(session: Session, mission_id: int) -> list[ScoutMissionTarget]:
    return list(session.scalars(
        select(ScoutMissionTarget).options(joinedload(ScoutMissionTarget.player)).where(ScoutMissionTarget.mission_id == int(mission_id)).order_by(ScoutMissionTarget.id)
    ).unique().all())


def update_mission_status(session: Session, mission_id: int, actor_id: int, *, status: str, result_summary: str | None = None) -> ScoutMission:
    item = session.get(ScoutMission, int(mission_id))
    if not item:
        raise ValueError("Misión no encontrada.")
    if item.assigned_to != int(actor_id):
        assert_role(session, actor_id, "director")
    if status in {"in_progress", "completed"}:
        require_schedule_confirmed(session.get(Match, item.match_id), action="iniciar o completar la tarea de scouting")
    item.status = status
    if result_summary is not None:
        item.result_summary = result_summary.strip() or None
    item.completed_at = UTC_NOW() if status == "completed" else item.completed_at
    item.updated_at = UTC_NOW()
    audit(session, actor_id, "update_scout_mission", "scout_mission", item.id, detail=status)
    return item


def ensure_scout_profile(session: Session, player_id: int, actor_id: int) -> ScoutedPlayerProfile:
    _assert_tracker(session, actor_id)
    item = session.scalar(select(ScoutedPlayerProfile).where(ScoutedPlayerProfile.player_id == int(player_id)))
    if item:
        return item
    player = session.get(Player, int(player_id))
    if not player:
        raise ValueError("Jugador no encontrado.")
    item = ScoutedPlayerProfile(
        player_id=player.id, status="candidate", model_position=player.primary_position,
        requested_by=int(actor_id), revision=1, created_at=UTC_NOW(), updated_at=UTC_NOW(),
    )
    session.add(item)
    session.flush()
    audit(session, actor_id, "scout_detect_player", "scouted_player_profile", item.id, detail=f"player={player.id}")
    return item


def create_observation(
    session: Session,
    *,
    player_id: int,
    reviewer_id: int,
    match_id: int | None = None,
    mission_id: int | None = None,
    source_type: str = "specific",
    observation_level: str = "observation",
    model_role_id: int | None = None,
) -> ScoutObservation:
    _assert_tracker(session, reviewer_id)
    profile = ensure_scout_profile(session, int(player_id), reviewer_id)
    if mission_id:
        mission = session.get(ScoutMission, int(mission_id))
        if not mission or mission.assigned_to != int(reviewer_id):
            raise PermissionError("La tarea histórica no está asignada a este usuario.")
        match_id = mission.match_id
    if match_id:
        require_schedule_confirmed(session.get(Match, int(match_id)), action="iniciar el seguimiento individual")
    if mission_id:
        mission.status = "in_progress"
        mission.updated_at = UTC_NOW()
    level = str(observation_level or "observation").strip().casefold()
    if level not in {"scan", "observation", "dossier"}:
        raise ValueError("Nivel de observación no válido.")
    if model_role_id is not None and not session.get(GameModelRole, int(model_role_id)):
        raise ValueError("Rol del Modelo No Name no encontrado.")
    item = ScoutObservation(
        profile_id=profile.id, reviewer_id=int(reviewer_id), match_id=match_id, mission_id=mission_id,
        model_role_id=int(model_role_id) if model_role_id else None, source_type=source_type, observation_level=level,
        status="draft", observed_at=UTC_NOW(), created_at=UTC_NOW(), updated_at=UTC_NOW(),
    )
    session.add(item)
    session.flush()
    audit(session, reviewer_id, "create_scout_observation", "scout_observation", item.id, detail=f"player={player_id}; match={match_id}; mission={mission_id}")
    return item


def save_observation(
    session: Session,
    observation_id: int,
    actor_id: int,
    *,
    observed_position: str | None,
    general_rating: float | None = None,
    technical_rating: float | None = None,
    tactical_rating: float | None = None,
    physical_rating: float | None = None,
    mental_rating: float | None = None,
    current_level: float | None = None,
    potential_score: float | None = None,
    model_fit_score: float | None = None,
    attributes: dict | None = None,
    strengths: str | None = None,
    weaknesses: str | None = None,
    summary: str | None = None,
    recommendation: str | None = None,
    model_role_id: int | None = None,
    observation_level: str | None = None,
    submit: bool = False,
) -> ScoutObservation:
    item = session.get(ScoutObservation, int(observation_id))
    if not item:
        raise ValueError("Observación no encontrada.")
    if item.reviewer_id != int(actor_id):
        raise PermissionError("Solo el autor puede editar esta observación de seguimiento.")
    item.observed_position = observed_position
    if model_role_id is not None:
        if not session.get(GameModelRole, int(model_role_id)):
            raise ValueError("Rol del Modelo No Name no encontrado.")
        item.model_role_id = int(model_role_id)
    if observation_level is not None:
        level = str(observation_level).strip().casefold()
        if level not in {"scan", "observation", "dossier"}:
            raise ValueError("Nivel de observación no válido.")
        item.observation_level = level
    item.general_rating = general_rating
    item.technical_rating = technical_rating
    item.tactical_rating = tactical_rating
    item.physical_rating = physical_rating
    item.mental_rating = mental_rating
    item.current_level = current_level
    item.potential_score = potential_score
    item.model_fit_score = model_fit_score
    clean_attributes = dict(attributes or {})
    # Compatibility with 3.5/3.6 readers while model_role_id is now a proper column.
    if item.model_role_id and "model_role_id" not in clean_attributes:
        clean_attributes["model_role_id"] = item.model_role_id
    item.attributes_json = json.dumps(clean_attributes, ensure_ascii=False)
    item.strengths = (strengths or "").strip() or None
    item.weaknesses = (weaknesses or "").strip() or None
    item.summary = (summary or "").strip() or None
    item.recommendation = recommendation
    item.status = "submitted" if submit else "draft"
    item.submitted_at = UTC_NOW() if submit else item.submitted_at
    item.updated_at = UTC_NOW()
    profile = session.get(ScoutedPlayerProfile, item.profile_id)
    if profile and submit:
        profile.status = "in_review"
        profile.updated_at = UTC_NOW()
    if item.mission_id and submit:
        mission = session.get(ScoutMission, item.mission_id)
        if mission:
            targets = mission_targets(session, mission.id)
            target_profiles = {session.scalar(select(ScoutedPlayerProfile.id).where(ScoutedPlayerProfile.player_id == t.player_id)) for t in targets}
            submitted_profiles = set(session.scalars(select(ScoutObservation.profile_id).where(ScoutObservation.mission_id == mission.id, ScoutObservation.status == "submitted")).all())
            if not target_profiles or target_profiles.issubset(submitted_profiles):
                mission.status = "completed"
                mission.completed_at = UTC_NOW()
            else:
                mission.status = "in_progress"
            mission.updated_at = UTC_NOW()
    audit(session, actor_id, "save_scout_observation", "scout_observation", item.id, detail=f"submitted={submit}")
    return item


def list_observations(session: Session, *, player_id: int | None = None, reviewer_id: int | None = None, match_id: int | None = None, limit: int = 300) -> list[ScoutObservation]:
    stmt = select(ScoutObservation).options(
        joinedload(ScoutObservation.profile).joinedload(ScoutedPlayerProfile.player), joinedload(ScoutObservation.reviewer),
        joinedload(ScoutObservation.match).joinedload(Match.home_team), joinedload(ScoutObservation.match).joinedload(Match.away_team),
        joinedload(ScoutObservation.mission),
    )
    stmt = stmt.where(or_(ScoutObservation.match_id.is_(None),
                          ScoutObservation.match_id.in_(select(Match.id).where(official_match_clause()))))
    if player_id:
        stmt = stmt.join(ScoutedPlayerProfile, ScoutObservation.profile_id == ScoutedPlayerProfile.id).where(ScoutedPlayerProfile.player_id == int(player_id))
    if reviewer_id:
        stmt = stmt.where(ScoutObservation.reviewer_id == int(reviewer_id))
    if match_id:
        stmt = stmt.where(ScoutObservation.match_id == int(match_id))
    return list(session.scalars(stmt.order_by(desc(ScoutObservation.observed_at), desc(ScoutObservation.id)).limit(int(limit))).unique().all())



def save_quick_match_observations(
    session: Session, *, match_id: int, reviewer_id: int, rows: Sequence[dict], mission_id: int | None = None,
) -> int:
    """Save quick observations for several players and optionally fulfil an assigned task."""
    _assert_tracker(session, reviewer_id)
    match = session.get(Match, int(match_id))
    if not match:
        raise ValueError("Partido no encontrado.")
    require_schedule_confirmed(match, action="guardar una observación de partido")
    mission = None
    if mission_id is not None:
        mission = session.get(ScoutMission, int(mission_id))
        if not mission or mission.match_id != match.id or mission.assigned_to != int(reviewer_id):
            raise PermissionError("La tarea no está asignada a este Scout para este partido.")
        mission.status = "in_progress"
        mission.updated_at = UTC_NOW()
    count = 0
    saved_player_ids: set[int] = set()
    for row in rows:
        player_id = int(row.get("player_id") or 0)
        rating = row.get("general_rating")
        if not player_id or rating is None or float(rating) <= 0:
            continue
        profile = ensure_scout_profile(session, player_id, reviewer_id)
        item = ScoutObservation(
            profile_id=profile.id, reviewer_id=int(reviewer_id), match_id=match.id, mission_id=mission.id if mission else None,
            source_type="match_scan", observation_level="scan", status="submitted", observed_at=UTC_NOW(),
            observed_position=row.get("observed_position"), general_rating=float(rating),
            summary=(row.get("summary") or "").strip() or None, recommendation=row.get("recommendation") or "Sin conclusión",
            submitted_at=UTC_NOW(), created_at=UTC_NOW(), updated_at=UTC_NOW(),
        )
        session.add(item)
        saved_player_ids.add(player_id)
        count += 1
    session.flush()
    if mission and count:
        targets = {t.player_id for t in mission_targets(session, mission.id)}
        observed_players = set(session.scalars(
            select(ScoutedPlayerProfile.player_id)
            .join(ScoutObservation, ScoutObservation.profile_id == ScoutedPlayerProfile.id)
            .where(ScoutObservation.mission_id == mission.id, ScoutObservation.status == "submitted")
        ).all())
        if not targets or targets.issubset(observed_players):
            mission.status = "completed"
            mission.completed_at = UTC_NOW()
        mission.updated_at = UTC_NOW()
    audit(session, reviewer_id, "quick_match_scout", "match", match.id, detail=f"observations={count}; mission={mission_id}")
    return count

def create_model_role(session: Session, actor_id: int, *, name: str, position: str, description: str | None = None) -> GameModelRole:
    assert_role(session, actor_id, "director", "admin")
    item = GameModelRole(name=name.strip(), position=position, description=(description or "").strip() or None, active=True, order_index=0, created_by=int(actor_id), created_at=UTC_NOW(), updated_at=UTC_NOW())
    session.add(item); session.flush()
    audit(session, actor_id, "create_model_role", "game_model_role", item.id)
    return item


def list_model_roles(session: Session, *, active_only: bool = True) -> list[GameModelRole]:
    stmt = select(GameModelRole)
    if active_only:
        stmt = stmt.where(GameModelRole.active.is_(True))
    return list(session.scalars(stmt.order_by(GameModelRole.position, GameModelRole.order_index, GameModelRole.name)).all())


def add_model_criterion(session: Session, actor_id: int, role_id: int, *, name: str, category: str, weight: int, description: str | None = None) -> GameModelCriterion:
    assert_role(session, actor_id, "director", "admin")
    if not session.get(GameModelRole, int(role_id)):
        raise ValueError("Rol de modelo no encontrado.")
    item = GameModelCriterion(role_id=int(role_id), name=name.strip(), category=category, description=(description or "").strip() or None, weight=max(1, min(5, int(weight))), order_index=0)
    session.add(item); session.flush(); audit(session, actor_id, "add_model_criterion", "game_model_criterion", item.id)
    return item


def list_model_criteria(session: Session, role_id: int) -> list[GameModelCriterion]:
    return list(session.scalars(select(GameModelCriterion).where(GameModelCriterion.role_id == int(role_id)).order_by(GameModelCriterion.order_index, GameModelCriterion.id)).all())


def upsert_squad_need(session: Session, actor_id: int, *, season_id: int, model_role_id: int, need_level: str, status: str | None = None, note: str | None = None) -> SquadNeed:
    assert_role(session, actor_id, "director", "admin")
    item = session.scalar(select(SquadNeed).where(SquadNeed.season_id == int(season_id), SquadNeed.model_role_id == int(model_role_id)))
    if not item:
        item = SquadNeed(season_id=int(season_id), model_role_id=int(model_role_id), updated_by=int(actor_id), updated_at=UTC_NOW())
        session.add(item)
    canonical = normalize_need_state(need_level or status)
    item.need_level = canonical
    # status is kept only for backwards DB compatibility and mirrors the one
    # canonical user-visible value.
    item.status = canonical
    item.note = (note or "").strip() or None
    item.updated_by = int(actor_id); item.updated_at = UTC_NOW()
    session.flush(); audit(session, actor_id, "upsert_squad_need", "squad_need", item.id, detail=canonical)
    return item


def list_squad_needs(session: Session, season_id: int) -> list[SquadNeed]:
    return list(session.scalars(select(SquadNeed).options(joinedload(SquadNeed.model_role)).where(SquadNeed.season_id == int(season_id)).order_by(SquadNeed.need_level, SquadNeed.id)).unique().all())


def upsert_season_decision(session: Session, actor_id: int, *, season_id: int, player_id: int, status: str, priority: int, model_role_id: int | None = None, director_note: str | None = None, fit_score: float | None = None, current_level: float | None = None, potential_score: float | None = None, criteria_scores: dict[int, float] | None = None) -> PlayerSeasonDecision:
    assert_role(session, actor_id, "director", "admin")
    item = session.scalar(select(PlayerSeasonDecision).where(PlayerSeasonDecision.season_id == int(season_id), PlayerSeasonDecision.player_id == int(player_id)))
    if not item:
        item = PlayerSeasonDecision(season_id=int(season_id), player_id=int(player_id), updated_by=int(actor_id), created_at=UTC_NOW(), updated_at=UTC_NOW())
        session.add(item)
    item.status = normalize_player_state(status); item.priority = int(priority); item.model_role_id = model_role_id; item.director_note = (director_note or "").strip() or None; item.fit_score = fit_score
    item.current_level = current_level; item.potential_score = potential_score
    if criteria_scores is not None:
        item.criteria_json = json.dumps({str(k): float(v) for k, v in criteria_scores.items() if v is not None and float(v) > 0}, ensure_ascii=False)
    item.updated_by = int(actor_id); item.updated_at = UTC_NOW()
    session.flush(); audit(session, actor_id, "upsert_player_season_decision", "player_season_decision", item.id, detail=status)
    return item


def list_season_decisions(session: Session, season_id: int, *, status: str | None = None) -> list[PlayerSeasonDecision]:
    stmt = select(PlayerSeasonDecision).options(joinedload(PlayerSeasonDecision.player), joinedload(PlayerSeasonDecision.model_role)).where(PlayerSeasonDecision.season_id == int(season_id))
    if status:
        stmt = stmt.where(PlayerSeasonDecision.status == status)
    return list(session.scalars(stmt.order_by(PlayerSeasonDecision.priority, desc(PlayerSeasonDecision.fit_score), PlayerSeasonDecision.player_id)).unique().all())


def weighted_model_fit(criteria: Sequence[GameModelCriterion], scores: dict[int, float]) -> float | None:
    values = [(float(scores[c.id]), int(c.weight or 1)) for c in criteria if c.id in scores and scores[c.id] is not None]
    if not values:
        return None
    total_weight = sum(w for _, w in values)
    return round(sum(score * weight for score, weight in values) / total_weight, 2) if total_weight else None


def shadow_squad(session: Session, season_id: int) -> list[dict]:
    roles = list_model_roles(session)
    needs = {n.model_role_id: n for n in list_squad_needs(session, season_id)}
    decisions = list_season_decisions(session, season_id)
    own_team = players_repo.get_own_team(session)
    own_ids: set[int] = set()
    if own_team:
        own_ids = set(session.scalars(select(TeamRoster.player_id).where(
            TeamRoster.team_id == own_team.id, TeamRoster.season_id == int(season_id), TeamRoster.active.is_(True)
        )).all())
    by_role: dict[int, list[PlayerSeasonDecision]] = {}
    for decision in decisions:
        if decision.model_role_id:
            by_role.setdefault(int(decision.model_role_id), []).append(decision)
    result = []
    for role in roles:
        all_items = by_role.get(role.id, [])
        internal = sorted([d for d in all_items if d.player_id in own_ids], key=lambda d: (-(d.fit_score or 0), d.player.full_name))
        candidates = sorted([d for d in all_items if d.player_id not in own_ids], key=lambda d: (d.priority, -(d.fit_score or 0), d.player.full_name))
        result.append({"role": role, "need": needs.get(role.id), "own_players": internal, "candidates": candidates})
    return result


def _evidence_strength(specific_count: int, scout_count: int) -> str:
    if specific_count >= 3 and scout_count >= 2:
        return "Alta"
    if specific_count >= 2 or (specific_count >= 1 and scout_count >= 2):
        return "Media"
    if specific_count >= 1:
        return "Inicial"
    return "Sin scouting específico"


def scouting_evidence_many(session: Session, player_ids: Sequence[int], *, season_id: int | None = None) -> dict[int, dict]:
    """Batch evidence summary; avoids N+1 queries in DD planning/shortlists."""
    from models.entities import PlayerEvaluation, Report
    from repositories import scouting as base_repo

    ids = list(dict.fromkeys(int(x) for x in player_ids if x))
    if not ids:
        return {}
    result = {pid: {
        "postmatch_observations": 0, "postmatch_reporters": 0, "postmatch_last": None,
        "specific_observations": 0, "specific_scouts": 0, "specific_matches": 0, "specific_last": None,
        "specific_strength": "Sin scouting específico", "intentional_evidence": False,
    } for pid in ids}

    post_stmt = (
        select(
            PlayerEvaluation.player_id, func.count(PlayerEvaluation.id),
            func.count(func.distinct(Report.reporter_id)), func.max(Match.match_date),
        )
        .select_from(PlayerEvaluation)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .where(PlayerEvaluation.player_id.in_(ids), *base_repo._valid_rival_evaluation_predicates())
    )
    if season_id:
        post_stmt = post_stmt.where(Match.season_id == int(season_id))
    post_stmt = post_stmt.group_by(PlayerEvaluation.player_id)
    for pid, count, reporters, last in session.execute(post_stmt).all():
        row = result[int(pid)]
        row.update(postmatch_observations=int(count or 0), postmatch_reporters=int(reporters or 0), postmatch_last=last)

    scout_stmt = (
        select(
            ScoutedPlayerProfile.player_id, func.count(ScoutObservation.id),
            func.count(func.distinct(ScoutObservation.reviewer_id)),
            func.count(func.distinct(ScoutObservation.match_id)), func.max(ScoutObservation.observed_at),
        )
        .select_from(ScoutObservation)
        .join(ScoutedPlayerProfile, ScoutObservation.profile_id == ScoutedPlayerProfile.id)
        .outerjoin(Match, ScoutObservation.match_id == Match.id)
        .where(ScoutedPlayerProfile.player_id.in_(ids), ScoutObservation.status == "submitted",
            or_(ScoutObservation.match_id.is_(None), ScoutObservation.match_id.in_(select(Match.id).where(official_match_clause()))))
    )
    if season_id:
        scout_stmt = scout_stmt.where(or_(Match.season_id == int(season_id), ScoutObservation.match_id.is_(None)))
    scout_stmt = scout_stmt.group_by(ScoutedPlayerProfile.player_id)
    for pid, count, scouts, matches, last in session.execute(scout_stmt).all():
        row = result[int(pid)]
        count, scouts = int(count or 0), int(scouts or 0)
        row.update(
            specific_observations=count, specific_scouts=scouts, specific_matches=int(matches or 0), specific_last=last,
            specific_strength=_evidence_strength(count, scouts), intentional_evidence=count > 0,
        )
    return result


def scouting_evidence_summary(session: Session, player_id: int, *, season_id: int | None = None) -> dict:
    """One-player wrapper around the batch evidence engine."""
    return scouting_evidence_many(session, [int(player_id)], season_id=season_id)[int(player_id)]


def scouting_opportunities(session: Session, *, season_id: int, days_ahead: int = 120, limit: int = 40) -> list[dict]:
    """Future fixtures that can close evidence gaps for current squad needs, using batch queries."""
    from repositories import scouting as base_repo

    today = date.today()
    until = date.fromordinal(today.toordinal() + int(days_ahead))
    shadow = shadow_squad(session, int(season_id))
    decisions = [d for block in shadow for d in block["candidates"]]
    if not decisions:
        return []

    player_ids = [int(d.player_id) for d in decisions]
    team_map = base_repo.latest_player_team_map(session, player_ids)
    roster_rows = session.execute(
        select(TeamRoster.player_id, Team.id, Team.name)
        .join(Team, TeamRoster.team_id == Team.id)
        .where(TeamRoster.season_id == int(season_id), TeamRoster.player_id.in_(player_ids), TeamRoster.active.is_(True))
    ).all()
    for player_id, team_id, team_name in roster_rows:
        team_map.setdefault(int(player_id), {"team_id": int(team_id), "team_name": team_name, "last_observed": None})

    team_ids = sorted({int(x["team_id"]) for x in team_map.values() if x.get("team_id")})
    next_by_team: dict[int, Match] = {}
    if team_ids:
        fixtures = list(session.scalars(
            select(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team))
            .where(
                Match.season_id == int(season_id), official_match_clause(),
                Match.match_date >= today, Match.match_date <= until,
                or_(Match.home_team_id.in_(team_ids), Match.away_team_id.in_(team_ids)),
            )
            .order_by(Match.match_date, Match.kickoff_at.nullslast(), Match.id)
        ).unique().all())
        for match in fixtures:
            for team_id in (match.home_team_id, match.away_team_id):
                if team_id in team_ids and team_id not in next_by_team:
                    next_by_team[int(team_id)] = match

    evidence_map = scouting_evidence_many(session, player_ids, season_id=season_id)
    opportunities = []
    for block in shadow:
        need = block["need"]
        if not need or normalize_need_state(need.need_level or need.status) not in {"Alta", "Media"}:
            continue
        for decision in block["candidates"]:
            team_id = team_map.get(int(decision.player_id), {}).get("team_id")
            match = next_by_team.get(int(team_id)) if team_id else None
            if not match:
                continue
            opportunities.append({
                "role": block["role"], "need": need, "decision": decision, "match": match,
                "team_id": int(team_id), "evidence": evidence_map.get(int(decision.player_id), {}),
            })
    opportunities.sort(key=lambda x: (0 if x["need"].need_level == "Alta" else 1, x["match"].match_date, x["decision"].priority))
    return opportunities[: int(limit)]

