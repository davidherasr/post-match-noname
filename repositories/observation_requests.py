"""Voluntary sporting questions. Never creates an old scout mission or a rating."""
from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from models.entities import (Match, MatchOpinion, MatchOpinionPlayer, Participation,
    Player, PlayerEvaluation, PlayerObservationRecipient, PlayerObservationRequest,
    PlayerObservationResponse, Report, Season, TeamRoster, User)
from repositories.common import UTC_NOW, audit, FINAL_REPORT_STATUSES
from repositories.data_governance import official_match_clause
from repositories.players import get_own_team
from repositories.users import assert_role, user_has_role

RESULTS = {"seen": "Lo vi", "not_seen": "No pude verlo", "did_not_play": "No jugó (según informador)",
           "later": "Ahora no", "declined": "Prefiero no responder"}


def _external(session: Session, player_id: int, season_id: int) -> Player:
    player = session.get(Player, int(player_id))
    season = session.get(Season, int(season_id))
    if not player or not player.active or player.merged_into_id is not None or not season:
        raise ValueError("El jugador o la temporada no están disponibles.")
    own = get_own_team(session)
    if own and session.scalar(select(TeamRoster.id).where(
            TeamRoster.player_id == player.id, TeamRoster.team_id == own.id,
            TeamRoster.season_id == season.id).limit(1)):
        raise ValueError("No se solicitan observaciones de mercado sobre futbolistas propios.")
    return player


def available_reporters(session: Session) -> list[User]:
    from models.entities import UserRole
    ids = select(UserRole.user_id).where(UserRole.role == "reporter")
    return list(session.scalars(select(User).where(User.active.is_(True), User.deleted_at.is_(None),
        or_(User.id.in_(ids), User.role == "reporter")).order_by(User.full_name, User.id)).all())


def create_request(session: Session, *, actor_id: int, player_id: int, season_id: int,
                   recipient_ids: list[int], question: str, target_match_id: int | None = None,
                   priority: str = "Normal") -> PlayerObservationRequest:
    assert_role(session, actor_id, "director")
    _external(session, player_id, season_id)
    question = (question or "").strip()
    if len(question) < 5:
        raise ValueError("Especifica qué necesitas conocer del jugador (al menos 5 caracteres).")
    recipients = sorted({int(uid) for uid in recipient_ids})
    if not recipients:
        raise ValueError("Selecciona al menos un Informador.")
    valid = {u.id for u in available_reporters(session)}
    if set(recipients) - valid:
        raise PermissionError("Hay destinatarios sin rol Informador activo.")
    if priority not in {"Normal", "Alta"}:
        raise ValueError("Prioridad desconocida.")
    if target_match_id is not None:
        target = session.scalar(select(Match).where(Match.id == int(target_match_id),
            Match.season_id == int(season_id), official_match_clause()))
        if target is None:
            raise ValueError("Partido objetivo no disponible.")
        # Explicit targeting must refer to the player's real match/season context.
        appearance = session.scalar(select(Participation.id).where(
            Participation.match_id == target.id, Participation.player_id == int(player_id)).limit(1))
        roster = session.scalar(select(TeamRoster.id).where(
            TeamRoster.player_id == int(player_id), TeamRoster.season_id == int(season_id),
            TeamRoster.team_id.in_([target.home_team_id, target.away_team_id])).limit(1))
        if not appearance and not roster:
            raise ValueError("El jugador no consta vinculado a ese partido. Déjalo como próxima coincidencia.")
    # The same unresolved question is extended, not multiplied, across recipients.
    existing = session.scalar(select(PlayerObservationRequest).where(
        PlayerObservationRequest.player_id == int(player_id),
        PlayerObservationRequest.season_id == int(season_id),
        PlayerObservationRequest.status == "open",
        PlayerObservationRequest.question == question,
        PlayerObservationRequest.target_match_id == target_match_id))
    if existing:
        current = {r.user_id for r in session.scalars(select(PlayerObservationRecipient).where(
            PlayerObservationRecipient.request_id == existing.id)).all()}
        for uid in recipients:
            if uid not in current:
                session.add(PlayerObservationRecipient(request_id=existing.id, user_id=uid, status="pending"))
        audit(session, actor_id, "extend_observation_request", "player_observation_request", existing.id,
              detail=f"destinatarios añadidos: {len(set(recipients)-current)}")
        return existing
    req = PlayerObservationRequest(player_id=player_id, season_id=season_id, requested_by=actor_id,
        question=question, target_match_id=target_match_id, priority=priority, status="open")
    session.add(req)
    session.flush()
    for uid in recipients:
        session.add(PlayerObservationRecipient(request_id=req.id, user_id=uid, status="pending"))
    audit(session, actor_id, "create_observation_request", "player_observation_request", req.id,
          detail=f"jugador={player_id}; destinatarios={len(recipients)}; partido={target_match_id}")
    return req


