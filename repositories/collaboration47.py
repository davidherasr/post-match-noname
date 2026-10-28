"""4.7 sporting collaboration: permission checks at the repository boundary.

No new activity is inferred from old draft records. Every event is an explicit
business transition. A read never acknowledges an item; the user controls X.
"""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session
from models.entities import (
    SportingContribution47 as Contribution, ActivityEvent47 as Event,
    ActivityState47 as EventState, PlayerProposal47 as Proposal,
    StaffRequest47 as StaffRequest, DataCorrection47 as Correction,
    MatchPriority47 as Priority, Match, User, Player, Season,
)
from repositories.users import assert_role, user_has_role
from repositories.common import audit, UTC_NOW
from repositories.data_governance import official_match_clause

KINDS = {'quick', 'complete', 'individual', 'general', 'synthesis', 'formation'}
PRIORITIES = {'Normal', 'Alta', 'Muy importante'}


def _actor(session, uid):
    user = session.get(User, int(uid))
    if not user or not user.active or user.deleted_at is not None:
        raise PermissionError('Usuario inexistente o inactivo.')
    return user


def _reporter(session, uid):
    _actor(session, uid)
    if not user_has_role(session, uid, 'reporter'):
        raise PermissionError('Esta aportación requiere rol Informador.')


def _director(session, uid):
    _actor(session, uid)
    if not user_has_role(session, uid, 'director'):
        raise PermissionError('Solo Dirección Deportiva puede realizar esta acción.')


def _admin(session, uid):
    _actor(session, uid)
    if not user_has_role(session, uid, 'admin'):
        raise PermissionError('Acceso exclusivo de Administración.')


def _match(session, season_id, match_id):
    if match_id is None:
        return None
    obj = session.scalar(select(Match).where(Match.id == int(match_id),
        Match.season_id == int(season_id), official_match_clause()))
    if obj is None:
        raise ValueError('Partido oficial inexistente en la temporada elegida.')
    return obj


def _json(payload):
    if not isinstance(payload, dict):
        raise ValueError('La observación debe tener datos estructurados.')
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    if len(raw) > 32000:
        raise ValueError('La observación es demasiado extensa.')
    return raw


def _event(session, *, season_id, actor_id, kind, title, target_type, target_id,
           audience='director', recipient_id=None, detail=None):
    row = Event(season_id=season_id, actor_id=actor_id, kind=kind, title=title[:220],
                target_type=target_type, target_id=target_id, audience=audience,
                recipient_id=recipient_id, detail=(detail or '')[:2000])
    session.add(row)
    session.flush()
    return row


def save_contribution(session: Session, *, actor_id: int, season_id: int,
                      kind: str, title: str, data: dict, match_id=None,
                      player_id=None, team_id=None, contribution_id=None,
                      expected_revision=None, publish=False):
    _reporter(session, actor_id)
    if kind not in KINDS or not title.strip():
        raise ValueError('Tipo o título de observación inválidos.')
    _match(session, season_id, match_id)
    if session.get(Season, int(season_id)) is None:
        raise ValueError('Temporada inexistente.')
    if player_id is not None and session.get(Player, int(player_id)) is None:
        raise ValueError('Jugador inexistente.')
    payload = _json(data)
    # Repeated quick save from another tab or a retried submit must update the
    # original note. A partial unique DB index protects concurrent requests.
    if kind=='quick' and match_id is not None and contribution_id is None:
        earlier=session.scalar(select(Contribution).where(Contribution.author_id==actor_id,
            Contribution.match_id==match_id,Contribution.kind=='quick').with_for_update())
        if earlier is not None: contribution_id=earlier.id
    if not any(str(v).strip() for v in data.values() if v is not None):
        raise ValueError('Introduce una observación antes de guardar.')
    if contribution_id:
        row = session.get(Contribution, int(contribution_id))
        if not row or row.author_id != actor_id:
            raise PermissionError('Solo puedes modificar tus aportaciones.')
        if row.season_id != int(season_id) or row.kind != kind:
            raise ValueError('No puedes cambiar el tipo o temporada de una aportación existente.')
        if row.status == 'shared' and kind != 'quick':
            raise ValueError('Un informe compartido es inmutable. Crea una ampliación independiente.')
        if expected_revision is not None and row.revision != int(expected_revision):
            raise RuntimeError('Otra sesión ha modificado esta aportación. Recarga antes de guardar.')
        was_shared = row.status == 'shared'
        row.revision += 1
    else:
        row = Contribution(author_id=int(actor_id), season_id=int(season_id), kind=kind)
        session.add(row)
        was_shared = False
    row.match_id = match_id
    row.player_id = player_id
    row.team_id = team_id
    row.title = title.strip()[:180]
    row.data_json = payload
    row.updated_at = UTC_NOW()
    if publish:
        row.status = 'shared'
        row.published_at = row.published_at or UTC_NOW()
    else:
        if not was_shared:
            row.status = 'draft'
    session.flush()
    if publish and not was_shared:
        _event(session, season_id=row.season_id, actor_id=actor_id, kind='contribution',
               title='Nueva aportación deportiva', target_type='contribution', target_id=row.id,
               detail=row.title)
    elif publish and was_shared:
        _event(session, season_id=row.season_id, actor_id=actor_id, kind='contribution_update',
               title='Valoración actualizada', target_type='contribution', target_id=row.id,
               detail=row.title)
    audit(session, actor_id, 'save_sporting_contribution_47', 'sporting_contribution_47', row.id,
          detail=f'kind={kind}; state={row.status}; revision={row.revision}')
    return row


