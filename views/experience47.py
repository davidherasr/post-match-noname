"""4.7 role-specific consultation-first routes.

Every button is backed by an authorised repository operation. Do not import
legacy sport intelligence screens that predate the confidentiality decisions.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import joinedload

from core.database import session_scope
from core.permissions import can_admin, can_direct, can_report, working_profile
from core.navigation import request_navigation
from core.clock import local_today
from models.entities import (
    Match, Team, TeamRoster, Player, User, Report, PlayerEvaluation,
    MatchOpinion, MatchOpinionPlayer, Participation, PlayerSeasonDecision,
    SportingContribution47 as Contribution, MatchPriority47 as Priority,
)
from repositories import collaboration47 as domain
from repositories import players as players_repo
from repositories.data_governance import official_match_clause
from repositories.common import FINAL_REPORT_STATUSES
from ui.styles import page_header


def _go(dest, *, match=None, player=None, team=None, contribution=None):
    if match is not None:
        st.session_state['workspace_match_id'] = int(match)
    if player is not None:
        st.session_state['workspace_player_id'] = int(player)
    if team is not None:
        st.session_state['workspace_team_id'] = int(team)
    if contribution is not None:
        st.session_state['contribution_id_47'] = int(contribution)
    st.session_state['selection_epoch47'] = st.session_state.get('selection_epoch47', 0) + 1
    request_navigation(dest)
    st.rerun()


def _season():
    with session_scope() as db:
        active = players_repo.get_active_season(db)
        return active.id if active else None


def _own():
    with session_scope() as db:
        own = players_repo.get_own_team(db)
        return own.id if own else None


def _fixture_label(m):
    result = ('—' if m.home_score is None or m.away_score is None
              else f'{m.home_score}–{m.away_score}')
    return f'{m.home_team.name} – {m.away_team.name} · {result}'


def _date_label(m):
    return f'{m.match_date:%d/%m/%Y}' + (f' · {m.kickoff_at:%H:%M}' if m.kickoff_at else ' · Hora no confirmada')


def _fixtures(season_id, own_id=None, count=100):
    with session_scope() as db:
        stmt = select(Match).options(joinedload(Match.home_team), joinedload(Match.away_team)).where(
            Match.season_id == season_id, official_match_clause())
        if own_id is not None:
            stmt = stmt.where(or_(Match.home_team_id == own_id, Match.away_team_id == own_id))
        return list(db.scalars(stmt.order_by(Match.match_date.desc(), Match.id.desc()).limit(count)).unique().all())


def _direct_link_to_event(event):
    if event.target_type == 'contribution':
        return 'Mis aportaciones', {'contribution': event.target_id}
    if event.target_type == 'request':
        return 'Mis solicitudes', {}
    if event.target_type == 'proposal':
        return 'Dirección Deportiva', {}
    if event.target_type in {'legacy_report','legacy_opinion'}:
        return 'Partidos', {}
    return 'Inicio', {}


def _events(user, season_id, *, intro=False):
    if not season_id:
        return
    st.markdown('### Novedades' if intro else '### Bandeja de actividad')
    filter_value = st.radio('Mostrar', ['Nuevos','Todos','Guardados'], horizontal=True,
                            key='inbox_filter_47', label_visibility='collapsed')
    group='Todo'
    if can_direct(user):
        group=st.selectbox('Tipo de novedad',['Todo','Informes y observaciones','Propuestas de jugadores',
                     'Respuestas y solicitudes'],key='inbox_group47')
    with session_scope() as db:
        events = domain.visible_events(db, actor_id=user['id'], season_id=season_id,
                        filter_by={'Nuevos':'new','Todos':'all','Guardados':'saved'}[filter_value], limit=150)
    classes={'Informes y observaciones':{'contribution','contribution_update','legacy_report','legacy_opinion'},
        'Propuestas de jugadores':{'proposal','proposal_decision'},
        'Respuestas y solicitudes':{'request','response','request_response','request_closed'}}
    if group in classes:
        events=[(e,state) for e,state in events if e.kind in classes[group]]
    if not events:
        st.info('No hay novedades en esta vista. Las aportaciones guardadas y los partidos siguen disponibles.')
        return
    for event, state in events:
        with st.container(border=True):
            head, buttons = st.columns([5,3], vertical_alignment='center')
            with head:
                st.markdown(f'**{event.title}**')
                st.caption(f'{event.detail or ""} · {event.created_at:%d/%m/%Y %H:%M}')
            with buttons:
                c1,c2,c3 = st.columns(3)
                if c1.button('Abrir', key=f'ev_open47_{event.id}', use_container_width=True):
                    dest, kw = _direct_link_to_event(event)
                    if event.target_type=='request' and can_direct(user):
                        st.session_state['pending_dd_section47']='Solicitudes'
                        dest,kw='Dirección Deportiva',{}
                    if event.target_type in {'legacy_report','legacy_opinion'}:
                        with session_scope() as db:
                            source = db.get(Report if event.target_type=='legacy_report' else MatchOpinion, event.target_id)
                            if not source or not can_direct(user):
                                st.error('Fuente no disponible para tu perfil.')
                                return
                            kw={'match':source.match_id}
                    # A DD may also open a published contribution directly.
                    if event.target_type == 'contribution':
                        st.session_state['contribution_id_47'] = event.target_id
                        if can_direct(user): st.session_state['pending_dd_section47'] = 'Aportaciones compartidas'
                        dest = 'Dirección Deportiva' if can_direct(user) else 'Mis aportaciones'
                        kw = {}
                    _go(dest, **kw)
                if c2.button('☆' if not (state and state.saved_at) else '★',
                             key=f'ev_save47_{event.id}', help='Guardar para después', use_container_width=True):
                    with session_scope() as db:
                        domain.change_event_state(db, actor_id=user['id'], event_id=event.id,
                            action='unsave' if state and state.saved_at else 'save')
                    st.rerun()
                if c3.button('×' if not (state and state.seen_at) else '↶',
                             key=f'ev_seen47_{event.id}', help='Marcar visto / recuperar', use_container_width=True):
                    with session_scope() as db:
                        domain.change_event_state(db, actor_id=user['id'], event_id=event.id,
                            action='unsee' if state and state.seen_at else 'seen')
                    st.rerun()


def _fixture_shortcut(m, label):
    with st.container(border=True):
        c1,c2 = st.columns([5,1],vertical_alignment='center')
        c1.markdown(f'**{label} · {_fixture_label(m)}**')
        c1.caption(_date_label(m))
        if c2.button('Abrir', key=f'fixture_short47_{label}_{m.id}', use_container_width=True):
            _go('Partidos', match=m.id)


def home(user):
    if working_profile(user) == 'own':
        return own_matches(user)
    page_header('Inicio','Consulta primero. Aporta o decide cuando lo necesites.')
    season = _season()
    if not season:
        st.info('No hay temporada activa. Administración debe configurarla.'); return
    if can_direct(user):
        _events(user, season, intro=True)
        st.markdown('### Asuntos para Dirección Deportiva')
        with session_scope() as db:
            proposals = [p for p in domain.list_proposals(db,user['id'],season) if p.state == 'new']
            requests = [r for r in domain.list_requests(db,actor_id=user['id'],season_id=season)
                        if r.sender_id == user['id'] and r.state == 'pending']
        st.caption(f'{len(proposals)} propuestas sin revisar · {len(requests)} solicitudes pendientes de respuesta')
        if st.button('Abrir mesa DD',key='home_dd47'):
            _go('Dirección Deportiva')
    else:
        _events(user, season, intro=True)
        if can_report(user):
            with session_scope() as db:
                mine = [r for r in domain.list_requests(db,actor_id=user['id'],season_id=season,include_closed=False)
                        if r.recipient_id == user['id']]
            if mine:
                st.markdown(f'**Tienes {len(mine)} solicitud(es) de Aarón pendientes de respuesta.**')
                if st.button('Consultar mis solicitudes',key='home_my_requests47'):
                    _go('Mis solicitudes')
    if can_report(user) and not can_direct(user):
        with session_scope() as db:
            shared=[p for p in domain.list_proposals(db,user['id'],season)
                if p.author_id!=user['id']]
        if shared:
            with st.expander(f'Propuestas compartidas conmigo ({len(shared)})',expanded=False):
                for prop in shared[:20]:
                    st.markdown(f'**{prop.subject}** · {prop.state}')
                    st.caption(prop.reason)
    own_id = _own()
    fixtures = _fixtures(season, own_id=own_id, count=80) if own_id else []
    today=local_today()
    past = next((m for m in fixtures if m.match_date <= today), None)
    future = next((m for m in reversed(fixtures) if m.match_date >= today), None)
    st.markdown('### Partidos de referencia')
    if past: _fixture_shortcut(past,'Último partido')
    if future and (not past or future.id != past.id): _fixture_shortcut(future,'Próximo partido')
    if not past and not future: st.caption('No hay partidos del equipo propio registrados.')


def _table_select(df: pd.DataFrame, *, key: str):
    if df.empty:
        return None
    selection = st.dataframe(df, hide_index=True, use_container_width=True,
        on_select='rerun', selection_mode='single-row', key=key,
        height=min(560, 39*(len(df)+1)))
    rows = selection.selection.rows
    return int(rows[0]) if rows else None


def matches(user, own_only=False):
    team_selection = st.session_state.get('workspace_team_id')
    if team_selection and not own_only:
        return team_detail(user, int(team_selection))
    selected = st.session_state.get('workspace_match_id')
    if selected:
        return match_detail(user,int(selected),return_to='Mis partidos' if own_only else 'Partidos')
    page_header('Mis partidos' if own_only else 'Partidos',
                'Recientes, próximos y observados. No necesitas un horario confirmado para consultar o valorar.')
    season=_season()
    if not season:
        st.info('No hay temporada activa.'); return
    own_id=_own()
    if own_only and own_id:
        own_fixtures=_fixtures(season,own_id=own_id,count=80)
        last=next((m for m in own_fixtures if m.match_date<=local_today()),None)
        if last:
            st.markdown(f'**Último partido:** {_fixture_label(last)} · {last.match_date:%d/%m}')
            if st.button('Valorar último partido',type='primary',key='quick_last47'):
                st.session_state['contrib_mode47']='quick'
                _go('Mis partidos',match=last.id)
    scope = 'Noname' if own_only else st.radio('Ámbito',['Todos','Noname','Otros equipos'],horizontal=True,key='match_scope47')
    fixtures=_fixtures(season, own_id=own_id if scope=='Noname' else None, count=500)
    if scope=='Otros equipos' and own_id:
        fixtures=[m for m in fixtures if own_id not in (m.home_team_id,m.away_team_id)]
    mode=st.radio('Periodo',['Recientes','Próximos','Todos'],horizontal=True,key='match_period47')
    today=local_today()
    if mode=='Recientes': fixtures=[m for m in fixtures if m.match_date<=today]
    if mode=='Próximos': fixtures=[m for m in fixtures if m.match_date>=today]
    if mode=='Recientes': fixtures=fixtures[:40]
    if mode=='Próximos': fixtures=list(reversed(fixtures))[:40]
    if not fixtures:
        st.info('No hay partidos para este filtro. Prueba con «Todos».'); return
    rows=[{'Fecha':_date_label(m),'Encuentro':_fixture_label(m),'Jornada':m.round_name}
          for m in fixtures]
    idx=_table_select(pd.DataFrame(rows),key=f'match_list47_{st.session_state.get("selection_epoch47",0)}_{scope}_{mode}')
    if idx is not None:
        _go('Mis partidos' if own_only else 'Partidos',match=fixtures[idx].id)
    if can_direct(user) or (can_report(user) and working_profile(user) in {'analyst','director'}):
        with st.expander('Falta un partido oficial · Comunicar o registrar',expanded=False):
            _missing_match_form(user,season)


def _missing_match_form(user, season):
    # Registration requires identifiable teams, competition and calendar date;
    # never make up an absent date. A separate reported error handles uncertainty.
    with session_scope() as db:
        teams=list(db.scalars(select(Team).where(Team.active.is_(True),Team.is_test.is_(False)).order_by(Team.name)).all())
        from models.entities import Competition
        comps=list(db.scalars(select(Competition).where(Competition.active.is_(True)).order_by(Competition.name)).all())
    if not (teams and comps):
        st.caption('Necesitas al menos dos equipos y una competición cargados.'); return
    with st.form('missing_fixture47'):
        teamids={t.id:t.name for t in teams}
        home=st.selectbox('Local',list(teamids),format_func=teamids.get)
        away=st.selectbox('Visitante',list(teamids),format_func=teamids.get,index=min(1,len(teamids)-1))
        comp=st.selectbox('Competición',[c.id for c in comps],format_func=lambda cid:next(c.name for c in comps if c.id==cid))
        day=st.date_input('Fecha documentada',value=local_today())
        round_name=st.text_input('Jornada / referencia',value='Por determinar')
        confirmed=st.checkbox('He comprobado que el encuentro es oficial y la fecha es correcta')
        create=st.form_submit_button('Registrar encuentro oficial')
    if create:
        try:
            if not confirmed: raise ValueError('Confirma que el encuentro está comprobado.')
            with session_scope() as db:
                domain.create_official_match(db,actor_id=user['id'],season_id=season,
                    competition_id=comp,home_team_id=home,away_team_id=away,
                    match_date=day,round_name=round_name)
            st.success('Encuentro registrado sin hora artificial.');st.rerun()
        except Exception as exc: st.error(str(exc))


def own_matches(user):
    return matches(user, own_only=True)


def _contrib_status(row):
    return 'Borrador privado' if row.status == 'draft' else 'Compartida con DD'


def _contribution_summary(row):
    try:
        data=json.loads(row.data_json)
    except (TypeError,ValueError):
        data={}
    return data


def _show_contribution(row, actor_id):
    data=_contribution_summary(row)
    st.markdown(f'**{row.title}** · {_contrib_status(row)}')
    st.caption(f'{row.kind} · {row.updated_at:%d/%m/%Y %H:%M} · revisión {row.revision}')
    for key,value in data.items():
        if value in ('',None,[]): continue
        st.write(f'**{key.replace("_"," ").capitalize()}:** {value}')


def _open_work(user, match, mode):
    st.session_state['contrib_mode47']=mode
    st.session_state['workspace_match_id']=match.id
    st.rerun()


def _zone_buttons(mid):
    st.caption('Selecciona una zona, no un XI ni una formación. No se afirmará que jugó un futbolista concreto.')
    sections=[('Ataque',['EI','DC','ED']),('Mediocampo',['MI','MC','MCO','MD']),('Defensa',['LI','DCI','DCD','LD']),('Portería',['POR'])]
    selected=st.session_state.get(f'zone47_{mid}')
    for line, values in sections:
        cols=st.columns(len(values))
        for col,val in zip(cols,values):
            if col.button(val,key=f'zonepick47_{mid}_{val}',type='primary' if selected==val else 'secondary',use_container_width=True):
                st.session_state[f'zone47_{mid}']=val
                st.rerun()
    if selected: st.caption(f'Zona seleccionada: {selected}')
    return selected


def _quick(user, match, own_id):
    if not can_report(user): return
    with session_scope() as db:
        prior=db.scalar(select(Contribution).where(Contribution.author_id==user['id'],
             Contribution.match_id==match.id,Contribution.kind=='quick').order_by(Contribution.id.desc()).limit(1))
    defaults=_contribution_summary(prior) if prior else {}
    st.markdown('### Valoración rápida · Noname')
    st.caption('Solo nota + Guardar. Todo lo demás es opcional. Tu opinión es privada para ti y Dirección Deportiva.')
    with st.form(f'quickform47_{match.id}'):
        ratings=list(range(1,11))
        previous_note=defaults.get('nota_noname')
        rating=st.radio('¿Qué nota le das a Noname?',ratings,
             index=ratings.index(int(previous_note)) if previous_note in ratings else None,
             horizontal=True, key=f'quickrating47_{match.id}')
        comment=st.text_area('Comentario opcional',value=str(defaults.get('comentario') or ''),height=80)
        submitted=st.form_submit_button('Guardar valoración',type='primary',use_container_width=True)
    if submitted:
        try:
            if rating is None: raise ValueError('Elige primero una nota del 1 al 10.')
            with session_scope() as db:
                domain.save_contribution(db,actor_id=user['id'],season_id=match.season_id,
                    match_id=match.id,team_id=own_id,kind='quick',title=f'Valoración Noname · {match.round_name}',
                    data={'nota_noname':rating,'comentario':comment},
                    contribution_id=prior.id if prior else None,expected_revision=prior.revision if prior else None,publish=True)
            st.success('Valoración guardada. Puedes editarla desde este mismo partido.')
            st.rerun()
        except Exception as exc: st.error(str(exc))
    with st.expander('Señalar un jugador por su zona (opcional)',expanded=False):
        zone=_zone_buttons(match.id)
        with st.form(f'quickzone47_{match.id}'):
            dorsal=st.number_input('Dorsal si lo conoces (0 = desconocido)',min_value=0,max_value=99,value=0)
            score=st.selectbox('Nota individual opcional',['Sin nota']+list(range(1,11)))
            category=st.selectbox('Impresión (opcional)',['Sin categoría','Destacado','Menos destacado'])
            text=st.text_area('Qué observaste',placeholder='Puedes identificarlo solo por su posición.')
            keep=st.form_submit_button('Guardar observación del jugador',disabled=not bool(zone))
        if keep:
            with session_scope() as db:
                domain.save_contribution(db,actor_id=user['id'],season_id=match.season_id,
                   match_id=match.id,team_id=own_id,kind='individual',title=f'Observación {zone} · {match.round_name}',
                   data={'posicion_observada':zone,'dorsal_observado':dorsal or None,
                         'nota':None if score=='Sin nota' else score,'comentario':text,
                         'impresion':None if category=='Sin categoría' else category},publish=True)
            st.success('Observación guardada sin inventar el nombre ni el XI.');st.rerun()


def _complete(user, match):
    if not can_report(user): return
    sid=st.session_state.get('edit_contribution_47')
    prior=None
    if sid:
        with session_scope() as db:
            try: prior=domain.get_contribution(db,sid,user['id'])
            except PermissionError: pass
        if prior and (prior.kind!='complete' or prior.match_id!=match.id or prior.status!='draft'):
            prior=None
    old=_contribution_summary(prior) if prior else {}
    st.markdown('### Análisis completo')
    st.caption('Guarda avances sin publicarlos. Puedes registrar solo el equipo propio, el rival o ambos. Sin XI confirmado.')
    with st.form(f'complete47_{match.id}_{prior.id if prior else 0}'):
        scope=st.radio('Qué has observado',['Noname','Rival','Ambos'],horizontal=True,
              index=['Noname','Rival','Ambos'].index(('Noname' if old.get('ambito')=='No Name' else old.get('ambito','Ambos'))))
        own=st.text_area('Lectura de Noname (opcional)',value=old.get('equipo_propio',''),height=105)
        rival=st.text_area('Lectura del rival (opcional)',value=old.get('rival',''),height=105)
        strengths=st.text_area('Fortalezas observadas',value=old.get('fortalezas',''),height=85)
        weak=st.text_area('Debilidades observadas',value=old.get('debilidades',''),height=85)
        observation=st.text_area('Conclusión / contexto',value=old.get('conclusion',''),height=95)
        stats=st.text_area('Datos propios de rendimiento, pases u otras mediciones (opcional)',
              value=old.get('datos_individuales',''),height=85)
        video=st.text_input('Referencia a cortes o vídeo de apoyo (opcional)',
              value=old.get('cortes_video',''))
        save=st.form_submit_button('Guardar borrador privado',use_container_width=True)
    if save:
        try:
            data={'ambito':scope,'equipo_propio':own if scope in ('Noname','Ambos') else '',
                  'rival':rival if scope in ('Rival','Ambos') else '',
                  'fortalezas':strengths,'debilidades':weak,'conclusion':observation,
                  'datos_individuales':stats,'cortes_video':video}
            with session_scope() as db:
                row=domain.save_contribution(db,actor_id=user['id'],season_id=match.season_id,
                    match_id=match.id,kind='complete',title=f'Análisis · {_fixture_label(match)}',
                    data=data,contribution_id=prior.id if prior else None,
                    expected_revision=prior.revision if prior else None)
            st.session_state['edit_contribution_47']=row.id
            st.success('Borrador privado guardado. Puedes seguir otro día.');st.rerun()
        except Exception as exc: st.error(str(exc))
    if prior:
        st.info('Borrador recuperado. Dirección Deportiva no puede leerlo hasta que lo compartas.')
        if st.button('Compartir análisis con Dirección Deportiva',key=f'publish_complete47_{prior.id}',type='primary'):
            with session_scope() as db:
                domain.publish_draft(db,actor_id=user['id'],contribution_id=prior.id)
            st.session_state.pop('edit_contribution_47',None)
            st.success('Análisis compartido con Dirección Deportiva.');st.rerun()


def _individual(user, match):
    if not can_report(user): return
    st.markdown('### Añadir observación individual')
    with session_scope() as db:
        roster=list(db.scalars(select(TeamRoster).options(joinedload(TeamRoster.player)).where(
            TeamRoster.season_id==match.season_id,
            TeamRoster.team_id.in_([match.home_team_id,match.away_team_id]),TeamRoster.active.is_(True))).unique().all())
    names={r.player_id:f'{r.player.full_name} ({r.team_id})' for r in roster}
    with st.form(f'indiv47_{match.id}'):
        team=st.selectbox('Equipo',[match.home_team_id,match.away_team_id],
                  format_func=lambda tid:match.home_team.name if tid==match.home_team_id else match.away_team.name)
        player_id=st.selectbox('Jugador (opcional)',[None]+list(names),format_func=lambda pid:names.get(pid,'No identificado'))
        zone=st.selectbox('Posición observada (opcional)',['Sin determinar','POR','LD','DCD','DCI','LI','MC','MCO','ED','EI','DC'])
        shirt=st.number_input('Dorsal, si lo conoces',min_value=0,max_value=99,value=0)
        rate=st.selectbox('Nota',['Sin nota']+list(range(1,11)))
        note=st.text_area('Descripción de lo observado',height=110)
        publish=st.checkbox('Compartir con DD al guardar',value=False)
        save=st.form_submit_button('Guardar observación')
    if save:
        try:
            if player_id and not any(r.player_id==player_id and r.team_id==team for r in roster):
                raise ValueError('El jugador seleccionado no figura en la plantilla de ese equipo.')
            with session_scope() as db:
                domain.save_contribution(db,actor_id=user['id'],season_id=match.season_id,
                   match_id=match.id,team_id=team,player_id=player_id,
                   kind='individual',title=f'Jugador {names.get(player_id) if player_id else (zone if zone!="Sin determinar" else "por identificar")}',
                   data={'posicion_observada':None if zone=='Sin determinar' else zone,
                         'dorsal_observado':shirt or None,'nota':None if rate=='Sin nota' else rate,
                         'comentario':note,'identidad_confirmada':bool(player_id)},publish=publish)
            st.success('Observación individual guardada.');st.rerun()
        except Exception as exc: st.error(str(exc))


def _match_sources(user, match):
    with session_scope() as db:
        contribs=domain.list_contributions(db,actor_id=user['id'],season_id=match.season_id,match_id=match.id)
        old_reports=list(db.scalars(select(Report).options(joinedload(Report.reporter)).where(
            Report.match_id==match.id,
            or_(Report.reporter_id==user['id'],
                Report.status.in_(FINAL_REPORT_STATUSES) if can_direct(user) or can_admin(user) else Report.reporter_id==user['id']))).unique().all())
        opinion_stmt=select(MatchOpinion).options(joinedload(MatchOpinion.user)).where(MatchOpinion.match_id==match.id)
        if not (can_direct(user) or can_admin(user)):
            opinion_stmt=opinion_stmt.where(MatchOpinion.user_id==user['id'])
        old_opinions=list(db.scalars(opinion_stmt).unique().all())
    if not contribs and not old_reports and not old_opinions:
        st.caption('Todavía no hay aportaciones disponibles para tu perfil.')
    for row in contribs[:30]:
        with st.expander(f'{row.title} · {_contrib_status(row)}'):
            _show_contribution(row,user['id'])
    for op in old_opinions[:30]:
        with st.expander(f'Valoración histórica · {op.user.full_name} · {op.updated_at:%d/%m}'):
            if op.home_team_rating: st.write(f'{match.home_team.name}: {op.home_team_rating}/10')
            if op.away_team_rating: st.write(f'{match.away_team.name}: {op.away_team_rating}/10')
            if op.summary: st.write(op.summary)
    for row in old_reports[:30]:
        if row.status not in FINAL_REPORT_STATUSES and row.reporter_id!=user['id']:
            continue
        with st.expander(f'Informe histórico · {row.reporter.full_name} · {row.status}'):
            if row.own_team_rating: st.write('Noname:',row.own_team_rating)
            if row.rival_team_rating: st.write('Rival:',row.rival_team_rating)
            if row.own_team_note: st.write(row.own_team_note)
            if row.opponent_overview: st.write(row.opponent_overview)
            if row.key_takeaways: st.write(row.key_takeaways)


def _correction_form(user, entity_type, entity_id, season_id):
    with st.expander('Comunicar un error de datos',expanded=False):
        with st.form(f'correction47_{entity_type}_{entity_id}'):
            desc=st.text_area('Qué dato no es correcto y qué propones')
            send=st.form_submit_button('Enviar incidencia')
        if send:
            try:
                with session_scope() as db:
                    domain.create_correction(db,actor_id=user['id'],entity_type=entity_type,
                         entity_id=entity_id,season_id=season_id,description=desc)
                st.success('Incidencia enviada a Administración. Puedes seguir trabajando.')
            except Exception as exc: st.error(str(exc))


def match_detail(user, match_id, return_to='Partidos'):
    with session_scope() as db:
        match=db.scalar(select(Match).options(joinedload(Match.home_team),joinedload(Match.away_team)).where(
            Match.id==match_id,official_match_clause()))
        importance=db.scalar(select(Priority).where(Priority.match_id==match_id)) if match else None
    if not match:
        st.error('No se encuentra este partido oficial.');st.session_state.pop('workspace_match_id',None);return
    if st.button('← Volver a partidos',key=f'back47_{match_id}'):
        st.session_state.pop('workspace_match_id',None)
        st.session_state.pop('contrib_mode47',None)
        st.session_state.pop('edit_contribution_47',None)
        st.rerun()
    page_header(_fixture_label(match),f'{match.round_name} · {_date_label(match)}')
    if importance and importance.importance=='Muy importante':
        st.caption('★ Partido de especial interés para Dirección Deportiva')
    st.caption('Las plantillas de temporada no equivalen a una alineación confirmada.')
    if working_profile(user)!='own':
        cs=st.columns(2)
        if cs[0].button(f'Equipo · {match.home_team.name}',key=f'home_team47_{match.id}'):
            st.session_state.pop('workspace_match_id',None);_go('Partidos',team=match.home_team_id)
        if cs[1].button(f'Equipo · {match.away_team.name}',key=f'away_team47_{match.id}'):
            st.session_state.pop('workspace_match_id',None);_go('Partidos',team=match.away_team_id)
    own_id=_own()
    own_match=own_id in (match.home_team_id,match.away_team_id)
    if can_direct(user):
        with st.expander('Marcar interés y solicitar observación',expanded=False):
            with st.form(f'priority47_{match.id}'):
                level=st.selectbox('Prioridad',['Normal','Muy importante'],
                     index=1 if importance and importance.importance=='Muy importante' else 0)
                reason=st.text_input('Motivo (opcional)',value=importance.reason if importance else '')
                mark=st.form_submit_button('Guardar importancia')
            if mark:
                with session_scope() as db:
                    domain.set_match_importance(db,actor_id=user['id'],match_id=match.id,importance=level,reason=reason)
                st.success('Importancia guardada. Puedes solicitar la observación a personas concretas.');st.rerun()
            _request_form(user,match.season_id,default_match=match.id)
    mode=st.session_state.get('contrib_mode47')
    if not mode:
        if can_report(user):
            simple=working_profile(user)=='own'
            if simple:
                if own_match and st.button('Valorar a Noname',key=f'mvquick47_{match.id}',type='primary',use_container_width=True):
                    _open_work(user,match,'quick')
                with st.expander('También quiero comentar algo del rival (opcional)',expanded=False):
                    if st.button('Señalar un jugador del rival',key=f'own_rival47_{match.id}'):
                        _open_work(user,match,'individual')
            else:
                a,b,c=st.columns(3)
                if own_match and a.button('Valorar a Noname',key=f'mvquick47_{match.id}',type='primary',use_container_width=True):
                    _open_work(user,match,'quick')
                if b.button('Análisis completo',key=f'mvcomplete47_{match.id}',use_container_width=True):
                    _open_work(user,match,'complete')
                if c.button('Jugador observado',key=f'mvindiv47_{match.id}',use_container_width=True):
                    _open_work(user,match,'individual')
        st.markdown('### Información del encuentro')
        a,b=st.columns(2)
        with a:
            st.markdown(f'**{match.home_team.name}**')
            st.caption(f'Estructura de referencia: {match.home_formation if match.home_formation_known and match.home_formation else "Sin confirmar"}')
        with b:
            st.markdown(f'**{match.away_team.name}**')
            st.caption(f'Estructura de referencia: {match.away_formation if match.away_formation_known and match.away_formation else "Sin confirmar"}')
        if can_report(user) and working_profile(user) in {'analyst','director'}:
            with st.expander('Registrar una estructura observada (sin sobrescribir la oficial)',expanded=False):
                with st.form(f'formation47_{match.id}'):
                    side=st.selectbox('Equipo observado',[match.home_team_id,match.away_team_id],
                        format_func=lambda tid:match.home_team.name if tid==match.home_team_id else match.away_team.name)
                    shape=st.text_input('Estructura vista (ej. 4-4-2)')
                    comment=st.text_area('Contexto: fase con balón, sin balón o modificaciones')
                    publish=st.checkbox('Compartir mi observación con DD',value=False)
                    send=st.form_submit_button('Guardar estructura')
                if send:
                    if not shape.strip(): st.error('Describe la estructura observada.')
                    else:
                        try:
                            with session_scope() as db:
                                domain.save_contribution(db,actor_id=user['id'],season_id=match.season_id,
                                  match_id=match.id,team_id=side,kind='formation',
                                  title=f'Estructura observada · {match.home_team.name if side==match.home_team_id else match.away_team.name}',
                                  data={'formacion':shape.strip(),'contexto':comment},publish=publish)
                            st.success('Estructura registrada como observación independiente.');st.rerun()
                        except Exception as exc: st.error(str(exc))
        can_edit_data=can_direct(user) or can_admin(user) or (can_report(user) and
                       (user.get('participation_profile') or 'full') in {'full','free'})
        if can_edit_data:
            with st.expander('Gestionar plantillas y alineaciones comprobadas',expanded=False):
                st.caption('Pega datos de Federación. Sin TITULARES/SUPLENTES solo actualiza la plantilla, '
                           'no inventa participantes ni XI. Las alineaciones confirmadas quedan auditadas.')
                from repositories import matches as matches_repo
                with st.form(f'fed47_{match.id}'):
                    tid=st.selectbox('Equipo',[match.home_team_id,match.away_team_id],
                        format_func=lambda tid:match.home_team.name if tid==match.home_team_id else match.away_team.name)
                    pasted=st.text_area('Texto Federación',height=170,
                        placeholder='TITULARES\n1;Portero;POR\n...\nSUPLENTES\n12;Jugador;DC\n\nO bien solo: 7;Jugador;EI')
                    save_roster=st.form_submit_button('Verificar y guardar datos')
                if save_roster:
                    try:
                        with session_scope() as db:
                            result=matches_repo.import_federation_roster_text(db,
                                team_id=tid,season_id=match.season_id,actor_id=user['id'],
                                text=pasted,match_id=match.id)
                        st.success(f"Plantilla actualizada: {result['rows']} registros; "
                                   f"{result['starters']} titulares; {result['substitutes']} suplentes.")
                        st.rerun()
                    except Exception as exc: st.error(str(exc))
        st.markdown('### Aportaciones disponibles')
        _match_sources(user,match)
        if can_report(user) and working_profile(user) in {'analyst','director'} and own_match:
            with st.expander('Preparar al próximo rival (desde este partido)',expanded=False):
                rival=match.away_team if match.home_team_id==own_id else match.home_team
                st.caption(f'Partidos recientes del {rival.name}. No se crea una ficha táctica obligatoria.')
                season_matches=[m for m in _fixtures(match.season_id,count=200) if rival.id in (m.home_team_id,m.away_team_id) and m.id!=match.id]
                for other in season_matches[:8]:
                    if st.button(f'{other.match_date:%d/%m} · {_fixture_label(other)}',key=f'rival_source47_{other.id}'):
                        _go('Partidos',match=other.id)
                if st.button('Crear síntesis de varios partidos',key=f'synth47_{match.id}'):
                    st.session_state['contrib_mode47']='synthesis';st.rerun()
        _correction_form(user,'match',match.id,match.season_id)
    else:
        if st.button('← Volver al resumen del partido',key=f'mvback47_{match.id}'):
            st.session_state.pop('contrib_mode47',None)
            st.session_state.pop('edit_contribution_47',None)
            st.rerun()
        if mode=='quick':
            if not own_match: st.warning('La nota rápida de Noname corresponde a partidos del equipo propio.')
            else: _quick(user,match,own_id)
        elif mode=='complete': _complete(user,match)
        elif mode=='individual': _individual(user,match)
        elif mode=='synthesis': _synthesis(user,match)



def team_detail(user, team_id):
    # Historical club knowledge, never a mandatory opposition-preparation workflow.
    if st.button('← Volver a partidos',key=f'team_back47_{team_id}'):
        st.session_state.pop('workspace_team_id',None);st.rerun()
    sid=_season()
    with session_scope() as db:
        team=db.get(Team,team_id)
        if not team or not team.active:
            st.error('Equipo no disponible.');return
        roster=list(db.scalars(select(TeamRoster).options(joinedload(TeamRoster.player)).where(
            TeamRoster.team_id==team_id, TeamRoster.season_id==sid, TeamRoster.active.is_(True))
            .order_by(TeamRoster.shirt_number,TeamRoster.id)).unique().all()) if sid else []
        contributions=domain.list_contributions(db,actor_id=user['id'],season_id=sid,limit=200) if sid else []
    page_header(team.name,'Expediente histórico de club. Separado de la preparación del próximo rival.')
    st.caption('La plantilla es de temporada: no confirma presencia en ninguno de los encuentros.')
    st.markdown('### Jugadores registrados')
    if roster:
        roster_df=pd.DataFrame([{'Dorsal':r.shirt_number if r.shirt_number is not None else '—',
            'Jugador':r.player.display_name or r.player.full_name,
            'Posición':r.usual_position or r.player.primary_position or '—'} for r in roster])
        idx=_table_select(roster_df,key=f'team_roster47_{team_id}_{st.session_state.get("selection_epoch47",0)}')
        if idx is not None: _go('Jugadores',player=roster[idx].player_id)
    else: st.caption('No hay plantilla registrada en esta temporada.')
    st.markdown('### Partidos de los que hay constancia')
    fixtures=[m for m in _fixtures(sid,count=500) if team_id in (m.home_team_id,m.away_team_id)] if sid else []
    for m in fixtures[:20]:
        if st.button(f'{m.match_date:%d/%m} · {_fixture_label(m)}',key=f'team_fixture47_{team_id}_{m.id}'):
            st.session_state.pop('workspace_team_id',None);_go('Partidos',match=m.id)
    if not fixtures: st.caption('No hay partidos oficiales registrados para este equipo.')
    st.markdown('### Observaciones disponibles para tu perfil')
    usable=[c for c in contributions if c.team_id==team_id and c.status=='shared' or
            c.team_id==team_id and c.author_id==user['id']]
    if not usable: st.caption('Sin observaciones individuales de este club accesibles para ti.')
    for row in usable[:30]:
        with st.expander(f'{row.updated_at:%d/%m} · {row.title}'):
            _show_contribution(row,user['id'])
    if sid: _correction_form(user,'team',team_id,sid)


def _synthesis(user,match):
    st.markdown('### Síntesis de varios partidos')
    all_matches=_fixtures(match.season_id,count=300)
    choose=[m for m in all_matches if match.home_team_id in (m.home_team_id,m.away_team_id) or match.away_team_id in (m.home_team_id,m.away_team_id)]
    lookup={m.id:f'{m.match_date:%d/%m} · {_fixture_label(m)}' for m in choose}
    with st.form(f'synthform47_{match.id}'):
        chosen=st.multiselect('Partidos que has observado',list(lookup),format_func=lookup.get,
                              default=[match.id] if match.id in lookup else [])
        text=st.text_area('Qué conclusiones extraes de estos encuentros')
        shared=st.checkbox('Compartir con Dirección Deportiva',value=False)
        save=st.form_submit_button('Guardar síntesis')
    if save:
        try:
            if not chosen: raise ValueError('Selecciona al menos un partido documentado.')
            with session_scope() as db:
                domain.save_contribution(db,actor_id=user['id'],season_id=match.season_id,
                   match_id=match.id,kind='synthesis',title=f'Síntesis deportiva · {_fixture_label(match)}',
                   data={'partidos_revisados':chosen,'conclusion':text},publish=shared)
            st.success('Síntesis guardada sin duplicar observaciones individuales.');st.rerun()
        except Exception as exc: st.error(str(exc))


def my_contributions(user, ratings_only=False):
    if not can_report(user):
        st.error('Solo los Informadores tienen aportaciones propias.');return
    selected=st.session_state.get('contribution_id_47')
    if selected:
        return contribution_detail(user,selected)
    page_header('Mis valoraciones' if ratings_only else 'Mis aportaciones',
                'Borradores privados, lecturas compartidas y trabajos anteriores. Sin entregas obligatorias.')
    sid=_season()
    if not sid:
        st.info('No hay temporada activa.');return
    with session_scope() as db:
        rows=domain.list_contributions(db,actor_id=user['id'],season_id=sid,own_only=True,limit=250)
        old=list(db.scalars(select(Report).options(joinedload(Report.match).joinedload(Match.home_team),
            joinedload(Report.match).joinedload(Match.away_team)).where(
            Report.reporter_id==user['id'],Report.match.has(Match.season_id==sid))
            .order_by(Report.updated_at.desc()).limit(80)).unique().all())
    if ratings_only:
        rows=[r for r in rows if r.kind in {'quick','individual'}]
    view=st.radio('Estado',['Todos','Borradores','Compartidos'],horizontal=True,key='my_filter47')
    if view=='Borradores': rows=[r for r in rows if r.status=='draft']
    if view=='Compartidos': rows=[r for r in rows if r.status=='shared']
    if not rows and not old:
        st.info('Aún no has guardado aportaciones. Puedes comenzar voluntariamente desde un partido.')
    drafts=[r for r in rows if r.status=='draft']
    if drafts:
        with st.expander('Entregar varias aportaciones cuando hayas terminado',expanded=False):
            draft_titles={r.id:r.title for r in drafts}
            chosen=st.multiselect('Mis borradores',list(draft_titles),format_func=draft_titles.get)
            if st.button('Compartir seleccionadas con DD',disabled=not bool(chosen),key='share_many47'):
                try:
                    with session_scope() as db:
                        for cid in chosen: domain.publish_draft(db,actor_id=user['id'],contribution_id=cid)
                    st.success(f'{len(chosen)} aportación(es) compartidas con Dirección Deportiva.');st.rerun()
                except Exception as exc: st.error(str(exc))
    if rows:
        df=pd.DataFrame([{'Fecha':f'{r.updated_at:%d/%m/%Y}','Tipo':r.kind,
                          'Aportación':r.title,'Estado':_contrib_status(r)} for r in rows])
        idx=_table_select(df,key=f'own_rows47_{st.session_state.get("selection_epoch47",0)}_{view}')
        if idx is not None: _go('Mis valoraciones' if ratings_only else 'Mis aportaciones',contribution=rows[idx].id)
    if not ratings_only and old:
        with st.expander(f'Informes históricos de la 4.6 y anteriores ({len(old)})',expanded=False):
            for r in old[:50]:
                st.markdown(f'**{_fixture_label(r.match)}** · {r.status}')
                st.caption(f'{r.updated_at:%d/%m/%Y} · conserva el informe original')
    if not ratings_only:
        st.markdown('### Nueva observación general')
        with st.expander('Anotar algo fuera de un partido',expanded=False):
            with st.form('general47'):
                title=st.text_input('Asunto o jugador')
                text=st.text_area('Observación y contexto')
                link=st.text_input('Buscar jugador existente (opcional)')
                share=st.checkbox('Compartir directamente con DD',value=False)
                save=st.form_submit_button('Guardar observación')
            if save:
                try:
                    with session_scope() as db:
                        matched=list(db.scalars(select(Player).where(Player.active.is_(True),
                            Player.merged_into_id.is_(None),Player.full_name.ilike(link.strip()))).all()) if link.strip() else []
                        if link.strip() and len(matched)!=1:
                            raise ValueError('La identidad no es unívoca. Utiliza el nombre completo exacto o deja el enlace sin completar.')
                        domain.save_contribution(db,actor_id=user['id'],season_id=sid,
                            kind='general',title=title,player_id=matched[0].id if matched else None,
                            data={'observacion':text},publish=share)
                    st.success('Observación guardada.');st.rerun()
                except Exception as exc: st.error(str(exc))


def contribution_detail(user,contribution_id):
    if st.button('← Volver a mis aportaciones',key=f'back_my47_{contribution_id}'):
        st.session_state.pop('contribution_id_47',None);st.rerun()
    with session_scope() as db:
        row=domain.get_contribution(db,contribution_id,user['id'])
        source=db.get(Match,row.match_id) if row.match_id else None
    page_header(row.title,_contrib_status(row))
    _show_contribution(row,user['id'])
    if row.kind=='individual' and not row.player_id and (row.author_id==user['id'] or can_direct(user) or can_admin(user)):
        with st.expander('Identificar futbolista observado (opcional)',expanded=False):
            st.caption('Confirmar una identidad nunca inventa una participación ni cambia la nota original.')
            with session_scope() as db:
                candidates=domain.possible_identity_links(db,actor_id=user['id'],contribution_id=row.id)
            if candidates:
                st.info(f'{len(candidates)} observación(es) potencialmente relacionadas. No se fusionan automáticamente.')
            typed=st.text_input('Buscar nombre',key=f'identity_query47_{row.id}')
            if len(typed.strip())>=2:
                with session_scope() as db:
                    poss=list(db.scalars(select(Player).where(Player.active.is_(True),
                        Player.merged_into_id.is_(None),Player.full_name.ilike(f'%{typed.strip()}%'))
                        .order_by(Player.full_name).limit(25)).all())
                candidates_names={p.id:p.full_name for p in poss}
                if poss:
                    chosen=st.selectbox('Confirmar identidad',[None]+list(candidates_names),
                        format_func=lambda pid:candidates_names.get(pid,'Selecciona el jugador'),key=f'identity_select47_{row.id}')
                    if st.button('Vincular identidad confirmada',disabled=chosen is None,key=f'identity_confirm47_{row.id}'):
                        try:
                            with session_scope() as db:
                                domain.resolve_observed_identity(db,actor_id=user['id'],
                                    contribution_id=row.id,player_id=chosen)
                            st.success('Identidad vinculada conservando el origen.');st.rerun()
                        except Exception as exc: st.error(str(exc))
                else: st.caption('No existen jugadores que coincidan. Puedes comunicar un error de datos.')
    if row.author_id==user['id'] and row.status=='draft':
        if row.kind in {'individual','general','formation','synthesis'}:
            with st.expander('Continuar y corregir este borrador',expanded=False):
                raw=_contribution_summary(row)
                field={'individual':'comentario','general':'observacion',
                       'formation':'contexto','synthesis':'conclusion'}[row.kind]
                with st.form(f'edit_simple47_{row.id}'):
                    text=st.text_area('Observación',value=str(raw.get(field) or ''),height=135)
                    save_edit=st.form_submit_button('Guardar cambios privados')
                if save_edit:
                    try:
                        raw[field]=text
                        with session_scope() as db:
                            domain.save_contribution(db,actor_id=user['id'],season_id=row.season_id,
                                kind=row.kind,title=row.title,data=raw,
                                match_id=row.match_id,player_id=row.player_id,team_id=row.team_id,
                                contribution_id=row.id,expected_revision=row.revision,publish=False)
                        st.success('Borrador actualizado en el mismo registro.');st.rerun()
                    except Exception as exc: st.error(str(exc))
        if row.kind=='complete' and row.match_id:
            if st.button('Continuar análisis completo',key=f'continue47_{row.id}',type='primary'):
                st.session_state['edit_contribution_47']=row.id
                st.session_state['contrib_mode47']='complete'
                _go('Partidos',match=row.match_id)
        if st.button('Compartir con Dirección Deportiva',key=f'share47_{row.id}',type='primary'):
            try:
                with session_scope() as db:
                    domain.publish_draft(db,actor_id=user['id'],contribution_id=row.id)
                st.success('Compartida con DD.');st.rerun()
            except Exception as exc: st.error(str(exc))
    if row.kind=='quick' and row.match_id and row.author_id==user['id']:
        if st.button('Modificar nota de este partido',key=f'quick_editlink47_{row.id}'):
            st.session_state['contrib_mode47']='quick'
            st.session_state.pop('contribution_id_47',None)
            _go('Mis partidos' if working_profile(user)=='own' else 'Partidos',match=row.match_id)
    if row.status=='shared' and row.author_id==user['id']:
        st.markdown('### Proponer un jugador a Dirección Deportiva')
        st.caption('Un informe compartido no genera automáticamente interés DD. Solo si propones expresamente a alguien.')
        with st.form(f'propose47_{row.id}'):
            subject=st.text_input('Nombre o identificación provisional (equipo, dorsal, zona)')
            why=st.text_area('Por qué merece una revisión')
            send=st.form_submit_button('Proponer a DD')
        if send:
            try:
                with session_scope() as db:
                    domain.propose_player(db,actor_id=user['id'],season_id=row.season_id,
                        subject=subject,reason=why,contribution_id=row.id,
                        player_id=row.player_id,match_id=row.match_id)
                st.success('Propuesta remitida a DD, sin crear un seguimiento automáticamente.')
            except Exception as exc: st.error(str(exc))


def _request_form(user,season_id,default_match=None,default_player=None,default_proposal=None):
    if not can_direct(user):return
    with session_scope() as db:
        from repositories.users import get_user_roles
        people=list(db.scalars(select(User).where(User.active.is_(True),User.deleted_at.is_(None))
                    .order_by(User.full_name)).all())
        people=[u for u in people if 'reporter' in get_user_roles(db,u.id)]
    if not people:
        st.caption('No hay Informadores activos destinatarios.');return
    targets={u.id:u.full_name for u in people}
    with st.form(f'new_req47_{default_match}_{default_player}_{default_proposal}'):
        who=st.selectbox('A quién solicitar información',list(targets),format_func=targets.get)
        subject=st.text_input('Asunto',value='Observación de un partido' if default_match else '')
        question=st.text_area('Qué quieres que observe o responda')
        priority=st.selectbox('Prioridad',['Normal','Alta','Muy importante'])
        create=st.form_submit_button('Enviar solicitud')
    if create:
        try:
            with session_scope() as db:
                domain.create_request(db,actor_id=user['id'],recipient_id=who,season_id=season_id,
                    subject=subject,question=question,match_id=default_match,
                    player_id=default_player,proposal_id=default_proposal,priority=priority)
            st.success('Solicitud enviada. Aparecerá en la bandeja y Mis solicitudes del destinatario.')
        except Exception as exc: st.error(str(exc))


def my_requests(user):
    page_header('Mis solicitudes','Una solicitud permanece pendiente aunque su novedad se marque como vista.')
    sid=_season()
    if not sid:
        st.info('Sin temporada activa.');return
    with session_scope() as db:
        rows=domain.list_requests(db,actor_id=user['id'],season_id=sid)
    if not rows:
        st.info('No hay solicitudes registradas para tu cuenta.');return
    for row in rows[:100]:
        with st.expander(f'{row.state.upper()} · {row.subject} · {row.priority}',expanded=row.state=='pending'):
            st.write(row.question)
            st.caption(f'{row.created_at:%d/%m/%Y} · Solicitud #{row.id}' +
                 (f' · Vinculada a propuesta #{row.proposal_id}' if row.proposal_id else ''))
            if row.answer:
                st.markdown('**Respuesta**');st.write(row.answer)
            if row.response_contribution_id:
                if st.button('Abrir informe que responde a esta solicitud',key=f'answer_src47_{row.id}'):
                    with session_scope() as db:
                        source=domain.get_contribution(db,row.response_contribution_id,user['id'])
                    if can_direct(user):
                        st.session_state['contribution_id_47']=source.id
                        st.session_state['pending_dd_section47']='Aportaciones compartidas'
                        _go('Dirección Deportiva')
                    else: _go('Mis aportaciones',contribution=source.id)
            if row.recipient_id==user['id'] and row.state=='pending' and can_report(user):
                with session_scope() as db:
                    own_sources=[c for c in domain.list_contributions(db,actor_id=user['id'],
                        season_id=sid,own_only=True,limit=250) if c.status=='shared' and
                        (row.match_id is None or c.match_id==row.match_id) and
                        (row.player_id is None or c.player_id==row.player_id)]
                sources={c.id:c.title for c in own_sources}
                with st.form(f'reply47_{row.id}'):
                    reply=st.text_area('Respuesta (puedes indicar que no tienes información)',key=f'replytxt47_{row.id}')
                    chosen=st.selectbox('Adjuntar informe propio ya compartido (opcional)',[None]+list(sources),
                        format_func=lambda cid:sources.get(cid,'Sin informe asociado'))
                    send=st.form_submit_button('Responder a Dirección Deportiva')
                if send:
                    try:
                        with session_scope() as db:
                            domain.respond_request(db,actor_id=user['id'],request_id=row.id,answer=reply,contribution_id=chosen)
                        st.success('Respuesta enviada.');st.rerun()
                    except Exception as exc: st.error(str(exc))
            if row.sender_id==user['id'] and can_direct(user) and row.state!='closed':
                if st.button('Cerrar solicitud',key=f'req_close47_{row.id}'):
                    with session_scope() as db:
                        domain.close_request(db,actor_id=user['id'],request_id=row.id)
                    st.rerun()


def director(user):
    if not can_direct(user):
        st.error('Solo Dirección Deportiva puede consultar esta mesa.');return
    page_header('Dirección Deportiva','Propuestas explícitas, evidencias y solicitudes. Las notas no crean candidatos automáticamente.')
    sid=_season()
    if not sid:
        st.info('Sin temporada activa.');return
    pending=st.session_state.pop('pending_dd_section47',None)
    if pending: st.session_state['dd_section47']=pending
    section=st.radio('Mesa',['Propuestas','Aportaciones compartidas','Solicitudes','Modelo y necesidades','Actividad'],horizontal=True,key='dd_section47')
    if section=='Actividad':
        _events(user,sid);return
    if section=='Solicitudes':
        with st.expander('Nueva solicitud de observación',expanded=False):
            _request_form(user,sid)
        return my_requests(user)
    if section=='Modelo y necesidades':
        from repositories import planning as planning_repo
        from core.presentation import NEED_STATES
        with session_scope() as db:
            roles=planning_repo.list_model_roles(db)
            needs=planning_repo.list_squad_needs(db,sid)
        by_role={n.model_role_id:n for n in needs}
        st.markdown('### Necesidades de plantilla')
        st.caption('Son decisiones manuales de DD. No se crean por medias o tendencias de las valoraciones.')
        if roles:
            table=pd.DataFrame([{'Rol / perfil':r.name,'Posición':r.position,
                'Necesidad':by_role[r.id].need_level if r.id in by_role else 'Sin definir'} for r in roles])
            st.dataframe(table,hide_index=True,use_container_width=True,height=min(400,39*(len(table)+1)))
            with st.expander('Actualizar una necesidad',expanded=False):
                role_names={r.id:f'{r.position} · {r.name}' for r in roles}
                with st.form('need47'):
                    rid=st.selectbox('Perfil de juego',list(role_names),format_func=role_names.get)
                    previous=by_role.get(rid)
                    level=st.selectbox('Nivel de necesidad',NEED_STATES,
                        index=NEED_STATES.index(previous.need_level) if previous and previous.need_level in NEED_STATES else 1)
                    note=st.text_area('Motivo (opcional)',value=previous.note if previous else '')
                    commit=st.form_submit_button('Guardar decisión DD')
                if commit:
                    try:
                        with session_scope() as db:
                            planning_repo.upsert_squad_need(db,user['id'],season_id=sid,
                               model_role_id=rid,need_level=level,note=note)
                        st.success('Necesidad registrada sin asignar tareas a los Informadores.');st.rerun()
                    except Exception as exc: st.error(str(exc))
        else:
            st.info('No hay perfiles del Modelo Noname. Puedes seguir trabajando sin configurarlos.')
        with st.expander('Definir un perfil del modelo (opcional)',expanded=False):
            with st.form('model_role47'):
                name=st.text_input('Nombre del perfil')
                pos=st.selectbox('Posición',['POR','LD','LI','DFC','MC','MCO','ED','EI','DC'])
                info=st.text_area('Descripción breve')
                create=st.form_submit_button('Crear perfil')
            if create:
                try:
                    if not name.strip(): raise ValueError('Escribe el nombre del perfil.')
                    with session_scope() as db:
                        planning_repo.create_model_role(db,user['id'],name=name,
                            position=pos,description=info)
                    st.success('Perfil añadido.');st.rerun()
                except Exception as exc: st.error(str(exc))
        return

    if section=='Propuestas':
        with session_scope() as db:
            proposals=domain.list_proposals(db,user['id'],sid)
        selected=st.radio('Estado de propuesta',['Pendientes','Guardadas','Seguimiento','Descartadas','Todas'],
                          horizontal=True,key='proposal_filter47')
        statuses={'Pendientes':['new'],'Guardadas':['saved'],'Seguimiento':['tracking'],
                  'Descartadas':['dismissed'],'Todas':['new','saved','tracking','dismissed']}
        proposals=[p for p in proposals if p.state in statuses[selected]]
        if not proposals: st.info('No hay propuestas para este filtro.')
        for p in proposals:
            with st.container(border=True):
                st.markdown(f'**{p.subject}**')
                st.caption(f'{p.created_at:%d/%m/%Y} · {p.state} · propuesta explícita #{p.id}')
                st.write(p.reason)
                if p.contribution_id:
                    if st.button('Ver aportación de origen',key=f'proposal_src47_{p.id}'):
                        st.session_state['contribution_id_47']=p.contribution_id
                        st.session_state['pending_dd_section47']='Aportaciones compartidas'
                        st.rerun()
                if p.player_id:
                    if st.button('Abrir ficha del jugador',key=f'proposal_player47_{p.id}'):
                        _go('Jugadores',player=p.player_id)
                with st.expander('Pedir una ampliación de esta propuesta',expanded=False):
                    _request_form(user,sid,default_match=p.match_id,default_player=p.player_id,
                                  default_proposal=p.id)
                with st.expander('Compartir propuesta con personas concretas',expanded=False):
                    with session_scope() as db:
                        people=list(db.scalars(select(User).where(User.active.is_(True),User.deleted_at.is_(None)).order_by(User.full_name)).all())
                    known={u.id:u.full_name for u in people if u.id != user['id']}
                    try: existing_ids=json.loads(p.shared_with or '[]')
                    except ValueError: existing_ids=[]
                    selected_staff=st.multiselect('Destinatarios',list(known),
                        default=[uid for uid in existing_ids if uid in known],format_func=known.get,
                        key=f'share_p47_{p.id}')
                    if st.button('Aplicar acceso selectivo',key=f'share_p47_go_{p.id}'):
                        try:
                            with session_scope() as db:
                                domain.share_proposal(db,actor_id=user['id'],proposal_id=p.id,
                                    recipient_ids=selected_staff)
                            st.success('Acceso actualizado. Las notas privadas del autor siguen protegidas.');st.rerun()
                        except Exception as exc: st.error(str(exc))

                with st.form(f'decide47_{p.id}'):
                    decision=st.radio('Qué quieres hacer',[
                        'Guardar el informe para después','Iniciar seguimiento deportivo',
                        'Descartar la propuesta','Devolver a pendientes'],
                        index=0,key=f'decision_choice47_{p.id}')
                    commit=st.form_submit_button('Confirmar decisión')
                if commit:
                    target={'Guardar el informe para después':'saved',
                        'Iniciar seguimiento deportivo':'tracking','Descartar la propuesta':'dismissed',
                        'Devolver a pendientes':'new'}[decision]
                    try:
                        with session_scope() as db:
                            if target=='tracking' and not p.player_id:
                                raise ValueError('Identifica al jugador antes de iniciar seguimiento formal. Puedes guardar la propuesta entretanto.')
                            domain.decide_proposal(db,actor_id=user['id'],proposal_id=p.id,state=target)
                            if target=='tracking':
                                from repositories import planning as planning_repo
                                existing=db.scalar(select(PlayerSeasonDecision).where(
                                    PlayerSeasonDecision.player_id==p.player_id,
                                    PlayerSeasonDecision.season_id==sid))
                                planning_repo.upsert_season_decision(db,user['id'],season_id=sid,
                                    player_id=p.player_id,status='Seguimiento',priority=2,
                                    director_note=existing.director_note if existing else None,
                                    model_role_id=existing.model_role_id if existing else None,
                                    fit_score=existing.fit_score if existing else None,
                                    current_level=existing.current_level if existing else None,
                                    potential_score=existing.potential_score if existing else None)
                        st.success('Decisión guardada, con autor e histórico.');st.rerun()
                    except Exception as exc: st.error(str(exc))
    elif section=='Aportaciones compartidas':
        selected_id=st.session_state.get('contribution_id_47')
        with session_scope() as db:
            rows=[r for r in domain.list_contributions(db,actor_id=user['id'],season_id=sid,limit=150) if r.status=='shared']
        if selected_id:
            matching=next((r for r in rows if r.id==selected_id),None)
            if matching:
                _show_contribution(matching,user['id'])
                if st.button('Cerrar detalle',key='dd_close_contrib47'):
                    st.session_state.pop('contribution_id_47',None);st.rerun()
            else:
                st.warning('La aportación no está compartida con DD.')
        else:
            if not rows: st.info('Aún no hay observaciones compartidas en la 4.7.')
            for row in rows[:100]:
                with st.expander(f'{row.updated_at:%d/%m} · {row.title}'):
                    _show_contribution(row,user['id'])
        with st.expander('Informes incorporados antes de la 4.7',expanded=False):
            with session_scope() as db:
                originals=list(db.scalars(select(Report).options(joinedload(Report.match),
                      joinedload(Report.reporter)).where(
                      Report.status.in_(FINAL_REPORT_STATUSES),Report.match.has(Match.season_id==sid))
                      .order_by(Report.submitted_at.desc()).limit(75)).unique().all())
            for row in originals:
                st.markdown(f'**{row.reporter.full_name}** · {row.match.round_name} · {row.submitted_at:%d/%m}' if row.submitted_at else row.match.round_name)
                with st.expander('Ver síntesis del informe'):
                    for val in (row.own_team_note,row.opponent_overview,row.key_takeaways):
                        if val: st.write(val)


def players(user):
    target=st.session_state.get('workspace_player_id')
    if target: return player_detail(user,int(target))
    page_header('Jugadores','Catálogo con búsqueda y filtros. Sin medias privadas expuestas.')
    sid=_season()
    search=st.text_input('Buscar jugador por nombre',key='catalog_search47')
    col1,col2=st.columns([3,2])
    with session_scope() as db:
        teams=list(db.scalars(select(Team).where(Team.active.is_(True),
                     Team.is_test.is_(False)).order_by(Team.name)).all())
    team_names={t.id:t.name for t in teams}
    team_filter=col1.selectbox('Equipo',[None]+list(team_names),
       format_func=lambda tid:team_names.get(tid,'Todos los equipos'),key='catalog_team47')
    pos_filter=col2.selectbox('Posición',['Todas','POR','LD','LI','DCI','DCD','DFC','MC','MCO','ED','EI','DC'],
       key='catalog_pos47')
    with session_scope() as db:
        stmt=select(Player).where(Player.active.is_(True),Player.merged_into_id.is_(None))
        if search.strip(): stmt=stmt.where(or_(Player.full_name.ilike(f'%{search.strip()}%'),
                                                 Player.display_name.ilike(f'%{search.strip()}%')))
        if pos_filter!='Todas': stmt=stmt.where(Player.primary_position==pos_filter)
        if team_filter is not None:
            stmt=stmt.where(Player.id.in_(select(TeamRoster.player_id).where(
                TeamRoster.team_id==team_filter,TeamRoster.season_id==sid,
                TeamRoster.active.is_(True))))
        total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        count=st.selectbox('Filas por página',[25,50],key='catalog_page_size47')
        maximum=max(1,(total+count-1)//count)
        # A changing filter resets the page without mutating a live widget key.
        signature=f'{search}|{team_filter}|{pos_filter}|{count}'
        if st.session_state.get('catalog_signature47')!=signature:
            st.session_state['catalog_signature47']=signature
            st.session_state['catalog_page_input47']=1
        page=st.number_input('Página',min_value=1,max_value=maximum,key='catalog_page_input47')
        chunk=list(db.scalars(stmt.order_by(Player.full_name,Player.id)
              .offset((page-1)*count).limit(count)).all())
    st.caption(f'{total} jugadores encontrados · Página {page} de {maximum}')
    if not chunk:
        st.info('No hay jugadores coincidentes. Prueba otra búsqueda.');return
    df=pd.DataFrame([{'Jugador':p.display_name or p.full_name,
       'Posición':p.primary_position or '—','Nacionalidad':p.nationality or '—'} for p in chunk])
    idx=_table_select(df,key=f'players_table47_{st.session_state.get("selection_epoch47",0)}_{page}_{signature}')
    if idx is not None: _go('Jugadores',player=chunk[idx].id)


def player_detail(user,player_id):
    if st.button('← Volver al catálogo',key=f'playerback47_{player_id}'):
        st.session_state.pop('workspace_player_id',None);st.rerun()
    sid=_season()
    with session_scope() as db:
        p=db.get(Player,player_id)
        if not p or not p.active:
            st.error('No existe este jugador.');return
        rosters=list(db.scalars(select(TeamRoster).options(joinedload(TeamRoster.team)).where(
                  TeamRoster.player_id==player_id,TeamRoster.season_id==sid,
                  TeamRoster.active.is_(True))).unique().all()) if sid else []
        contributions=domain.list_contributions(db,actor_id=user['id'],season_id=sid,
                  player_id=player_id) if sid else []
        legacy=[]
        if can_direct(user) or can_admin(user) or can_report(user):
            stmt=select(PlayerEvaluation,Report).options(joinedload(Report.match)).join(Report,Report.id==PlayerEvaluation.report_id).where(
                    PlayerEvaluation.player_id==player_id,Report.status.in_(FINAL_REPORT_STATUSES))
            if not (can_direct(user) or can_admin(user)):
                stmt=stmt.where(Report.reporter_id==user['id'])
            legacy=list(db.execute(stmt.order_by(Report.submitted_at.desc()).limit(40)).all())
        opinions_stmt=select(MatchOpinionPlayer,MatchOpinion).join(
            MatchOpinion,MatchOpinion.id==MatchOpinionPlayer.opinion_id).where(
            MatchOpinionPlayer.player_id==player_id)
        if not (can_direct(user) or can_admin(user)):
            opinions_stmt=opinions_stmt.where(MatchOpinion.user_id==user['id'])
        neutral_notes=list(db.execute(opinions_stmt.limit(60)).all())
        decision=db.scalar(select(PlayerSeasonDecision).where(PlayerSeasonDecision.player_id==player_id,
                PlayerSeasonDecision.season_id==sid)) if sid and can_direct(user) else None
    page_header(p.display_name or p.full_name,'Ficha deportiva · evidencia identificada y muestra disponible')
    st.caption(' · '.join([p.primary_position or 'Posición desconocida',
                          ', '.join(r.team.name for r in rosters) if rosters else 'Equipo no confirmado']))
    scores_by_observer={}
    for ev,r in legacy:
        if ev.general_rating is not None and ev.general_rating>0:
            scores_by_observer[(r.match_id,r.reporter_id)] = float(ev.general_rating)
    for ev,op in neutral_notes:
        if ev.rating is not None and ev.rating>0:
            scores_by_observer.setdefault((op.match_id,op.user_id),float(ev.rating))
    for c in sorted(contributions,key=lambda r:(r.updated_at,r.id)):
        val=_contribution_summary(c).get('nota')
        if c.kind=='individual' and c.match_id and val is not None and float(val)>0:
            scores_by_observer[(c.match_id,c.author_id)]=float(val)
    ratings=list(scores_by_observer.values())
    latest=len({mid for mid,uid in scores_by_observer})
    c1,c2,c3=st.columns(3)
    c1.metric('Partidos evaluados',latest)
    c2.metric('Nota (fuentes visibles)',f'{sum(ratings)/len(ratings):.1f}' if ratings else 'Sin muestra')
    c3.metric('Opiniones con nota',len(ratings))
    if decision: st.caption(f'Decisión DD actual: {decision.status} · Prioridad {decision.priority}')
    st.markdown('### Evidencia disponible')
    if not contributions and not legacy and not neutral_notes:
        st.info('Todavía no existen valoraciones accesibles con tu perfil. No se interpreta como un 0.')
    for row in contributions:
        with st.expander(f'{row.updated_at:%d/%m} · {row.title}'):_show_contribution(row,user['id'])
    for ev,rep in legacy:
        st.write(f'**{rep.match.match_date:%d/%m} · nota {ev.general_rating if ev.general_rating else "—"}**')
        if ev.short_note: st.caption(ev.short_note)
    for ev,op in neutral_notes:
        st.write(f'**Valoración histórica · nota {ev.rating if ev.rating is not None else "—"}**')
        if ev.note: st.caption(ev.note)
    if can_direct(user) and sid:
        with st.expander('Solicitar una ampliación sobre este jugador',expanded=False):
            _request_form(user,sid,default_player=player_id)
    _correction_form(user,'player',player_id,sid)


def squad(user):
    if not can_direct(user):
        st.error('Plantilla deportiva reservada a Dirección Deportiva.');return
    page_header('Plantilla · Noname','Rendimiento con muestra, evolución y fuentes. No se crean necesidades de fichaje automáticamente.')
    sid=_season(); own_id=_own()
    if not sid or not own_id: st.info('Configura temporada y equipo propio.');return
    with session_scope() as db:
        roster=list(db.scalars(select(TeamRoster).options(joinedload(TeamRoster.player)).where(
             TeamRoster.team_id==own_id,TeamRoster.season_id==sid,TeamRoster.active.is_(True))
             .order_by(TeamRoster.shirt_number)).unique().all())
        rows=list(db.execute(select(PlayerEvaluation,Report).options(joinedload(Report.match)).join(Report,
             Report.id==PlayerEvaluation.report_id).where(
             PlayerEvaluation.team_id==own_id,Report.status.in_(FINAL_REPORT_STATUSES),
             Report.match.has(Match.season_id==sid))).all())
        extras=list(db.scalars(select(Contribution).where(Contribution.season_id==sid,
            Contribution.team_id==own_id,Contribution.status=='shared',
            Contribution.kind=='individual',Contribution.player_id.is_not(None))).all())
    # One final numeric evaluation per (player, match, author). New individual
    # observations take precedence over legacy if the same source is present.
    grouped=defaultdict(dict)
    for ev,rep in rows:
        if ev.general_rating is not None and ev.general_rating>0:
            grouped[ev.player_id][(rep.match_id,rep.reporter_id)] = (
                rep.match.match_date,float(ev.general_rating),'legacy')
    with session_scope() as db:
        neutral=list(db.execute(select(MatchOpinionPlayer,MatchOpinion,Match).join(
            MatchOpinion,MatchOpinion.id==MatchOpinionPlayer.opinion_id).join(
            Match,Match.id==MatchOpinion.match_id).where(
            MatchOpinionPlayer.team_id==own_id,Match.season_id==sid)).all())
    for ev,op,match in neutral:
        if ev.rating is not None and ev.rating>0:
            grouped[ev.player_id].setdefault((match.id,op.user_id),
                (match.match_date,float(ev.rating),'legacy_opinion'))
    for item in sorted(extras,key=lambda r:(r.updated_at,r.id)):
        data=_contribution_summary(item)
        if data.get('nota') is not None and float(data['nota'])>0 and item.match_id:
            key=(item.match_id,item.author_id)
            with session_scope() as db:
                m=db.get(Match,item.match_id)
            if m: grouped[item.player_id][key]=(m.match_date,float(data['nota']),'47')
    records=[]
    for r in roster:
        observations=grouped.get(r.player_id,{})
        scores=[ob[1] for ob in observations.values()]
        games=defaultdict(list)
        for (mid,uid),(when,score,source) in observations.items():
            games[mid].append((when,score))
        # Trend uses distinct matches, never multiple colleagues on one match.
        games_ordered=sorted(((min(t for t,v in vals),sum(v for t,v in vals)/len(vals))
                 for vals in games.values()),key=lambda a:a[0])
        trend='—'
        if len(games_ordered)>=4:
            half=len(games_ordered)//2
            delta=(sum(v for _,v in games_ordered[-half:])/half -
                   sum(v for _,v in games_ordered[:half])/half)
            trend='Mejora' if delta>=0.8 else ('Baja' if delta<=-0.8 else 'Estable')
        records.append({'Jugador':r.player.display_name or r.player.full_name,
            'Pos.':r.usual_position or r.player.primary_position or '—',
            'PJ evaluados':len(games),'Opiniones':len(scores),
            'Media':f'{sum(scores)/len(scores):.1f}' if scores else '—','Tendencia':trend})
    if not records: st.info('No hay plantilla propia documentada. No se inventa un once.');return
    idx=_table_select(pd.DataFrame(records),key=f'squad47_{st.session_state.get("selection_epoch47",0)}')
    if idx is not None: _go('Jugadores',player=roster[idx].player_id)
    st.caption('Tendencia solo con 4+ partidos distintos; es un indicio, no una recomendación automática. Las medias muestran fuente y muestra al entrar al jugador.')
    by_pos=defaultdict(int)
    for rec in records: by_pos[rec['Pos.']]+=1
    st.caption('Cobertura registrada: '+', '.join(f'{pos} {n}' for pos,n in sorted(by_pos.items())))


def admin(user):
    if not can_admin(user): st.error('Acceso reservado a Administración.');return
    page_header('Administración técnica','Mantenimiento ocasional. Horarios y valoraciones voluntarias no generan incidencias.')
    section=st.radio('Sección',['Incidencias','Usuarios y permisos','Datos deportivos','Mantenimiento'],horizontal=True,key='admin_section47')
    if section=='Incidencias':
        with session_scope() as db:
            items=domain.list_corrections(db,actor_id=user['id'],only_open=True)
        if not items: st.success('Sin incidencias comunicadas pendientes de revisión.')
        for item in items:
            with st.expander(f'#{item.id} · {item.entity_type} · {item.description[:80]}'):
                st.write(item.description)
                st.caption(f'{item.created_at:%d/%m/%Y} · Enviado por usuario {item.author_id}')
                with st.form(f'admin_resolve47_{item.id}'):
                    status=st.radio('Resolución',['resolved','dismissed'],
                           format_func=lambda x:'Corregida' if x=='resolved' else 'Descartada',horizontal=True)
                    explanation=st.text_area('Qué se ha revisado o corregido')
                    save=st.form_submit_button('Cerrar incidencia')
                if save:
                    try:
                        with session_scope() as db:
                            domain.resolve_correction(db,actor_id=user['id'],correction_id=item.id,
                                state=status,resolution=explanation)
                        st.success('Incidencia resuelta con trazabilidad.');st.rerun()
                    except Exception as exc: st.error(str(exc))
        with st.expander('Controles automáticos de calidad',expanded=False):
            from views.admin_hub import _quality
            _quality(user)
    elif section=='Usuarios y permisos':
        from views import admin as admin_legacy
        admin_legacy._section_users(user)
    elif section=='Datos deportivos':
        from views.admin_hub import _real_data_status
        _real_data_status(user)
        with st.expander('Catálogos, plantillas y temporadas',expanded=False):
            from views import catalog as legacy_catalog
            which=st.radio('Catálogo',['Temporadas','Competiciones','Equipos','Plantillas'],horizontal=True)
            if which=='Temporadas':legacy_catalog._section_seasons(user)
            elif which=='Competiciones':legacy_catalog._section_competitions(user)
            elif which=='Equipos':legacy_catalog._section_teams(user)
            else:legacy_catalog._section_rosters(user)
    else:
        from views.admin_hub import _technical
        st.warning('Haz una copia antes de utilizar herramientas que puedan afectar al histórico.')
        _technical(user)


def render(user, label):
    if label=='Inicio':return home(user)
    if label=='Partidos':return matches(user)
    if label=='Mis partidos':return own_matches(user)
    if label=='Mis valoraciones':return my_contributions(user,ratings_only=True)
    if label=='Mis aportaciones':return my_contributions(user)
    if label=='Mis solicitudes':return my_requests(user)
    if label=='Jugadores':return players(user)
    if label=='Plantilla':return squad(user)
    if label=='Dirección Deportiva':return director(user)
    if label=='Administración':return admin(user)
    st.error('Sección no disponible para este perfil.')
