"""4.7.2: small, permission-checked rating workflow backed by real roster IDs.

A roster entry is a candidate for evaluation, NOT evidence that the player played.
The view must label this distinction. Opponent positional slots without names are
anonymous observations, never automatically promoted to a Player identity.
"""
from __future__ import annotations
import json
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from models.entities import (Match, Player, TeamRoster, Participation, SportingContribution47 as Contribution,
                             PlayerProposal47 as Proposal)
from repositories import collaboration47 as domain
from repositories.players import get_own_team
from core.formations import slots_for


def choices(session, match_id, team_id):
    match = session.get(Match, int(match_id))
    if match is None or int(team_id) not in (match.home_team_id, match.away_team_id):
        raise ValueError('El equipo no pertenece a este encuentro.')
    participations = list(session.scalars(select(Participation).options(joinedload(Participation.player))
                         .where(Participation.match_id == match.id, Participation.team_id == team_id)
                         .order_by(Participation.starter.desc(), Participation.order_index, Participation.id)).all())
    if participations:
        # A named bench player who never entered must not be rated as having played.
        actually_played=[p for p in participations if p.starter or p.minute_out>p.minute_in]
        return ([{'key':f'p:{p.player_id}', 'player_id':p.player_id,
                  'name':p.player.full_name, 'dorsal':p.shirt_number,
                  'position':p.position or p.player.primary_position or '',
                  'status':'Titular' if p.starter else 'Participó'} for p in actually_played], True)
    roster = list(session.scalars(select(TeamRoster).options(joinedload(TeamRoster.player))
                          .where(TeamRoster.season_id == match.season_id, TeamRoster.team_id == team_id,
                                 TeamRoster.active.is_(True))
                          .order_by(TeamRoster.shirt_number, TeamRoster.id)).all())
    return ([{'key':f'p:{r.player_id}', 'player_id':r.player_id,
              'name':r.player.full_name, 'dorsal':r.shirt_number,
              'position':r.player.primary_position or '', 'status':'En plantilla'}
             for r in roster], False)


def positional_choices(formation='4-2-3-1'):
    slots = slots_for(formation)
    if not slots:
        raise ValueError('No se admite esa formación.')
    return [{'key':f'z:{formation}:{idx}', 'player_id':None, 'name':slot.label,
             'dorsal':None, 'position':slot.code, 'status':'Posición provisional'}
            for idx, slot in enumerate(slots)]


def existing(session, *, author_id, match_id):
    records = list(session.scalars(select(Contribution).where(Contribution.author_id == author_id,
        Contribution.match_id == match_id, Contribution.status == 'shared', Contribution.kind.in_(['quick','individual']))
        .order_by(Contribution.id)).all())
    team_rating = None
    annotated = {}
    proposal_ids=set(session.scalars(select(Proposal.contribution_id).where(
        Proposal.author_id==author_id, Proposal.match_id==match_id,
        Proposal.contribution_id.is_not(None))).all())
    for rec in records:
        try: data = json.loads(rec.data_json or '{}')
        except (ValueError,TypeError): continue
        if rec.kind == 'quick': team_rating = data.get('nota_noname')
        elif data.get('source')=='mobile472' and data.get('key'):
            annotated[f"{rec.team_id}:{data['key']}"] = {
                'score':data.get('nota'), 'comment':data.get('comentario') or '',
                'favorite':rec.id in proposal_ids}
    return team_rating, annotated


def _score(value):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not 1 <= value <= 10:
        raise ValueError('La nota debe estar entre 1 y 10.')
    return int(value) if float(value).is_integer() else float(value)