def publish_draft(session, *, actor_id, contribution_id):
    _reporter(session, actor_id)
    row = session.get(Contribution, int(contribution_id))
    if not row or row.author_id != int(actor_id):
        raise PermissionError('No puedes publicar esta aportación.')
    if row.status == 'shared':
        return row
    row.status = 'shared'
    row.published_at = UTC_NOW()
    row.updated_at = UTC_NOW()
    row.revision += 1
    session.flush()
    _event(session, season_id=row.season_id, actor_id=actor_id,
           kind='contribution', title='Nueva aportación deportiva',
           target_type='contribution', target_id=row.id, detail=row.title)
    audit(session, actor_id, 'publish_sporting_contribution_47', 'sporting_contribution_47', row.id)
    return row


def can_read_contribution(session, row: Contribution, actor_id: int) -> bool:
    if row.author_id == int(actor_id):
        return True
    if row.status != 'shared':
        return False
    return user_has_role(session, actor_id, 'director', 'admin')


def get_contribution(session, contribution_id: int, actor_id: int):
    _actor(session, actor_id)
    row = session.get(Contribution, int(contribution_id))
    if not row or not can_read_contribution(session, row, actor_id):
        raise PermissionError('Aportación no disponible para esta cuenta.')
    return row


def list_contributions(session, *, actor_id: int, season_id: int, own_only=False,
                       match_id=None, player_id=None, limit=100):
    _actor(session, actor_id)
    is_privileged = user_has_role(session, actor_id, 'director', 'admin')
    conditions = [Contribution.season_id == int(season_id)]
    if own_only or not is_privileged:
        conditions.append(Contribution.author_id == int(actor_id))
    else:
        conditions.append(or_(Contribution.author_id == int(actor_id), Contribution.status == 'shared'))
    if match_id is not None:
        conditions.append(Contribution.match_id == int(match_id))
    if player_id is not None:
        conditions.append(Contribution.player_id == int(player_id))
    return list(session.scalars(select(Contribution).where(*conditions)
        .order_by(Contribution.updated_at.desc(), Contribution.id.desc())
        .limit(max(1, min(int(limit), 300)))).all())


def propose_player(session, *, actor_id, season_id, subject, reason,
                   player_id=None, match_id=None, contribution_id=None):
    _reporter(session, actor_id)
    if not subject.strip() or len(reason.strip()) < 5:
        raise ValueError('Describe qué futbolista propones y por qué.')
    _match(session, season_id, match_id)
    if contribution_id is not None:
        source = session.get(Contribution, int(contribution_id))
        if not source or source.author_id != actor_id or source.status != 'shared' or source.season_id != int(season_id):
            raise PermissionError('Solo puedes proponer desde una aportación propia compartida.')
    if player_id is not None and session.get(Player, int(player_id)) is None:
        raise ValueError('Jugador inexistente.')
    row = Proposal(author_id=actor_id, season_id=season_id,
        subject=subject.strip()[:180], reason=reason.strip(), player_id=player_id,
        match_id=match_id, contribution_id=contribution_id)
    session.add(row)
    session.flush()
    _event(session, season_id=season_id, actor_id=actor_id, kind='proposal',
           title='Jugador propuesto a Dirección Deportiva', target_type='proposal',
           target_id=row.id, detail=row.subject)
    audit(session, actor_id, 'propose_player_47', 'player_proposal_47', row.id)
    return row