def list_requests(session: Session, *, season_id: int, reporter_id: int | None = None,
                  active_only: bool = False) -> list[PlayerObservationRequest]:
    stmt = select(PlayerObservationRequest).options(joinedload(PlayerObservationRequest.player),
        joinedload(PlayerObservationRequest.creator), joinedload(PlayerObservationRequest.match))
    stmt = stmt.where(PlayerObservationRequest.season_id == int(season_id))
    if active_only:
        stmt = stmt.where(PlayerObservationRequest.status == "open")
    if reporter_id is not None:
        stmt = stmt.where(PlayerObservationRequest.id.in_(select(PlayerObservationRecipient.request_id).where(
            PlayerObservationRecipient.user_id == int(reporter_id),
            PlayerObservationRecipient.status == "pending")))
    return list(session.scalars(stmt.order_by(PlayerObservationRequest.created_at.desc(),
                                             PlayerObservationRequest.id.desc())).unique().all())


def recipients(session: Session, request_id: int) -> list[PlayerObservationRecipient]:
    return list(session.scalars(select(PlayerObservationRecipient).options(
        joinedload(PlayerObservationRecipient.user)).where(
        PlayerObservationRecipient.request_id == int(request_id)).order_by(PlayerObservationRecipient.id)).unique().all())


def responses(session: Session, request_id: int) -> list[PlayerObservationResponse]:
    return list(session.scalars(select(PlayerObservationResponse).options(
        joinedload(PlayerObservationResponse.user),
        joinedload(PlayerObservationResponse.match).joinedload(Match.home_team),
        joinedload(PlayerObservationResponse.match).joinedload(Match.away_team),
        joinedload(PlayerObservationResponse.evaluation), joinedload(PlayerObservationResponse.neutral_signal))
        .where(PlayerObservationResponse.request_id == int(request_id))
        .order_by(PlayerObservationResponse.created_at.desc(), PlayerObservationResponse.id.desc())).unique().all())


def match_relevance(session: Session, request: PlayerObservationRequest, match_id: int) -> str | None:
    """Known appearance vs roster-only match; never infer XI from roster."""
    m = session.scalar(select(Match).where(Match.id == int(match_id),
        Match.season_id == request.season_id, official_match_clause()))
    if m is None or (request.target_match_id is not None and request.target_match_id != m.id):
        return None
    appearance = session.scalar(select(Participation.id).where(
        Participation.match_id == m.id, Participation.player_id == request.player_id,
        or_(Participation.starter.is_(True), Participation.minute_in > 0)).limit(1))
    if appearance:
        return "participation"
    roster = session.scalar(select(TeamRoster.id).where(TeamRoster.player_id == request.player_id,
        TeamRoster.season_id == m.season_id,
        TeamRoster.team_id.in_([m.home_team_id, m.away_team_id])).limit(1))
    return "possible" if roster else None


def requests_for_match(session: Session, *, match_id: int, reporter_id: int) -> list[tuple[PlayerObservationRequest, str]]:
    match = session.scalar(select(Match).where(Match.id == int(match_id), official_match_clause()))
    if not match:
        return []
    pending = list_requests(session, season_id=match.season_id, reporter_id=reporter_id, active_only=True)
    result = []
    for req in pending:
        relevance = match_relevance(session, req, match_id)
        if relevance and not session.scalar(select(PlayerObservationResponse.id).where(
            PlayerObservationResponse.request_id == req.id,
            PlayerObservationResponse.user_id == int(reporter_id),
            PlayerObservationResponse.match_id == int(match_id)).limit(1)):
            result.append((req, relevance))
    return result


