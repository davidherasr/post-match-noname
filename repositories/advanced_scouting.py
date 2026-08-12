from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session, joinedload

from models.entities import Player, ScoutedPlayerProfile, ScoutReview, User
from repositories import scouting as base_repo

UTC_NOW = lambda: datetime.now(timezone.utc).replace(tzinfo=None)
_UNSET = object()

SCOUT_STATUSES = {
    "candidate": "Candidato",
    "requested": "Solicitado",
    "in_review": "En revisión",
    "scouted": "Ojeado",
    "archived": "Archivado",
}
SCOUT_DECISIONS = ["Sin decidir", "No encaja", "Base", "Seguimiento", "Prioritario", "Descartado"]
SCOUT_RECOMMENDATIONS = ["Sin conclusión", "No encaja", "Volver a ver", "Seguimiento", "Prioritario", "Descartar"]


def get_profile(session: Session, player_id: int) -> ScoutedPlayerProfile | None:
    return session.scalar(
        select(ScoutedPlayerProfile)
        .options(
            joinedload(ScoutedPlayerProfile.player),
            joinedload(ScoutedPlayerProfile.requester),
            joinedload(ScoutedPlayerProfile.assignee),
            joinedload(ScoutedPlayerProfile.approver),
        )
        .where(ScoutedPlayerProfile.player_id == int(player_id))
    )


def request_profile(
    session: Session,
    *,
    player_id: int,
    actor_id: int,
    assigned_to: int | None = None,
    model_position: str | None = None,
    model_role: str | None = None,
) -> ScoutedPlayerProfile:
    base_repo.assert_role(session, actor_id, "director", "admin")
    player = session.get(Player, int(player_id))
    if not player:
        raise ValueError("Jugador no encontrado.")
    item = session.scalar(select(ScoutedPlayerProfile).where(ScoutedPlayerProfile.player_id == int(player_id)))
    if item is None:
        item = ScoutedPlayerProfile(
            player_id=int(player_id),
            status="requested" if assigned_to else "candidate",
            requested_by=int(actor_id),
            assigned_to=assigned_to,
            model_position=model_position or player.primary_position,
            model_role=model_role,
            revision=1,
            created_at=UTC_NOW(),
            updated_at=UTC_NOW(),
        )
        session.add(item)
        session.flush()
    else:
        item.status = "requested" if assigned_to else (item.status if item.status not in {"archived"} else "candidate")
        item.assigned_to = assigned_to if assigned_to is not None else item.assigned_to
        item.model_position = model_position or item.model_position or player.primary_position
        item.model_role = model_role or item.model_role
        item.revision = int(item.revision or 0) + 1
        item.updated_at = UTC_NOW()
    base_repo.audit(session, actor_id, "request_scout_profile", "scouted_player_profile", item.id, detail=f"player={player_id}; assigned_to={assigned_to}")
    return item


def update_profile(
    session: Session,
    profile_id: int,
    actor_id: int,
    *,
    status: str | None = None,
    assigned_to: int | None | object = _UNSET,
    model_position: str | None = None,
    model_role: str | None = None,
    fit_score: float | None = None,
    current_level: float | None = None,
    potential_score: float | None = None,
    final_decision: str | None = None,
    director_summary: str | None = None,
    approve: bool = False,
) -> ScoutedPlayerProfile:
    base_repo.assert_role(session, actor_id, "director", "admin")
    item = session.get(ScoutedPlayerProfile, int(profile_id))
    if not item:
        raise ValueError("Ficha scout no encontrada.")
    before = {"status": item.status, "model_position": item.model_position, "model_role": item.model_role, "fit_score": item.fit_score, "final_decision": item.final_decision}
    if status is not None:
        item.status = status
    if assigned_to is not _UNSET:
        item.assigned_to = None if assigned_to is None else int(assigned_to)
    if model_position is not None:
        item.model_position = model_position
    if model_role is not None:
        item.model_role = model_role
    if fit_score is not None:
        item.fit_score = fit_score
    if current_level is not None:
        item.current_level = current_level
    if potential_score is not None:
        item.potential_score = potential_score
    if final_decision is not None:
        item.final_decision = final_decision
    if director_summary is not None:
        item.director_summary = director_summary
    if approve:
        item.status = "scouted"
        item.approved_by = int(actor_id)
        item.approved_at = UTC_NOW()
    item.revision = int(item.revision or 0) + 1
    item.updated_at = UTC_NOW()
    after = {"status": item.status, "model_position": item.model_position, "model_role": item.model_role, "fit_score": item.fit_score, "final_decision": item.final_decision}
    base_repo.audit(session, actor_id, "update_scout_profile", "scouted_player_profile", item.id, before=before, after=after)
    return item