def list_proposals(session, actor_id, season_id):
    _actor(session, actor_id)
    stmt = select(Proposal).where(Proposal.season_id == season_id)
    if not user_has_role(session, actor_id, 'director', 'admin'):
        # JSON text is checked again in Python to avoid a substring-based ACL.
        stmt = stmt.where(or_(Proposal.author_id == actor_id, Proposal.shared_with != '[]'))
    rows = list(session.scalars(stmt.order_by(Proposal.created_at.desc(), Proposal.id.desc())).all())
    if user_has_role(session, actor_id, 'director', 'admin'):
        return rows
    return [p for p in rows if p.author_id == actor_id or actor_id in json.loads(p.shared_with or '[]')]


def get_proposal(session, proposal_id, actor_id):
    row = session.get(Proposal, int(proposal_id))
    if not row or not (row.author_id == actor_id or user_has_role(session, actor_id, 'director', 'admin')
                       or actor_id in json.loads(row.shared_with or '[]')):
        raise PermissionError('Propuesta privada o inexistente.')
    return row


def decide_proposal(session, *, actor_id, proposal_id, state):
    _director(session, actor_id)
    if state not in {'saved', 'tracking', 'dismissed', 'new'}:
        raise ValueError('Estado desconocido.')
    row = get_proposal(session, proposal_id, actor_id)
    before = row.state
    if before == state:
        return row
    row.state = state
    row.decided_by = actor_id
    row.decided_at = UTC_NOW()
    row.updated_at = UTC_NOW()
    session.flush()
    _event(session, season_id=row.season_id, actor_id=actor_id, kind='proposal_decision',
           title='Dirección Deportiva ha revisado una propuesta',
           target_type='proposal', target_id=row.id, detail=f'{row.subject} · {state}',
           audience='recipient', recipient_id=row.author_id)
    audit(session, actor_id, 'decide_proposal_47', 'player_proposal_47', row.id,
          before={'state': before}, after={'state': state})
    return row


def create_request(session, *, actor_id, recipient_id, season_id, subject, question,
                   player_id=None, match_id=None, proposal_id=None, priority='Normal'):
    _director(session, actor_id)
    recipient = _actor(session, recipient_id)
    if not user_has_role(session, recipient.id, 'reporter'):
        raise ValueError('El destinatario debe tener permiso para informar.')
    _match(session, season_id, match_id)
    if proposal_id is not None:
        proposal=get_proposal(session,proposal_id,actor_id)
        if proposal.season_id != season_id:
            raise ValueError('La propuesta pertenece a otra temporada.')
        if proposal.player_id is not None and player_id is not None and proposal.player_id != player_id:
            raise ValueError('El jugador no coincide con la propuesta original.')
    if priority not in PRIORITIES or not subject.strip() or not question.strip():
        raise ValueError('Solicitud incompleta o prioridad inválida.')
    row = StaffRequest(sender_id=actor_id, recipient_id=recipient_id,
        season_id=season_id, subject=subject.strip()[:180], question=question.strip(),
        match_id=match_id, player_id=player_id, proposal_id=proposal_id, priority=priority)
    session.add(row)
    session.flush()
    _event(session, season_id=season_id, actor_id=actor_id, kind='request',
           title='Nueva solicitud de Dirección Deportiva', target_type='request',
           target_id=row.id, detail=row.subject, audience='recipient', recipient_id=recipient_id)
    audit(session, actor_id, 'create_staff_request_47', 'staff_request_47', row.id)
    return row


def list_requests(session, *, actor_id, season_id, include_closed=True):
    _actor(session, actor_id)
    stmt = select(StaffRequest).where(StaffRequest.season_id == season_id,
       or_(StaffRequest.sender_id == actor_id, StaffRequest.recipient_id == actor_id))
    if not include_closed:
        stmt = stmt.where(StaffRequest.state == 'pending')
    return list(session.scalars(stmt.order_by(StaffRequest.created_at.desc(), StaffRequest.id.desc())).all())