def save_board(session, *, actor_id, match_id, team_id, payload):
    """Persist own-team grade and optional per-player observations atomically.

    Client-submitted IDs, positions, match/team and arbitrary JSON are NOT trusted.
    Cross-team or unrostered player IDs and duplicate rows are rejected.
    """
    if not isinstance(payload, dict): raise ValueError('Formato inválido.')
    match = session.get(Match, int(match_id))
    if match is None: raise ValueError('Encuentro inexistente.')
    from repositories.publication473 import is_open
    if not is_open(session, match.id):
        raise PermissionError('El partido todavía no está publicado para valorar.')
    own = get_own_team(session)
    if int(team_id) not in {match.home_team_id,match.away_team_id}:
        raise ValueError('El equipo seleccionado no pertenece al encuentro.')
    is_own = bool(own and int(team_id) == own.id)
    board=payload.get('players', [])
    if not isinstance(board,list) or len(board)>40:raise ValueError('Lista de jugadores inválida.')
    members,confirmed = choices(session,match_id,team_id)
    permitted={r['key']:r for r in members}
    if not confirmed:
        raise ValueError('Falta la alineación confirmada del equipo.')
    removed = payload.get('cleared', [])
    if not isinstance(removed,list) or len(removed)>40:
        raise ValueError('La lista de notas retiradas es inválida.')
    clear_keys=set()
    for entry in removed:
        if not isinstance(entry,str) or entry not in permitted or entry in clear_keys:
            raise PermissionError('No puedes retirar una nota de otro jugador.')
        clear_keys.add(entry)
    notes=[]; seen=set()
    for item in board:
        if not isinstance(item,dict) or not isinstance(item.get('key'),str):raise ValueError('Entrada inválida.')
        key=item['key']
        if key in seen: raise ValueError('El mismo jugador aparece repetido.')
        seen.add(key)
        if key in clear_keys: raise ValueError('Una nota no puede guardarse y retirarse a la vez.')
        ref=permitted.get(key)
        if ref is None:raise PermissionError('Jugador o posición ajenos a la plantilla del encuentro.')
        raw_score=item.get('score')
        comment=str(item.get('comment') or '').strip()
        if len(comment)>1200: raise ValueError('El comentario es demasiado largo.')
        favorite=item.get('favorite') is True
        if raw_score is None and not comment and not favorite:continue
        notes.append((ref,_score(raw_score) if raw_score is not None else None,comment,favorite))
    if len(notes)>30: raise ValueError('Demasiadas observaciones para un encuentro.')
    team_score=payload.get('team_score')
    if team_score is not None:
        if not is_own:raise ValueError('La nota colectiva rápida es exclusiva de Noname.')
        team_score=_score(team_score)
    if team_score is None and not notes and not clear_keys:
        raise ValueError('Selecciona una nota o algún jugador.')
    # Check permissions and all user data before touching any record.
    domain._reporter(session, actor_id)
    previous = list(session.scalars(select(Contribution).where(
        Contribution.author_id == actor_id, Contribution.match_id == match.id,
        Contribution.kind == 'individual', Contribution.team_id == team_id)).all())
    by_key={}
    for row in previous:
        if row.status != 'shared': continue
        try: data=json.loads(row.data_json or '{}')
        except (ValueError,TypeError):continue
        if data.get('source')=='mobile472' and data.get('key'):by_key[data['key']]=row
    # A retraction keeps signed evidence in the audit trail while removing
    # its score from the active per-player/season aggregates.
    for key in clear_keys:
        old = by_key.get(key)
        if old is not None:
            old.status = 'retracted'
            old.revision += 1
            old.updated_at = domain.UTC_NOW()
            from repositories.common import audit
            audit(session,actor_id,'retract_individual_rating_474','sporting_contribution_47',old.id,
                  detail=f'match={match.id}; team={team_id}; key={key}')
    if team_score is not None:
        domain.save_contribution(session,actor_id=actor_id,season_id=match.season_id,
           match_id=match.id,team_id=team_id,kind='quick',title=f'Valoración Noname · {match.round_name}',
           data={'nota_noname':team_score,'comentario':str(payload.get('team_comment') or '')[:1200]},publish=True)
    saved=0; proposed=0
    for ref,score,comment,favorite in notes:
        old=by_key.get(ref['key'])
        data={'source':'mobile472','key':ref['key'],'nota':score,'comentario':comment,
              'posicion_observada':ref['position'], 'dorsal_observado':ref['dorsal'],
              'nombre_observado':ref['name'],'plantilla_no_confirma_participacion':not confirmed}
        unchanged=False
        if old:
            try:
                prev=json.loads(old.data_json or '{}')
                unchanged=all(prev.get(k)==data.get(k) for k in data)
            except (ValueError,TypeError):
                unchanged=False
        if unchanged:
            row=old
        else:
            row=domain.save_contribution(session,actor_id=actor_id,season_id=match.season_id,
                match_id=match.id,team_id=team_id,player_id=ref['player_id'],kind='individual',
                title=f'Valoración · {ref["name"]}',data=data,publish=True,
                contribution_id=old.id if old else None,expected_revision=old.revision if old else None,
                notify=False)
        saved+=1
        # Favorite is explicit; repeated Save must not resend the same proposal.
        if favorite:
            from models.entities import PlayerProposal47 as Proposal
            existing_proposal=session.scalar(select(Proposal.id).where(
                Proposal.author_id==actor_id, Proposal.contribution_id==row.id).limit(1))
            if not existing_proposal:
                domain.propose_player(session,actor_id=actor_id,season_id=match.season_id,
                    match_id=match.id,player_id=ref['player_id'],contribution_id=row.id,
                    subject=f'{ref["name"]} · {ref["position"] or "jugador"}',
                    reason=comment or 'Futbolista destacado expresamente por el informador para Dirección Deportiva.')
                proposed+=1
    return {'evaluados':saved,'retiradas':sum(k in by_key for k in clear_keys),
            'propuestas':proposed,'equipo':team_score is not None}
