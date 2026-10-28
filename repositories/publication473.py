"""4.7.4 · Explicit publication of rated games, with two complete named XIs.

All operations happen inside the caller's Session transaction. No migration
backfills publication for historical games, and a client cannot self-publish.
"""
from __future__ import annotations
from core.clock import local_today
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from models.entities import (Match, Team, MatchRatingRelease473 as Release, Participation,
                             TeamRoster, Player, SportingContribution47)
from repositories.common import audit
from repositories.matches import _assert_delegated_roster_editor, replace_participations
from repositories import players as players_repo
from core.lineup473 import parse_xi, XIPlayer
from core.utils import normalize_name


def is_open(session, match_id: int) -> bool:
    return bool(session.scalar(select(Release.id).where(Release.match_id==int(match_id))))


def opened_match_ids(session, match_ids: list[int]) -> set[int]:
    if not match_ids:return set()
    return set(session.scalars(select(Release.match_id).where(Release.match_id.in_(match_ids))).all())


def _validate_existing(session, match: Match, team_id: int) -> list[Participation]:
    rows=list(session.scalars(select(Participation).options(joinedload(Participation.player)).where(
        Participation.match_id==match.id, Participation.team_id==team_id,
        Participation.starter.is_(True))).all())
    if len(rows)!=11:
        raise ValueError(f"{len(rows)}/11 titulares en el equipo; debes cargar once para publicar.")
    shirts=[r.shirt_number for r in rows]
    if any(x is None or not 1<=x<=99 for x in shirts) or len(set(shirts))!=11:
        raise ValueError("Los dorsales de los once titulares deben ser únicos y válidos.")
    if len(set(r.player_id for r in rows))!=11:
        raise ValueError("Hay futbolistas duplicados en la alineación.")
    if any(not r.player or not r.player.full_name or not r.position for r in rows):
        raise ValueError("Cada titular necesita nombre y posición confirmados.")
    from core.lineup473 import ALLOWED
    if any(r.position not in ALLOWED for r in rows):
        raise ValueError("Hay posiciones sin reconocer; corrígelas antes de publicar.")
    if sum(r.position=='POR' for r in rows)!=1:
        raise ValueError("Cada XI debe tener un portero.")
    return rows


def readiness(session, match_id: int) -> dict:
    match=session.get(Match,int(match_id))
    if not match:raise ValueError("Partido no encontrado.")
    summary={"published":is_open(session,match.id),"teams":{}}
    for team_id in (match.home_team_id,match.away_team_id):
        count=session.scalar(select(func.count(Participation.id)).where(
            Participation.match_id==match.id,Participation.team_id==team_id,
            Participation.starter.is_(True))) or 0
        try:_validate_existing(session,match,team_id);valid=True;reason=None
        except ValueError as e:valid=False;reason=str(e)
        summary["teams"][team_id]={"starters":int(count),"ready":valid,"reason":reason}
    return summary


def _attach_xi(session,match:Match,team_id:int,actor_id:int,players:list[XIPlayer]):
    current=list(session.scalars(select(TeamRoster).options(joinedload(TeamRoster.player)).where(
        TeamRoster.team_id==team_id,TeamRoster.season_id==match.season_id,
        TeamRoster.active.is_(True))).all())
    known={}
    for r in current:known.setdefault(normalize_name(r.player.full_name),[]).append(r.player)
    assignment=[]
    for p in players:
        found=known.get(normalize_name(p.name),[])
        if len(found)>1:
            raise ValueError(f"Jugador '{p.name}' duplicado en la plantilla. Resuélvelo antes de publicar.")
        if found:obj=found[0]
        else:
            candidates=[c for c in players_repo.find_player_candidates(session,p.name) if c.active and not c.merged_into_id]
            if len(candidates)>1:
                raise ValueError(f"Identidad ambigua: {p.name}. Corrígela desde Jugadores.")
            if candidates:
                obj=candidates[0]
                other_club=session.scalar(select(TeamRoster.id).where(
                    TeamRoster.player_id==obj.id,TeamRoster.season_id==match.season_id,
                    TeamRoster.team_id!=team_id,TeamRoster.active.is_(True)).limit(1))
                if other_club is not None:
                    raise ValueError(f"Homónimo o cambio de club: '{p.name}'. Confirma la identidad en Jugadores antes de importar.")
                # Do not reuse an identity already associated with the other club
                # in this same fixture; equal names are not proof of identity.
                if session.scalar(select(Participation.id).where(Participation.player_id==obj.id,
                            Participation.match_id==match.id, Participation.team_id!=team_id)):
                    raise ValueError(f"'{p.name}' figura en otro equipo. Revisa identidad antes de publicar.")
            else:obj=players_repo.find_or_create_player(session,p.name,primary_position=p.position,actor_id=actor_id)
            players_repo.assign_player_to_roster(session,team_id,match.season_id,obj.id,p.shirt,actor_id)
            known.setdefault(normalize_name(p.name),[]).append(obj)
        assignment.append({"player_id":obj.id,"shirt_number":p.shirt,"starter":p.starter,
            "position":p.position,"minute_in":0,"minute_out":90 if p.starter else 0,
            "selected":True,"order_index":len(assignment)})
    replace_participations(session,match.id,team_id,assignment,actor_id)