def respond(session: Session, *, actor_id: int, request_id: int, result: str,
            match_id: int | None = None, note: str | None = None,
            confirmed_played: bool = False) -> PlayerObservationResponse:
    assert_role(session, actor_id, "reporter")
    req = session.get(PlayerObservationRequest, int(request_id))
    recipient = session.scalar(select(PlayerObservationRecipient).where(
        PlayerObservationRecipient.request_id == int(request_id),
        PlayerObservationRecipient.user_id == int(actor_id)))
    if req is None or req.status != "open" or recipient is None or recipient.status != "pending":
        raise PermissionError("No tienes esta petición pendiente.")
    if result not in RESULTS:
        raise ValueError("Respuesta desconocida.")
    if match_id is not None and match_relevance(session, req, int(match_id)) is None:
        raise ValueError("El jugador no está vinculado a ese partido por identidad y temporada.")
    if req.target_match_id and match_id not in (None, req.target_match_id):
        raise ValueError("La solicitud se refiere a otro encuentro.")
    note = (note or "").strip() or None
    if result == "seen":
        if match_id is None:
            raise ValueError("Indica el partido donde lo viste.")
        if match_relevance(session, req, match_id) == "possible" and not confirmed_played:
            raise ValueError("La participación no consta: debes confirmar expresamente que lo viste jugar.")
    existing = session.scalar(select(PlayerObservationResponse).where(
        PlayerObservationResponse.request_id == req.id,
        PlayerObservationResponse.user_id == int(actor_id),
        PlayerObservationResponse.match_id == match_id))
    if existing:
        if result == "later" and existing.result == "later":
            existing.note = note
            existing.updated_at = UTC_NOW()
            audit(session, actor_id, "defer_observation_request", "player_observation_request", req.id,
                detail=f"partido={match_id}")
            return existing
        raise ValueError("Ya respondiste a esta petición para ese partido. No se duplicará.")
    evaluation_id = signal_id = None
    if result == "seen" and match_id is not None:
        evaluation = session.scalar(select(PlayerEvaluation).join(Report, PlayerEvaluation.report_id == Report.id)
            .where(Report.match_id == int(match_id), Report.reporter_id == int(actor_id),
                Report.status.in_(FINAL_REPORT_STATUSES), PlayerEvaluation.player_id == req.player_id,
                PlayerEvaluation.general_rating.is_not(None), PlayerEvaluation.general_rating > 0).limit(1))
        if evaluation:
            evaluation_id = evaluation.id
        neutral = session.scalar(select(MatchOpinionPlayer).join(MatchOpinion, MatchOpinionPlayer.opinion_id == MatchOpinion.id)
            .where(MatchOpinion.match_id == int(match_id), MatchOpinion.user_id == int(actor_id),
                   MatchOpinionPlayer.player_id == req.player_id).limit(1))
        if neutral:
            signal_id = neutral.id
        if not (evaluation_id or signal_id or note):
            raise ValueError("Añade una impresión breve o valora al jugador en el informe antes de responder.")
    response = PlayerObservationResponse(request_id=req.id, user_id=actor_id,
        match_id=match_id, player_evaluation_id=evaluation_id, neutral_signal_id=signal_id,
        result=result, note=note)
    session.add(response)
    recipient.status = "declined" if result == "declined" else ("pending" if result == "later" else "answered")
    audit(session, actor_id, "answer_observation_request", "player_observation_request", req.id,
          detail=f"respuesta={result}; partido={match_id}; evaluación={evaluation_id}; señal={signal_id}")
    session.flush()
    return response


def close_request(session: Session, *, actor_id: int, request_id: int, reason: str) -> None:
    assert_role(session, actor_id, "director")
    req = session.get(PlayerObservationRequest, int(request_id))
    if not req or req.status != "open":
        raise ValueError("La petición no está abierta.")
    req.status, req.closed_at, req.closed_reason = "closed", UTC_NOW(), (reason or "").strip() or None
    audit(session, actor_id, "close_observation_request", "player_observation_request", req.id, detail=req.closed_reason)
