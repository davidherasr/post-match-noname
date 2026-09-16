"""Single logical match/player/author event for postmatch and individual tracking.

Existing duplicate observations remain untouched until DD explicitly reviews them.
No scouting mission, DD approval or automatic tracking is created by an 8/10.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from core.evaluation_rules import AUTO_STANDOUT_THRESHOLD
from models.entities import (
    Match, PlayerEvaluation, PlayerSeasonDecision, Report, ScoutObservation,
    ScoutedPlayerProfile, TeamRoster, User,
)
from repositories import players as players_repo
from repositories import sporting_reading as sporting_repo
from repositories.common import FINAL_REPORT_STATUSES, UTC_NOW, audit
from repositories.data_governance import official_match_clause
from repositories.users import assert_role


def report_tracking_candidates(session: Session, report_id: int, actor_id: int) -> list[PlayerEvaluation]:
    """Only rated external players in the informador's delivered own-match report."""
    actor = session.get(User, int(actor_id))
    if not actor or not actor.active or actor.deleted_at is not None or not actor.can_track_players:
        raise PermissionError("El seguimiento requiere el permiso individual concedido por Administración.")
    report = session.get(Report, int(report_id))
    if not report or report.reporter_id != actor.id or report.status not in FINAL_REPORT_STATUSES:
        raise PermissionError("Solo puedes ampliar tu propio postpartido ya incorporado.")
    official = session.scalar(select(Match.id).where(Match.id == report.match_id, official_match_clause()))
    own = players_repo.get_own_team(session)
    if not official or not own or report.own_team_id != own.id or report.rival_team_id == own.id:
        raise ValueError("El seguimiento solo se habilita para rivales de un partido propio oficial.")
    return list(session.scalars(
        select(PlayerEvaluation).options(joinedload(PlayerEvaluation.player),
                                         joinedload(PlayerEvaluation.participation),
                                         joinedload(PlayerEvaluation.report))
        .where(PlayerEvaluation.report_id == report.id, PlayerEvaluation.evaluation_scope == "rival",
               PlayerEvaluation.team_id == report.rival_team_id,
               PlayerEvaluation.observation_status == "evaluated", PlayerEvaluation.general_rating > 0)
        .order_by(PlayerEvaluation.general_rating.desc(), PlayerEvaluation.player_id)
    ).unique().all())


def match_observations(session: Session, player_id: int, author_id: int, match_id: int) -> list[ScoutObservation]:
    return list(session.scalars(
        select(ScoutObservation).join(ScoutedPlayerProfile, ScoutObservation.profile_id == ScoutedPlayerProfile.id)
        .where(ScoutedPlayerProfile.player_id == int(player_id), ScoutObservation.reviewer_id == int(author_id),
               ScoutObservation.match_id == int(match_id))
        .order_by(ScoutObservation.id)
    ).all())


def _external_player(session: Session, player_id: int, match_id: int) -> None:
    own = players_repo.get_own_team(session)
    if own and session.scalar(select(TeamRoster.id).where(TeamRoster.team_id == own.id,
                   TeamRoster.player_id == int(player_id), TeamRoster.active.is_(True)).limit(1)):
        raise ValueError("Un jugador de No Name no puede recibir seguimiento de mercado.")
    # A known participation in this very match overrides stale/incomplete roster data.
    if own:
        from models.entities import Participation
        if session.scalar(select(Participation.id).where(Participation.player_id == int(player_id),
                          Participation.team_id == own.id, Participation.match_id == int(match_id)).limit(1)):
            raise ValueError("Un jugador de No Name no puede recibir seguimiento de mercado.")


