"""4.5 · anonymous observations and evidence-preserving identity reconciliation."""
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.entities import (Match, Player, PlayerEvaluation, MatchOpinionPlayer,
                             MatchOpinion, Report, UnidentifiedPlayerSignal, User, TeamRoster)
from repositories import users as users_repo
from repositories.common import audit, UTC_NOW
from repositories.data_governance import official_match_clause


def _validate_rank(value):
    if value in (None, "", 0):
        return None
    if int(value) not in (1, 2, 3):
        raise ValueError("El puesto destacado debe ser 1, 2 o 3.")
    return int(value)


def _validate_rating(value):
    if value in (None, "", 0):
        return None
    value = float(value)
    if not 1 <= value <= 10:
        raise ValueError("La nota debe estar entre 1 y 10.")
    return value


def _existing_rank(session, *, match_id, user_id, team_id, rank, exclude_unknown=None,
                   exclude_eval=None, exclude_neutral=None):
    """One rank per author, match and side across identified and unresolved signals."""
    if rank is None:
        return
    qry = select(UnidentifiedPlayerSignal.id).where(
        UnidentifiedPlayerSignal.match_id == match_id, UnidentifiedPlayerSignal.user_id == user_id,
        UnidentifiedPlayerSignal.team_id == team_id, UnidentifiedPlayerSignal.highlight_rank == rank)
    if exclude_unknown:
        qry = qry.where(UnidentifiedPlayerSignal.id != exclude_unknown)
    if session.scalar(qry.limit(1)) is not None:
        raise ValueError(f"Ya has asignado el puesto {rank} a otro futbolista de ese equipo.")
    qry = (select(PlayerEvaluation.id).join(Report, Report.id == PlayerEvaluation.report_id)
           .where(Report.match_id == match_id, Report.reporter_id == user_id,
                  PlayerEvaluation.team_id == team_id, PlayerEvaluation.highlight_rank == rank))
    if exclude_eval:
        qry = qry.where(PlayerEvaluation.id != exclude_eval)
    if session.scalar(qry.limit(1)) is not None:
        raise ValueError(f"Ya has asignado el puesto {rank} a otro futbolista de ese equipo.")
    qry = (select(MatchOpinionPlayer.id).join(MatchOpinion)
           .where(MatchOpinion.match_id == match_id, MatchOpinion.user_id == user_id,
                  MatchOpinionPlayer.team_id == team_id, MatchOpinionPlayer.highlight_rank == rank))
    if exclude_neutral:
        qry = qry.where(MatchOpinionPlayer.id != exclude_neutral)
    if session.scalar(qry.limit(1)) is not None:
        raise ValueError(f"Ya has asignado el puesto {rank} a otro futbolista de ese equipo.")


def save_signal(session: Session, *, actor_id: int, match_id: int, team_id: int,
                position: str | None = None, shirt_number: int | None = None,
                rating: float | None = None, highlight_rank: int | None = None,
                attention_signal: bool = False, note: str | None = None,
                source: str = "own_report", signal_id: int | None = None) -> UnidentifiedPlayerSignal:
    if not users_repo.user_has_role(session, actor_id, "reporter"):
        raise PermissionError("Necesitas el rol Informador para observar a un jugador.")
    match = session.scalar(select(Match).where(Match.id == match_id, official_match_clause()))
    if match is None or team_id not in (match.home_team_id, match.away_team_id):
        raise ValueError("Partido/equipo no oficial o no coincidente.")
    if source not in {"own_report", "neutral"}:
        raise ValueError("Fuente de evidencia inválida.")
    from repositories.players import get_own_team
    own = get_own_team(session)
    is_own_match = bool(own and own.id in (match.home_team_id, match.away_team_id))
    if (source == "own_report") != is_own_match:
        raise ValueError("La fuente no corresponde al tipo de encuentro.")
    number = int(shirt_number) if shirt_number not in (None, "") else None
    if number is not None and not (0 <= number <= 99):
        raise ValueError("Dorsal no válido.")
    rank = _validate_rank(highlight_rank)
    rating = _validate_rating(rating)
    note = (note or "").strip() or None
    position = (position or "").strip().upper()[:20] or None
    if not any((rating, rank, attention_signal, len(note or "") >= 5)):
        raise ValueError("Añade una nota, destacado, señal o apunte real.")
    obj = session.get(UnidentifiedPlayerSignal, signal_id) if signal_id else None
    if signal_id and (not obj or obj.user_id != actor_id or obj.match_id != match_id or obj.team_id != team_id or obj.resolved_player_id):
        raise PermissionError("La señal no pertenece a este autor o ya está resuelta.")
    _existing_rank(session, match_id=match_id, user_id=actor_id, team_id=team_id,
                   rank=rank, exclude_unknown=obj.id if obj else None)
    if obj is None:
        obj = UnidentifiedPlayerSignal(match_id=match_id, team_id=team_id, user_id=actor_id,
                                       source=source, created_at=UTC_NOW())
        session.add(obj)
    obj.position = position
    obj.shirt_number = number
    obj.label = " · ".join(x for x in (position, f"dorsal {number}" if number is not None else None) if x) or "Jugador sin identificar"
    obj.rating = rating
    obj.highlight_rank = rank
    obj.attention_signal = bool(attention_signal or rank is not None)
    obj.note = note
    obj.updated_at = UTC_NOW()
    session.flush()
    audit(session, actor_id, "save_unidentified_signal", "unidentified_player_signal", obj.id, detail=f"match={match_id}; team={team_id}")
    return obj