def respond_request(session, *, actor_id, request_id, answer, contribution_id=None):
    _reporter(session, actor_id)
    row = session.get(StaffRequest, int(request_id))
    if not row or row.recipient_id != actor_id or row.state != 'pending':
        raise PermissionError('Esta solicitud no está disponible para responder.')
    if contribution_id is not None:
        source=get_contribution(session,contribution_id,actor_id)
        if source.author_id != actor_id or source.status!='shared':
            raise PermissionError('Solo puedes asociar un informe propio ya compartido con DD.')
        if source.season_id != row.season_id:
            raise ValueError('Informe y solicitud pertenecen a temporadas diferentes.')
        if row.match_id is not None and source.match_id != row.match_id:
            raise ValueError('El informe no corresponde al partido solicitado.')
        if row.player_id is not None and source.player_id != row.player_id:
            raise ValueError('El informe no corresponde al jugador solicitado.')
    if not (answer or '').strip() and contribution_id is None:
        raise ValueError('Escribe una respuesta o selecciona un informe ya compartido.')
    row.response_contribution_id=contribution_id
    row.answer=(answer or '').strip()
    row.state = 'answered'
    row.answered_at = UTC_NOW()
    row.updated_at = UTC_NOW()
    session.flush()
    _event(session, season_id=row.season_id, actor_id=actor_id, kind='response',
        title='Respuesta a una solicitud', target_type='request', target_id=row.id,
        detail=row.subject, audience='recipient', recipient_id=row.sender_id)
    audit(session, actor_id, 'respond_staff_request_47', 'staff_request_47', row.id)
    return row


def close_request(session, *, actor_id, request_id):
    _director(session, actor_id)
    row = session.get(StaffRequest, int(request_id))
    if not row or row.sender_id != actor_id:
        raise PermissionError('No puedes cerrar una solicitud ajena.')
    row.state = 'closed'
    row.updated_at = UTC_NOW()
    audit(session, actor_id, 'close_staff_request_47', 'staff_request_47', row.id)
    return row


def visible_events(session, *, actor_id, season_id, filter_by='new', limit=100):
    _actor(session, actor_id)
    is_dd = user_has_role(session, actor_id, 'director', 'admin')
    allowed = [and_(Event.audience == 'recipient', Event.recipient_id == actor_id),
               and_(Event.audience == 'author', Event.actor_id == actor_id)]
    if is_dd:
        allowed.append(Event.audience == 'director')
    stmt = select(Event, EventState).outerjoin(EventState,
        and_(EventState.event_id == Event.id, EventState.user_id == actor_id))
    stmt = stmt.where(Event.season_id == int(season_id), or_(*allowed))
    if filter_by == 'new':
        # Migrated reports are an archive, not a flood of artificial first-login
        # notifications on the day 4.7 is installed.
        stmt = stmt.where(EventState.seen_at.is_(None),
                          Event.kind.notin_({'legacy_report','legacy_opinion'}))
    if filter_by == 'saved':
        stmt = stmt.where(EventState.saved_at.is_not(None))
    # A persistent business task is not interchangeable with event read state.
    return list(session.execute(stmt.order_by(Event.created_at.desc(), Event.id.desc())
        .limit(max(1, min(int(limit), 250)))).all())


def change_event_state(session, *, actor_id, event_id, action):
    _actor(session, actor_id)
    if action not in {'seen', 'save', 'unsave', 'unsee'}:
        raise ValueError('Acción de bandeja desconocida.')
    event = session.get(Event, int(event_id))
    if not event:
        raise ValueError('Evento inexistente.')
    # Critical: visibility checked on *every* state mutation, not only UI.
    allowed = ((event.audience == 'recipient' and event.recipient_id == actor_id) or
               (event.audience == 'author' and event.actor_id == actor_id) or
               (event.audience == 'director' and user_has_role(session, actor_id, 'director', 'admin')))
    if not allowed:
        raise PermissionError('No puedes modificar esta notificación.')
    state = session.scalar(select(EventState).where(
        EventState.event_id == event_id, EventState.user_id == actor_id))
    if state is None:
        state = EventState(event_id=event_id, user_id=actor_id)
        session.add(state)
    if action in ('seen', 'unsee'):
        state.seen_at = UTC_NOW() if action == 'seen' else None
    else:
        state.saved_at = UTC_NOW() if action == 'save' else None
    session.flush()
    return state