def get_or_create_match_observation(session: Session, *, player_id: int, author_id: int,
                                    match_id: int, player_evaluation_id: int | None = None) -> tuple[ScoutObservation, bool]:
    actor = session.get(User, int(author_id))
    if not actor or not actor.active or actor.deleted_at is not None or not actor.can_track_players:
        raise PermissionError("No tienes permiso para crear seguimientos individuales.")
    match = session.scalar(select(Match).where(Match.id == int(match_id), official_match_clause()))
    if match is None:
        raise ValueError("Partido inexistente o excluido de los datos oficiales.")
    _external_player(session, player_id, match.id)
    # Serialize competing submissions for one player in PostgreSQL without ever
    # running a destructive historical deduplication or modifying another author.
    profile = session.scalar(select(ScoutedPlayerProfile)
                             .where(ScoutedPlayerProfile.player_id == int(player_id)).with_for_update())
    if profile is None:
        profile = sporting_repo.start_player_tracking(session, player_id=int(player_id), actor_id=int(author_id))
    previous = match_observations(session, player_id, author_id, match.id)
    if player_evaluation_id is not None:
        linked = next((row for row in previous if row.player_evaluation_id == int(player_evaluation_id)), None)
        if linked:
            return linked, False
    if previous:
        # Reuse the oldest submitted row, never create a third. Historical duplicates
        # are shown to DD for manual, audited review rather than silently destroyed.
        canonical = next((row for row in previous if row.status == "submitted" and row.player_evaluation_id is None), previous[0])
        if player_evaluation_id is not None:
            if canonical.player_evaluation_id not in (None, int(player_evaluation_id)):
                raise ValueError("La observación ya está vinculada a otra evaluación.")
            canonical.player_evaluation_id = int(player_evaluation_id)
        return canonical, False
    observation = ScoutObservation(profile_id=profile.id, reviewer_id=int(author_id), match_id=match.id,
        player_evaluation_id=int(player_evaluation_id) if player_evaluation_id else None,
        mission_id=None, source_type="postmatch_enrichment" if player_evaluation_id else "specific",
        observation_level="observation", status="draft", observed_at=UTC_NOW(),
        created_at=UTC_NOW(), updated_at=UTC_NOW())
    session.add(observation)
    session.flush()
    return observation, True


def enrich_postmatch_evaluation(session: Session, *, evaluation_id: int, author_id: int,
                                summary: str | None = None, strengths: str | None = None,
                                weaknesses: str | None = None, recommendation: str | None = None) -> ScoutObservation:
    ev = session.get(PlayerEvaluation, int(evaluation_id))
    if ev is None:
        raise ValueError("Valoración de postpartido no encontrada.")
    report_tracking_candidates(session, ev.report_id, author_id)
    report = session.get(Report, ev.report_id)
    if ev.evaluation_scope != "rival" or ev.team_id != report.rival_team_id or ev.observation_status != "evaluated" or not ev.general_rating or ev.general_rating <= 0:
        raise ValueError("Solo se pueden ampliar valoraciones válidas de futbolistas rivales.")
    observation, created = get_or_create_match_observation(session, player_id=ev.player_id,
        author_id=author_id, match_id=report.match_id, player_evaluation_id=ev.id)
    if observation.player_evaluation_id not in (None, ev.id):
        raise ValueError("La observación ya está vinculada a una valoración diferente.")
    before = {"rating": observation.general_rating, "summary": observation.summary,
              "evaluation": observation.player_evaluation_id, "status": observation.status}
    observation.player_evaluation_id = ev.id
    observation.source_type = "postmatch_enrichment"
    # Postmatch is the authoritative match grade. Do not enter a second one.
    observation.general_rating = float(ev.general_rating)
    if ev.participation:
        observation.observed_position = ev.participation.position or observation.observed_position
    for key, value in (("summary", summary), ("strengths", strengths),
                       ("weaknesses", weaknesses), ("recommendation", recommendation)):
        if value is not None:
            setattr(observation, key, str(value).strip() or None)
    if observation.summary is None and ev.short_note:
        observation.summary = ev.short_note
    observation.status = "submitted"
    observation.submitted_at = observation.submitted_at or UTC_NOW()
    observation.updated_at = UTC_NOW()
    audit(session, author_id, "postmatch_tracking_enriched", "scout_observation", observation.id,
          detail=f"player={ev.player_id}; match={report.match_id}; evaluation={ev.id}; new={created}",
          before=before, after={"rating": observation.general_rating, "summary": observation.summary,
                                "evaluation": ev.id, "status": observation.status})
    session.flush()
    return observation


def tracking_activity(session: Session, season_id: int, limit: int = 40) -> list[dict]:
    """Real submitted events (not speculative notifications), one per match/author/player."""
    rows = list(session.scalars(
        select(ScoutObservation)
        .options(joinedload(ScoutObservation.profile).joinedload(ScoutedPlayerProfile.player),
                 joinedload(ScoutObservation.reviewer), joinedload(ScoutObservation.match).joinedload(Match.home_team),
                 joinedload(ScoutObservation.match).joinedload(Match.away_team))
        .where(ScoutObservation.status == "submitted", ScoutObservation.match_id.in_(
            select(Match.id).where(Match.season_id == int(season_id), official_match_clause())))
        .order_by(ScoutObservation.updated_at.desc(), ScoutObservation.id.desc())
        .limit(max(150, int(limit) * 4))
    ).unique().all())
    seen: set[tuple[int, int, int]] = set()
    result = []
    for obs in rows:
        key = (obs.profile_id, obs.reviewer_id, obs.match_id)
        if key in seen:
            continue
        seen.add(key)
        result.append({"observation": obs, "player": obs.profile.player,
                       "author": obs.reviewer, "match": obs.match})
        if len(result) >= int(limit):
            break
    return result