def unresolved(session: Session, *, season_id: int | None = None, team_id: int | None = None,
               match_id: int | None = None, user_id: int | None = None):
    stmt = (select(UnidentifiedPlayerSignal).join(Match)
            .where(UnidentifiedPlayerSignal.resolved_player_id.is_(None), official_match_clause()))
    if season_id:
        stmt = stmt.where(Match.season_id == season_id)
    if team_id:
        stmt = stmt.where(UnidentifiedPlayerSignal.team_id == team_id)
    if match_id:
        stmt = stmt.where(UnidentifiedPlayerSignal.match_id == match_id)
    if user_id:
        stmt = stmt.where(UnidentifiedPlayerSignal.user_id == user_id)
    return list(session.scalars(stmt.order_by(UnidentifiedPlayerSignal.created_at.desc())).all())


def resolve(session: Session, *, actor_id: int, signal_id: int, player_id: int) -> UnidentifiedPlayerSignal:
    if not users_repo.user_has_role(session, actor_id, "admin", "director"):
        raise PermissionError("La identificación requiere Administración o Dirección Deportiva.")
    obj = session.get(UnidentifiedPlayerSignal, signal_id)
    player = session.get(Player, player_id)
    if obj is None or not player or player.merged_into_id:
        raise ValueError("Señal/jugador no válido.")
    if obj.resolved_player_id and obj.resolved_player_id != player_id:
        raise ValueError("Señal ya resuelta; revisa la corrección antes de reasignar.")
    if obj.resolved_player_id == player_id:
        return obj
    # Match/team context is mandatory. Do not assume participation from roster.
    match = session.get(Match, obj.match_id)
    if session.scalar(select(TeamRoster.id).where(
        TeamRoster.player_id == player_id, TeamRoster.team_id == obj.team_id,
        TeamRoster.season_id == match.season_id).limit(1)) is None:
        # Resolution can still be based on a verified match participation.
        from models.entities import Participation
        exists = session.scalar(select(Participation.id).where(
            Participation.player_id == player_id, Participation.team_id == obj.team_id,
            Participation.match_id == match.id).limit(1))
        if not exists:
            raise ValueError("Vincula antes al jugador con el equipo/temporada o documenta su participación.")
    obj.resolved_player_id = player_id
    obj.resolved_by = actor_id
    obj.resolved_at = UTC_NOW()
    session.flush()
    audit(session, actor_id, "resolve_unidentified_signal", "unidentified_player_signal", obj.id,
          detail=f"player={player_id}; original={obj.label}")
    return obj


def known_position(session: Session, *, player_id: int, team_id: int, season_id: int,
                   match_id: int | None = None) -> str | None:
    from models.entities import Participation
    if match_id:
        part = session.scalar(select(Participation).where(
            Participation.match_id == match_id, Participation.team_id == team_id,
            Participation.player_id == player_id))
        if part and part.position:
            return part.position
    roster = session.scalar(select(TeamRoster).where(
        TeamRoster.player_id == player_id, TeamRoster.team_id == team_id,
        TeamRoster.season_id == season_id))
    if roster and roster.usual_position:
        return roster.usual_position
    player = session.get(Player, player_id)
    return player.primary_position if player else None


def set_usual_position(session: Session, *, actor_id: int, team_id: int, season_id: int,
                       player_id: int, position: str | None):
    if not users_repo.user_has_role(session, actor_id, "admin", "director", "reporter"):
        raise PermissionError("Acceso denegado.")
    row = session.scalar(select(TeamRoster).where(TeamRoster.team_id == team_id,
        TeamRoster.season_id == season_id, TeamRoster.player_id == player_id))
    if row is None:
        raise ValueError("El jugador no está en la plantilla de ese equipo/temporada.")
    row.usual_position = position.strip().upper() if position else None
    audit(session, actor_id, "set_roster_usual_position", "team_roster", row.id,
          detail=f"usual_position={row.usual_position or 'desconocida'}")
    return row


def latest_formation_suggestion(session: Session, *, team_id: int, season_id: int,
                                current_match_id: int) -> tuple[str | None, int | None]:
    """Previous observed team shape, not a fact about the current fixture."""
    current = session.get(Match, current_match_id)
    if current is None:
        return None, None
    candidates = session.scalars(select(Match).where(
        Match.season_id == season_id, Match.id != current_match_id,
        Match.match_date <= current.match_date, official_match_clause(),
        ((Match.home_team_id == team_id) & Match.home_formation_known.is_(True)) |
        ((Match.away_team_id == team_id) & Match.away_formation_known.is_(True)))
        .order_by(Match.match_date.desc(), Match.id.desc()).limit(15)).all()
    for match in candidates:
        form = match.home_formation if match.home_team_id == team_id else match.away_formation
        if form:
            return form, match.id
    return None, None