def create_correction(session, *, actor_id, description, entity_type,
                      entity_id=None, season_id=None):
    _actor(session, actor_id)
    if not description.strip() or entity_type not in {'match','player','team','roster','other'}:
        raise ValueError('Describe el error y el tipo de dato afectado.')
    row = Correction(author_id=actor_id, description=description.strip()[:4000],
                     entity_type=entity_type, entity_id=entity_id, season_id=season_id)
    session.add(row)
    session.flush()
    if season_id is not None:
        _event(session, season_id=season_id, actor_id=actor_id, kind='correction',
            title='Incidencia de datos comunicada', target_type='correction',
            target_id=row.id, audience='recipient', recipient_id=actor_id)
    audit(session, actor_id, 'create_data_correction_47', 'data_correction_47', row.id)
    return row


def list_corrections(session, *, actor_id, only_open=True):
    _actor(session, actor_id)
    stmt = select(Correction)
    if not user_has_role(session, actor_id, 'admin'):
        stmt = stmt.where(Correction.author_id == actor_id)
    if only_open:
        stmt = stmt.where(Correction.state == 'open')
    return list(session.scalars(stmt.order_by(Correction.created_at.desc())).all())


def resolve_correction(session, *, actor_id, correction_id, state, resolution):
    _admin(session, actor_id)
    if state not in {'resolved', 'dismissed'} or not resolution.strip():
        raise ValueError('Debes explicar cómo se resolvió o descartó.')
    row = session.get(Correction, int(correction_id))
    if row is None or row.state != 'open':
        raise ValueError('Incidencia ya resuelta o inexistente.')
    row.state = state
    row.resolution = resolution.strip()[:3000]
    row.resolved_by = actor_id
    row.resolved_at = UTC_NOW()
    audit(session, actor_id, 'resolve_data_correction_47', 'data_correction_47', row.id)
    return row


def set_match_importance(session, *, actor_id, match_id, importance, reason=''):
    _director(session, actor_id)
    match = session.scalar(select(Match).where(Match.id == int(match_id), official_match_clause()))
    if not match:
        raise ValueError('Partido oficial inexistente.')
    if importance not in {'Normal', 'Muy importante'}:
        raise ValueError('Importancia desconocida.')
    row = session.scalar(select(Priority).where(Priority.match_id == match.id))
    if not row:
        row = Priority(match_id=match.id, marked_by=actor_id, importance=importance)
        session.add(row)
    before = row.importance
    row.importance = importance
    row.reason = (reason or '').strip()[:1000] or None
    row.marked_by = actor_id
    row.updated_at = UTC_NOW()
    session.flush()
    if before != importance:
        audit(session, actor_id, 'set_match_importance_47', 'match_priority_47', row.id,
              before={'importance':before}, after={'importance':importance})
    return row