def get_or_create_review(session: Session, profile_id: int, reviewer_id: int) -> ScoutReview:
    profile = session.get(ScoutedPlayerProfile, int(profile_id))
    if not profile:
        raise ValueError("Ficha scout no encontrada.")
    user = session.get(User, int(reviewer_id))
    if not user or not user.active:
        raise ValueError("Informador no disponible.")
    if user.role == "reporter" and profile.assigned_to not in {None, int(reviewer_id)}:
        raise PermissionError("Esta ficha está asignada a otro informador.")
    item = session.scalar(select(ScoutReview).where(ScoutReview.profile_id == int(profile_id), ScoutReview.reviewer_id == int(reviewer_id)))
    if item is None:
        item = ScoutReview(profile_id=int(profile_id), reviewer_id=int(reviewer_id), status="draft", created_at=UTC_NOW(), updated_at=UTC_NOW())
        session.add(item)
        session.flush()
    if profile.status in {"candidate", "requested"}:
        profile.status = "in_review"
        profile.updated_at = UTC_NOW()
    return item


def save_review(
    session: Session,
    review_id: int,
    actor_id: int,
    *,
    observed_position: str | None,
    technical_rating: float | None,
    tactical_rating: float | None,
    physical_rating: float | None,
    mental_rating: float | None,
    current_level: float | None,
    potential_score: float | None,
    model_fit_score: float | None,
    attributes: dict,
    strengths: str | None,
    weaknesses: str | None,
    summary: str | None,
    recommendation: str | None,
    submit: bool = False,
) -> ScoutReview:
    item = session.scalar(
        select(ScoutReview)
        .options(joinedload(ScoutReview.profile))
        .where(ScoutReview.id == int(review_id))
    )
    if not item:
        raise ValueError("Informe scout no encontrado.")
    actor = session.get(User, int(actor_id))
    if not actor or not actor.active:
        raise PermissionError("Usuario no válido.")
    if actor.role == "reporter" and item.reviewer_id != int(actor_id):
        raise PermissionError("No puedes editar la ficha de otro informador.")
    item.observed_position = observed_position
    item.technical_rating = technical_rating
    item.tactical_rating = tactical_rating
    item.physical_rating = physical_rating
    item.mental_rating = mental_rating
    item.current_level = current_level
    item.potential_score = potential_score
    item.model_fit_score = model_fit_score
    item.attributes_json = json.dumps(attributes or {}, ensure_ascii=False)
    item.strengths = strengths
    item.weaknesses = weaknesses
    item.summary = summary
    item.recommendation = recommendation
    item.status = "submitted" if submit else "draft"
    item.submitted_at = UTC_NOW() if submit else item.submitted_at
    item.updated_at = UTC_NOW()
    if item.profile and submit:
        item.profile.status = "in_review"
        item.profile.updated_at = UTC_NOW()
    base_repo.audit(session, actor_id, "save_scout_review", "scout_review", item.id, detail=f"submitted={submit}")
    return item


def list_profiles(
    session: Session,
    *,
    status: str | None = None,
    assigned_to: int | None = None,
    limit: int = 200,
) -> list[ScoutedPlayerProfile]:
    stmt = select(ScoutedPlayerProfile).options(
        joinedload(ScoutedPlayerProfile.player),
        joinedload(ScoutedPlayerProfile.assignee),
        joinedload(ScoutedPlayerProfile.requester),
    )
    if status and status != "Todos":
        stmt = stmt.where(ScoutedPlayerProfile.status == status)
    if assigned_to is not None:
        stmt = stmt.where(ScoutedPlayerProfile.assigned_to == int(assigned_to))
    return list(session.scalars(stmt.order_by(desc(ScoutedPlayerProfile.updated_at)).limit(int(limit))).all())


def list_reviews(session: Session, profile_id: int) -> list[ScoutReview]:
    return list(session.scalars(
        select(ScoutReview)
        .options(joinedload(ScoutReview.reviewer))
        .where(ScoutReview.profile_id == int(profile_id))
        .order_by(desc(ScoutReview.updated_at))
    ).all())


def profile_bundle(session: Session, player_id: int) -> dict | None:
    profile = get_profile(session, player_id)
    if not profile:
        return None
    reviews = list_reviews(session, profile.id)
    history = base_repo.player_history(session, int(player_id))
    ranking = next((r for r in base_repo.player_rankings(session, min_observations=1, limit=500) if int(r["player_id"]) == int(player_id)), None)
    team = base_repo.latest_player_team_map(session, [int(player_id)]).get(int(player_id), {})
    return {"profile": profile, "reviews": reviews, "history": history, "ranking": ranking, "team": team}