def publish_match(session, *, actor_id:int, match_id:int,
                  home_text:str|None=None, away_text:str|None=None) -> Release:
    """One deliberate, atomic act: optionally import both teams, then publish.

    Blank text means reuse a previously saved official XI. An incomplete,
    ambiguous or invalid side blocks the transaction for both sides.
    """
    _assert_delegated_roster_editor(session,actor_id)
    match=session.scalar(select(Match).where(Match.id==int(match_id)).with_for_update())
    if not match or match.deleted_at is not None or match.is_test or match.status=='archived':
        raise ValueError("El encuentro no está disponible.")
    if match.schedule_status in {'postponed','cancelled'}:
        raise ValueError("No se puede publicar un encuentro aplazado o suspendido.")
    if match.match_date>local_today():
        raise ValueError("El encuentro todavía no se ha disputado.")
    if is_open(session,match.id):
        raise ValueError("El partido ya está publicado para valorar. No se volverá a importar su XI.")
    prepared={}
    for team_id, text in ((match.home_team_id,home_text),(match.away_team_id,away_text)):
        if text and text.strip():
            name=session.get(Team,team_id).name
            prepared[team_id]=parse_xi(text,team_name=name)
    for team_id,lineup in prepared.items():
        _attach_xi(session,match,team_id,actor_id,lineup)
    session.flush()
    for tid in (match.home_team_id,match.away_team_id):
        _validate_existing(session,match,tid)
    release=Release(match_id=match.id,published_by=actor_id)
    session.add(release)
    session.flush()
    audit(session,actor_id,"publish_match_ratings_473","match",match.id,
          detail="Dos XI identificados y validados. Valoraciones habilitadas.")
    return release


def register_substitute(session, *, actor_id:int, match_id:int, team_id:int,
                        name:str, shirt:int, position:str, minute_in:int,
                        minute_out:int=90):
    """Record a verified substitute after publication without replacing the XI.

    Reuses an identity only when it is unambiguous in this team's season roster;
    unknown names are created as new local identities, never borrowed from a
    homonymous player of a different club.
    """
    _assert_delegated_roster_editor(session,actor_id)
    match=session.get(Match,int(match_id))
    if not match or not is_open(session,match.id):
        raise ValueError('El encuentro debe estar publicado para añadir suplentes.')
    if int(team_id) not in (match.home_team_id,match.away_team_id):
        raise ValueError('El equipo no corresponde al encuentro.')
    from core.lineup473 import ALLOWED
    from models.entities import Player
    from core.utils import normalize_name
    cleaned=' '.join(str(name).strip().split())
    if len(cleaned)<2 or len(cleaned)>180 or not any(c.isalpha() for c in cleaned):
        raise ValueError('Escribe el nombre real del suplente.')
    position=str(position).upper().strip()
    if position not in ALLOWED:raise ValueError('Posición no reconocida.')
    try:shirt=int(shirt);minute_in=int(minute_in);minute_out=int(minute_out)
    except (ValueError,TypeError):raise ValueError('Dorsal y minutos deben ser números.') from None
    if not 1<=shirt<=99 or not 0<=minute_in<=minute_out<=130:
        raise ValueError('Comprueba dorsal y minutos de participación.')
    existing=list(session.scalars(select(Participation).where(
        Participation.match_id==match.id,Participation.team_id==int(team_id))).all())
    if any(p.shirt_number==shirt for p in existing):
        raise ValueError('El dorsal ya pertenece a otro participante de este encuentro.')
    own_roster=list(session.scalars(select(TeamRoster).options(joinedload(TeamRoster.player)).where(
        TeamRoster.team_id==int(team_id),TeamRoster.season_id==match.season_id,
        TeamRoster.active.is_(True))).all())
    candidates=[r.player for r in own_roster if normalize_name(r.player.full_name)==normalize_name(cleaned)]
    if len(candidates)>1:raise ValueError('Nombre ambiguo en plantilla; revisa la identidad.')
    if candidates:player=candidates[0]
    else:
        player=Player(full_name=cleaned,normalized_name=normalize_name(cleaned),
                      primary_position=position,active=True)
        session.add(player);session.flush()
        players_repo.assign_player_to_roster(session,team_id,match.season_id,player.id,shirt,actor_id)
    if any(p.player_id==player.id for p in existing):
        raise ValueError('Este futbolista ya aparece en el partido.')
    part=Participation(match_id=match.id,team_id=int(team_id),player_id=player.id,
        shirt_number=shirt,position=position,starter=False,
        minute_in=minute_in,minute_out=minute_out,order_index=len(existing)+1)
    session.add(part);session.flush()
    audit(session,actor_id,'add_confirmed_substitute_474','participation',part.id,
        detail=f'match={match.id}; team={team_id}; shirt={shirt}; minute={minute_in}-{minute_out}')
    return part