def create_official_match(session, *, actor_id, season_id, competition_id,
                          home_team_id, away_team_id, match_date, round_name):
    """Delegated fixture correction: never fabricate a date or duplicate a fixture.

    A near-identical fixture can be a valid return leg; therefore check same
    teams and *date* strictly and require manual review of reverse fixtures.
    """
    _actor(session, actor_id)
    if not user_has_role(session, actor_id, 'director', 'admin'):
        actor = session.get(User, int(actor_id))
        if not (user_has_role(session, actor_id, 'reporter') and
                actor.participation_profile in {'full', 'free'}):
            raise PermissionError('Solo DD, analistas completos y Administración registran partidos oficiales.')
    if not isinstance(match_date, __import__('datetime').date):
        raise ValueError('Debes introducir una fecha comprobada. Nunca se inventa.')
    from models.entities import Team, Competition
    if session.get(Season, int(season_id)) is None or session.get(Competition, int(competition_id)) is None:
        raise ValueError('Temporada o competición inexistente.')
    home, away = session.get(Team,int(home_team_id)), session.get(Team,int(away_team_id))
    if not home or not away or home.id == away.id or any(t.is_test or t.archived_at for t in (home,away)):
        raise ValueError('Equipos no válidos para un partido oficial.')
    candidates=list(session.scalars(select(Match).where(Match.season_id==int(season_id),
        Match.competition_id==int(competition_id),Match.home_team_id==int(home_team_id),
        Match.away_team_id==int(away_team_id), official_match_clause())).all())
    if any(m.match_date==match_date for m in candidates):
        raise ValueError('Ya existe este partido oficial en la fecha seleccionada. Abre el existente.')
    if any(abs((m.match_date-match_date).days)<=7 for m in candidates):
        raise ValueError('Hay otro partido muy cercano con estos equipos. Comprueba antes si es aplazamiento o duplicado.')
    obj=Match(season_id=season_id,competition_id=competition_id,
        home_team_id=home_team_id,away_team_id=away_team_id,
        match_date=match_date,round_name=round_name.strip() or 'Jornada sin confirmar',
        status='draft',schedule_status='provisional',created_by=actor_id)
    session.add(obj)
    session.flush()
    audit(session,actor_id,'create_official_match_47','match',obj.id,
          detail='Sin hora ficticia; se conserva identidad de encuentro.')
    return obj


def resolve_observed_identity(session, *, actor_id, contribution_id, player_id):
    """Resolve a provisional single-player observation with full source retention."""
    _actor(session,actor_id)
    row=session.get(Contribution,int(contribution_id))
    if not row or row.kind!='individual':
        raise ValueError('No existe una observación individual provisional.')
    if not can_read_contribution(session, row, actor_id):
        raise PermissionError('La observación no se ha compartido contigo.')
    player=session.get(Player,int(player_id))
    if not player or not player.active or player.merged_into_id is not None:
        raise ValueError('Jugador de destino inexistente o fusionado.')
    if row.player_id and row.player_id!=player_id:
        raise ValueError('Identidad ya vinculada. Comunica una incidencia antes de cambiarla.')
    if row.player_id==player_id:
        return row
    data=json.loads(row.data_json or '{}')
    data['identificacion_resuelta']={'player_id':int(player_id),
        'autor_id':actor_id, 'fecha':UTC_NOW().isoformat(),
        'etiqueta_original':row.title,
        'dorsal_original':data.get('dorsal_observado'),
        'posicion_original':data.get('posicion_observada')}
    row.data_json=_json(data)
    row.player_id=int(player_id)
    row.updated_at=UTC_NOW()
    row.revision += 1
    session.flush()
    audit(session,actor_id,'resolve_observed_identity_47','sporting_contribution_47',row.id,
          detail=f'player={player_id}; origen preservado')
    return row


def possible_identity_links(session, *, actor_id, contribution_id):
    """Suggestions only, without implicit merge or visibility leakage."""
    source=get_contribution(session,contribution_id,actor_id)
    if source.kind!='individual' or not source.match_id or not source.team_id:
        return []
    data=json.loads(source.data_json or '{}')
    position=data.get('posicion_observada')
    number=data.get('dorsal_observado')
    if not (position or number):
        return []
    candidates=list(session.scalars(select(Contribution).where(
         Contribution.id!=source.id, Contribution.kind=='individual',
         Contribution.match_id==source.match_id,Contribution.team_id==source.team_id,
         or_(Contribution.author_id==actor_id,Contribution.status=='shared' if user_has_role(session,actor_id,'director','admin') else Contribution.author_id==actor_id))
         .limit(100)).all())
    result=[]
    for row in candidates:
        other=json.loads(row.data_json or '{}')
        if (position and other.get('posicion_observada')==position or
             number and other.get('dorsal_observado')==number):
            result.append(row)
    return result


def share_proposal(session, *, actor_id, proposal_id, recipient_ids):
    _director(session,actor_id)
    p=get_proposal(session,proposal_id,actor_id)
    ids=[]
    for recipient in list(dict.fromkeys(int(v) for v in recipient_ids)):
        _actor(session,recipient)
        ids.append(recipient)
    p.shared_with=json.dumps(ids)
    p.updated_at=UTC_NOW()
    audit(session,actor_id,'share_proposal_47','player_proposal_47',p.id,
          detail=f'permitted_staff_count={len(ids)}')
    return p