def duplicate_groups(session: Session, season_id: int) -> list[dict]:
    rows = list(session.scalars(select(ScoutObservation)
        .options(joinedload(ScoutObservation.profile).joinedload(ScoutedPlayerProfile.player),
                 joinedload(ScoutObservation.reviewer), joinedload(ScoutObservation.match).joinedload(Match.home_team),
                 joinedload(ScoutObservation.match).joinedload(Match.away_team))
        .where(ScoutObservation.match_id.in_(select(Match.id).where(Match.season_id == int(season_id),
               official_match_clause())))
        .order_by(ScoutObservation.profile_id, ScoutObservation.reviewer_id, ScoutObservation.match_id, ScoutObservation.id)
    ).unique().all())
    groups: dict[tuple[int, int, int], list[ScoutObservation]] = defaultdict(list)
    for obs in rows:
        groups[(obs.profile_id, obs.reviewer_id, obs.match_id)].append(obs)
    return [{"player": items[0].profile.player, "author": items[0].reviewer,
             "match": items[0].match, "observations": items}
            for items in groups.values() if len(items) > 1]


def delete_duplicate_observation(session: Session, *, observation_id: int, actor_id: int) -> None:
    """DD may delete one explicitly chosen duplicate, never the last evidence row."""
    assert_role(session, int(actor_id), "director")
    obs = session.get(ScoutObservation, int(observation_id))
    if obs is None or obs.match_id is None:
        raise ValueError("La observación no es válida para resolver duplicados.")
    similar = list(session.scalars(select(ScoutObservation).where(
        ScoutObservation.profile_id == obs.profile_id,
        ScoutObservation.reviewer_id == obs.reviewer_id,
        ScoutObservation.match_id == obs.match_id).order_by(ScoutObservation.id)).all())
    if len(similar) < 2:
        raise ValueError("No es un duplicado: no se puede borrar la última observación.")
    if obs.player_evaluation_id is not None:
        raise ValueError("El registro está vinculado al postpartido y es la evidencia principal. Elimina otro duplicado.")
    audit(session, int(actor_id), "delete_duplicate_tracking", "scout_observation", obs.id,
          detail=f"profile={obs.profile_id}; author={obs.reviewer_id}; match={obs.match_id}; retained={','.join(str(x.id) for x in similar if x.id != obs.id)}",
          before={"player_evaluation_id": obs.player_evaluation_id, "rating": obs.general_rating,
                  "summary": obs.summary, "strengths": obs.strengths, "weaknesses": obs.weaknesses,
                  "created_at": obs.created_at.isoformat() if obs.created_at else None})
    session.delete(obs)
    session.flush()


def delete_erroneous_observation(session: Session, *, observation_id: int,
                                 actor_id: int, reason: str) -> None:
    """Exceptionally remove a standalone incorrect entry, never source postmatch data.

    DD must inspect and explicitly document the correction. An audit snapshot
    persists outside the removed row. The postmatch-linked entry is immutable here.
    """
    assert_role(session, int(actor_id), "director")
    reason = (reason or "").strip()
    if len(reason) < 8:
        raise ValueError("Describe el error con al menos ocho caracteres.")
    obs = session.get(ScoutObservation, int(observation_id))
    if obs is None:
        raise ValueError("Observación no encontrada.")
    if obs.player_evaluation_id is not None:
        raise ValueError("Esta observación está vinculada a un postpartido; corrige el informe de origen.")
    if obs.mission_id is not None:
        raise ValueError("Registro histórico vinculado a una misión: requiere revisión administrativa.")
    audit(session, int(actor_id), "delete_erroneous_tracking", "scout_observation", obs.id,
          detail=reason, before={"profile_id": obs.profile_id, "reviewer_id": obs.reviewer_id,
              "match_id": obs.match_id, "rating": obs.general_rating,
              "summary": obs.summary, "strengths": obs.strengths,
              "weaknesses": obs.weaknesses, "source_type": obs.source_type,
              "created_at": obs.created_at.isoformat() if obs.created_at else None})
    session.delete(obs)
    session.flush()
