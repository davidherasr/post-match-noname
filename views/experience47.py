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
from core.match_priority472 import current_fixtures
from repositories import publication473 as publication
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
    from core.auth import current_user
    from core.permissions import navigation_for
    menu=navigation_for(current_user())
    if dest == 'Mis aportaciones' and dest not in menu:
        st.session_state.pop('workspace_match_id',None)
        st.session_state['partidos_mis_aportaciones471']=True
        dest='Partidos'
    elif dest == 'Mis valoraciones' and dest not in menu:
        st.session_state.pop('workspace_match_id',None)
        st.session_state['partidos_mis_valoraciones471']=True
        dest='Mis partidos'
    elif dest in {'Partidos','Mis partidos'} and match is not None:
        st.session_state.pop('partidos_mis_aportaciones471',None)
        st.session_state.pop('partidos_mis_valoraciones471',None)
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
    # Unknown kick-off is not an error: leave it out rather than displaying noise.
    return f'{m.match_date:%d/%m/%Y}' + (f' · {m.kickoff_at:%H:%M}' if m.kickoff_at else '')


def _fixtures(season_id, own_id=None, count=100):
    with session_scope() as db:
        stmt = select(Match).options(joinedload(Match.home_team), joinedload(Match.away_team)).where(
            Match.season_id == season_id, official_match_clause())
        if own_id is not None:
            stmt = stmt.where(or_(Match.home_team_id == own_id, Match.away_team_id == own_id))
        return list(db.scalars(stmt.order_by(Match.match_date.desc(), Match.id.desc()).limit(count)).unique().all())


def _published_list(matches):
    if not matches:return []
    with session_scope() as db:
        opened=publication.opened_match_ids(db,[m.id for m in matches])
    return [m for m in matches if m.id in opened]


def _can_prepare(user):
    from core.permissions import can_admin, can_direct, can_report
    return bool(can_admin(user) or can_direct(user) or (can_report(user) and
                (user or {}).get('participation_profile') in {'full','free'}))


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
    """Email-style, accessible activity list with explicit seen/save controls."""
    if not season_id:
        return
    from ui.mobile472 import inbox_component
    if not intro:
        st.markdown('### Novedades del cuerpo técnico')
        value=st.selectbox('Consultar', ['Nuevos','Todos','Guardados'],
              key='inbox_filter_472', label_visibility='collapsed')
    else:
        value='Nuevos'
    with session_scope() as db:
        events=domain.visible_events(db,actor_id=user['id'],season_id=season_id,
            filter_by={'Nuevos':'new','Todos':'all','Guardados':'saved'}[value],
            limit=8 if intro else 80)
    view=[{'id':ev.id,'title':ev.title,'detail':ev.detail or '',
           'date':ev.created_at.strftime('%d/%m'),
           'seen':bool(state and state.seen_at),'saved':bool(state and state.saved_at)}
          for ev,state in events]
    result=inbox_component(key=f'activity_list472_{"home" if intro else "dd"}_{value}',
                           data={'items':view})
    action=result.action
    if not isinstance(action,dict) or action.get('action') not in {'open','seen','unsee','save','unsave'}:
        return
    # Revalidate with the same access-controlled event collection; event ids
    # submitted from the browser are untrusted.
    chosen=next((ev for ev,state in events if ev.id==action.get('id')),None)
    if chosen is None:
        st.error('La novedad no está disponible para esta cuenta.');return
    if action['action'] != 'open':
        try:
            with session_scope() as db:
                domain.change_event_state(db,actor_id=user['id'],event_id=chosen.id,action=action['action'])
            st.rerun()
        except Exception as exc: st.error(str(exc))
        return
    dest,kw=_direct_link_to_event(chosen)
    if chosen.target_type=='request' and can_direct(user):
        st.session_state['pending_dd_section47']='Solicitudes'
        dest,kw='Dirección Deportiva',{}
    if chosen.target_type in {'legacy_report','legacy_opinion'}:
        with session_scope() as db:
            source=db.get(Report if chosen.target_type=='legacy_report' else MatchOpinion,chosen.target_id)
            if not source or not can_direct(user):
                st.error('Fuente no disponible para tu perfil.');return
            kw={'match':source.match_id}
    if chosen.target_type=='contribution':
        st.session_state['contribution_id_47']=chosen.target_id
        if can_direct(user):st.session_state['pending_dd_section47']='Aportaciones compartidas'
        dest='Dirección Deportiva' if can_direct(user) else 'Mis aportaciones'
        kw={}
    _go(dest,**kw)


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
    page_header('Inicio','Tu trabajo de esta semana, sin filtros ni tareas artificiales.')
    season=_season()
    if not season:
        st.info('No hay temporada activa.');return
    if can_direct(user):
        with session_scope() as db:
            proposals=[p for p in domain.list_proposals(db,user['id'],season) if p.state=='new']
            requests=[r for r in domain.list_requests(db,actor_id=user['id'],season_id=season)
                      if r.sender_id==user['id'] and r.state=='pending']
        with st.container(border=True):
            st.subheader('Revisar lo que ha enviado el staff')
            st.write(f'{len(proposals)} jugadores propuestos · {len(requests)} solicitudes esperando respuesta')
            if st.button('Abrir Dirección Deportiva',type='primary',key='home_dd471',use_container_width=True):
                _go('Dirección Deportiva')
    elif can_report(user):
        own_id=_own()
        fixtures=_fixtures(season,own_id=own_id,count=100) if own_id else []
        last,next_game=current_fixtures(fixtures,local_today())
        available=_published_list([m for m in fixtures if m.match_date<=local_today()])
        if available:
            ready=available[0]
            with st.container(border=True):
                st.caption('PARTIDO DISPONIBLE · VALORACIÓN INDIVIDUAL')
                st.subheader(_fixture_label(ready))
                st.caption(f'{ready.match_date:%d/%m/%Y} · {ready.round_name or "Jornada"}')
                if st.button('Valorar futbolistas',type='primary',key='home_ratings473',use_container_width=True):
                    st.session_state['contrib_mode47']='board472'
                    _go('Partidos',match=ready.id)
        elif last:
            st.info('El último encuentro todavía no está publicado para valorar.')
        if last and _can_prepare(user) and last.id not in {m.id for m in available}:
            if st.button('Preparar y publicar el último partido',key='home_release473',use_container_width=True):
                _go('Partidos',match=last.id)
        if next_game:
            rival=next_game.away_team if next_game.home_team_id==own_id else next_game.home_team
            with st.container(border=True):
                st.caption('PRÓXIMO RIVAL')
                st.markdown(f'**{rival.name}** · {next_game.match_date:%d/%m}')
                if st.button('Consultar rival y partidos',key='home_rival471',use_container_width=True):
                    _go('Partidos',match=next_game.id)
        with session_scope() as db:
            requests=[r for r in domain.list_requests(db,actor_id=user['id'],season_id=season,include_closed=False)
                      if r.recipient_id==user['id']]
        if requests:
            if st.button(f'Responder solicitudes de Aarón ({len(requests)})',key='home_req471',use_container_width=True):
                _go('Mis solicitudes')
    with st.expander('Novedades del staff',expanded=bool(can_direct(user))):
        _events(user,season,intro=True)
    if can_report(user):
        with st.expander('Mis observaciones y trabajos anteriores',expanded=False):
            if st.button('Abrir mis aportaciones',key='home_work471',use_container_width=True):
                _go('Mis aportaciones')


def _table_select(df: pd.DataFrame, *, key: str):
    if df.empty:
        return None
    selection = st.dataframe(df, hide_index=True, use_container_width=True,
        on_select='rerun', selection_mode='single-row', key=key,
        height=min(560, 39*(len(df)+1)))
    rows = selection.selection.rows
    return int(rows[0]) if rows else None


def _latest_match_state(user, match, *, full=False):
    """Do not mistake a quick team score for a finished analyst postmatch."""
    with session_scope() as db:
        kind='complete' if full else 'quick'
        rows=list(db.scalars(select(Contribution).where(
            Contribution.author_id==user['id'],Contribution.match_id==match.id,
            Contribution.kind==kind).order_by(Contribution.id.desc())).all())
        legacy=db.scalar(select(func.count(Report.id)).where(
            Report.reporter_id==user['id'],Report.match_id==match.id,
            Report.status.in_(FINAL_REPORT_STATUSES))) or 0
    if legacy or any(row.status=='shared' for row in rows):
        return 'shared',next((row for row in rows if row.status=='shared'),None)
    draft=next((row for row in rows if row.status=='draft'),None)
    return ('draft',draft) if draft else ('new',None)


def _review_previous_match(m, *, target, mode, label):
    if st.button(label,key=f'review471_{target}_{m.id}',use_container_width=True):
        st.session_state['contrib_mode47']=mode
        st.session_state.pop('edit_contribution_47',None)
        _go(target,match=m.id)


def matches(user, own_only=False):
    """The last own match is the task. Everything else is secondary."""
    team_selection = st.session_state.get('workspace_team_id')
    if team_selection and not own_only:
        return team_detail(user, int(team_selection))
    selected = st.session_state.get('workspace_match_id')
    if selected:
        return match_detail(user,int(selected),return_to='Mis partidos' if own_only else 'Partidos')
    if own_only and st.session_state.get('partidos_mis_valoraciones471'):
        if st.button('← Volver a mis partidos',key='back_to_own471'):
            st.session_state.pop('partidos_mis_valoraciones471',None)
            st.rerun()
        return my_contributions(user,ratings_only=True)
    if not own_only and st.session_state.get('partidos_mis_aportaciones471'):
        if st.button('← Volver a partidos',key='back_to_matches471'):
            st.session_state.pop('partidos_mis_aportaciones471',None)
            st.rerun()
        return my_contributions(user)
    page_header('Mis partidos' if own_only else 'Partidos',
                'Empieza por el último encuentro. Los anteriores siguen disponibles cuando los necesites.')
    season=_season()
    if not season:
        st.info('No hay temporada activa.'); return
    own_id=_own()
    today=local_today()
    mine=_fixtures(season,own_id=own_id,count=180) if own_id else []
    last,future=current_fixtures(mine,today)
    released=_published_list([m for m in mine if m.match_date<=today])
    dest='Mis partidos' if own_only else 'Partidos'
    if released:
        latest=released[0]
        with st.container(border=True):
            st.caption('ÚLTIMO PARTIDO ABIERTO PARA VALORAR')
            st.subheader(_fixture_label(latest))
            st.caption(f'{latest.match_date:%d/%m/%Y} · {latest.round_name or "Jornada"}')
            if st.button('Valorar jugadores',key='main_rating473',type='primary',use_container_width=True):
                st.session_state['contrib_mode47']='board472'
                _go(dest,match=latest.id)
    elif own_id:
        st.info('Todavía no hay partidos publicados para valorar. En cuanto se carguen los dos XI aparecerán aquí.')
    if last and (not released or last.id!=released[0].id) and _can_prepare(user) and not own_only:
        with st.container(border=True):
            st.caption('PENDIENTE DE PUBLICAR · ADMINISTRACIÓN / ANALISTAS')
            st.markdown('**'+_fixture_label(last)+'**')
            if st.button('Cargar alineaciones y publicar',key='main_release473',use_container_width=True):
                _go(dest,match=last.id)
    if future:
        with st.container(border=True):
            st.caption('PRÓXIMO PARTIDO')
            st.markdown('**'+_fixture_label(future)+'**')
            st.caption(f'{future.match_date:%d/%m/%Y}')
            if not own_only and st.button('Ver próximo partido',key='next471',use_container_width=True):
                _go('Partidos',match=future.id)
    if own_only:
        with st.expander('Elegir otro partido o consultar mis valoraciones',expanded=False):
            prior=[m for m in released if not released or m.id!=released[0].id]
            for match in prior[:25]:
                if st.button(f'{match.match_date:%d/%m} · {_fixture_label(match)}',
                             key=f'own_prior471_{match.id}',use_container_width=True):
                    _go('Mis partidos',match=match.id)
            st.divider()
            if st.button('Ver todas mis valoraciones',key='own_history471',use_container_width=True):
                _go('Mis valoraciones')
        with session_scope() as db:
            requests=[r for r in domain.list_requests(db,actor_id=user['id'],season_id=season,include_closed=False)
                      if r.recipient_id==user['id']]
        if requests:
            with st.expander(f'Solicitudes recibidas ({len(requests)})',expanded=False):
                if st.button('Responder a una solicitud',key='own_req471'):
                    _go('Mis solicitudes')
        return
    # Analysts and DD may consult the complete schedule, but it is not their
    # starting point. No scope/date filters before the primary action.
    with st.expander('Buscar partidos anteriores o de otros equipos',expanded=False):
        scope=st.radio('Equipos',['Noname','Todos los equipos','Otros equipos'],horizontal=True,key='match_scope471')
        fixtures=_fixtures(season, own_id=own_id if scope=='Noname' else None,count=500)
        if scope=='Otros equipos' and own_id:
            fixtures=[m for m in fixtures if own_id not in (m.home_team_id,m.away_team_id)]
        query=st.text_input('Buscar por equipo o jornada',key='match_search471',placeholder='Escribe el equipo...')
        if query.strip():
            needle=query.strip().casefold()
            fixtures=[m for m in fixtures if needle in _fixture_label(m).casefold() or needle in (m.round_name or '').casefold()]
        if fixtures:
            rows=[{'Fecha':f'{m.match_date:%d/%m/%Y}','Partido':_fixture_label(m)} for m in fixtures[:100]]
            idx=_table_select(pd.DataFrame(rows),key=f'match_lite471_{scope}_{query}_{st.session_state.get("selection_epoch47",0)}')
            if idx is not None: _go('Partidos',match=fixtures[idx].id)
        else:
            st.caption('No se han encontrado encuentros.')
        if can_direct(user) or (can_report(user) and working_profile(user) in {'analyst','director'}):
            if st.checkbox('Quiero registrar un partido oficial que falta',key='show_new_match471'):
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
    st.caption(f'{row.updated_at:%d/%m/%Y %H:%M} · revisión {row.revision}')
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


def _mobile_board(user, match, own_id):
    """Native mobile-style card, backed by actual match/season roster records."""
    if not can_report(user):
        st.error('Esta cuenta no tiene permiso para valorar.')
        return
    from repositories import mobile472
    from ui.mobile472 import scoreboard_component
    own_match=bool(own_id and own_id in (match.home_team_id,match.away_team_id))
    if own_match:
        own_team=match.home_team if match.home_team_id==own_id else match.away_team
        rival_team=match.away_team if match.home_team_id==own_id else match.home_team
    else:
        own_team=match.home_team
        rival_team=match.away_team
    with session_scope() as db:
        own_rows,own_confirmed=mobile472.choices(db,match.id,own_team.id)
        rival_rows,rival_confirmed=mobile472.choices(db,match.id,rival_team.id)
        _,annotated=mobile472.existing(db,author_id=user['id'],match_id=match.id)
    if not own_confirmed or not rival_confirmed:
        st.error('Este encuentro no tiene los dos XI confirmados. Solicita una corrección a Administración.')
        return
    suggested_form='4-2-3-1'  # backwards-compatible component field; not inferred.
    initial={}
    for side,team,rows in [('own',own_team,own_rows),('rival',rival_team,rival_rows)]:
        for row in rows:
            prior=annotated.get(f"{team.id}:{row['key']}")
            if prior:initial[f"{side}:{row['key']}"]=prior
    ui=scoreboard_component(
        key=f'mobile_rating472_{match.id}_{user["id"]}',
        data={'fixture':_fixture_label(match),'subtitle':f'{match.round_name or "Partido"} · {_date_label(match)}',
              'is_own_match':own_match,'own_name':own_team.name,'rival_name':rival_team.name,
              'own':own_rows,'rival':rival_rows,
              'own_hint':('Alineación confirmada' if own_confirmed else 'Plantilla de temporada: no confirma que todos jugaran') if own_rows and own_match else
                         ('Jugadores del encuentro' if own_confirmed else 'Posiciones provisionales, sin nombres confirmados'),
              'rival_hint':('Alineación confirmada' if rival_confirmed else 'Plantilla de temporada: no confirma participación') if rival_confirmed or any(x['player_id'] for x in rival_rows) else
                            'Posiciones orientativas · no se han confirmado los jugadores del rival',
              'team_score':None,'initial':initial,
              'formation':suggested_form},
    )
    packet=ui.save
    if packet is not None:
        try:
            if not isinstance(packet,dict):raise ValueError('Datos de valoración inválidos.')
            values=packet.get('players',[])
            if not isinstance(values,list) or any(not isinstance(p,dict) or p.get('side') not in {'own','rival'} for p in values):
                raise ValueError('Datos de jugador inválidos.')
            with session_scope() as db:
                saved=[]
                own_items=[{k:v for k,v in entry.items() if k!='side'} for entry in values if entry['side']=='own']
                rival_items=[{k:v for k,v in entry.items() if k!='side'} for entry in values if entry['side']=='rival']
                clear=packet.get('cleared', [])
                if not isinstance(clear,list) or any(not isinstance(x,dict) or x.get('side') not in {'own','rival'} for x in clear):
                    raise ValueError('Listado de notas retiradas inválido.')
                own_clear=[x['key'] for x in clear if x['side']=='own']
                rival_clear=[x['key'] for x in clear if x['side']=='rival']
                if packet.get('team_score') is not None or own_items or own_clear:
                    saved.append(mobile472.save_board(db,actor_id=user['id'],match_id=match.id,
                       team_id=own_team.id,payload={'team_score':packet.get('team_score'), 'players':own_items,'cleared':own_clear,
                                                   'formation':match.home_formation if not own_match and match.home_formation_known else '4-2-3-1'}))
                if rival_items or rival_clear:
                    saved.append(mobile472.save_board(db,actor_id=user['id'],match_id=match.id,
                       team_id=rival_team.id,payload={'players':rival_items,'cleared':rival_clear,
                          'formation':suggested_form}))
            total=sum(x['evaluados'] for x in saved)
            stars=sum(x['propuestas'] for x in saved)
            deleted=sum(x.get('retiradas',0) for x in saved)
            st.success(f'Cambios guardados · {total} jugadores valorados'+
                       (f' · {deleted} notas retiradas' if deleted else '')+
                       (f' · {stars} propuestas enviadas a Aarón' if stars else '')+'.')
        except Exception as exc:
            st.error(f'No se ha guardado la valoración: {exc}')


def _individual_statistics474(user,match):
    """Optional analyst metrics attached to an already published match."""
    if not can_report(user) or working_profile(user) not in {'analyst','director'}:
        return
    from repositories import mobile472,player_metrics474
    with st.expander('Añadir estadísticas individuales (opcional)',expanded=False):
        with session_scope() as db:
            home,_=mobile472.choices(db,match.id,match.home_team_id)
            away,_=mobile472.choices(db,match.id,match.away_team_id)
        participants=[(match.home_team_id,r) for r in home if r['player_id']]+[(match.away_team_id,r) for r in away if r['player_id']]
        if not participants:
            st.caption('Necesitas el XI publicado o un suplente confirmado.');return
        with st.form(f'metrics474_{match.id}'):
            choice=st.selectbox('Futbolista que has analizado',range(len(participants)),
                format_func=lambda idx:f"{participants[idx][1]['name']} · {match.home_team.name if participants[idx][0]==match.home_team_id else match.away_team.name}")
            left,right=st.columns(2)
            with left:
                completed=st.number_input('Pases acertados',min_value=0,max_value=300,value=0)
                total=st.number_input('Pases intentados',min_value=0,max_value=300,value=0)
            with right:
                won=st.number_input('Duelos ganados',min_value=0,max_value=300,value=0)
                duels=st.number_input('Duelos disputados',min_value=0,max_value=300,value=0)
            source=st.text_input('Procedencia',value='Registro manual del analista')
            sent=st.form_submit_button('Guardar estadísticas')
        if sent:
            try:
                tid,player=participants[choice]
                with session_scope() as db:
                    player_metrics474.save_stats(db,actor_id=user['id'],match_id=match.id,team_id=tid,
                        player_id=player['player_id'],passes_complete=int(completed),passes_total=int(total),
                        duels_won=int(won),duels_total=int(duels),source=source)
                st.success('Estadísticas guardadas en la ficha del jugador; no modifican su nota.')
            except Exception as exc:st.error(f'No se guardaron las estadísticas: {exc}')


def _quick(user, match, own_id):
    _mobile_board(user, match, own_id)


def _complete(user, match):
    if not can_report(user):return
    sid=st.session_state.get('edit_contribution_47')
    prior=None
    with session_scope() as db:
        if sid:
            try: prior=domain.get_contribution(db,sid,user['id'])
            except PermissionError:pass
        if not prior:
            prior=db.scalar(select(Contribution).where(
                Contribution.author_id==user['id'],Contribution.match_id==match.id,
                Contribution.kind=='complete',Contribution.status=='draft')
                .order_by(Contribution.id.desc()).limit(1))
    if prior and (prior.kind!='complete' or prior.match_id!=match.id or prior.status!='draft'):
        prior=None
    old=_contribution_summary(prior) if prior else {}
    own_id=_own()
    own_match=own_id in (match.home_team_id,match.away_team_id)
    rival=match.away_team if match.home_team_id==own_id else match.home_team
    st.markdown('### '+(f'Postpartido de {rival.name}' if own_match else 'Informe del partido'))
    st.caption('Escribe solo lo que has visto. Puedes dejar campos vacíos. No necesitas XI ni horario.')
    from ui.mobile472 import postmatch_component
    widget=postmatch_component(key=f'postmatch_mobile472_{match.id}_{user["id"]}',
        data={'title':f'Postpartido de {rival.name}' if own_match else 'Análisis del partido',
              'own_label':'Noname · ¿Qué destacarías?' if own_match else f'{match.home_team.name} · Observaciones',
              'rival_label':f'{rival.name} · ¿Qué destacarías?' if own_match else f'{match.away_team.name} · Observaciones',
              'old':old})
    result=widget.save
    if result is None:return
    try:
        if not isinstance(result,dict) or not isinstance(result.get('values'),dict):
            raise ValueError('Formulario no válido.')
        values=result['values']
        keys={'equipo_propio','rival','conclusion','fortalezas','debilidades',
              'datos_individuales','cortes_video','nota_propio','nota_rival'}
        if set(values) != keys:raise ValueError('El informe está incompleto o contiene campos desconocidos.')
        for field in ('nota_propio','nota_rival'):
            grade=values[field]
            if grade is not None and (type(grade) is not int or grade<1 or grade>10):
                raise ValueError('Nota de equipo fuera de rango.')
        for field in keys-{'nota_propio','nota_rival'}:
            if not isinstance(values[field],str) or len(values[field])>12000:
                raise ValueError('Texto de análisis inválido.')
        if not any(str(value).strip() for value in values.values() if value is not None):
            raise ValueError('Introduce algún dato antes de guardar.')
        data={'ambito':'Ambos' if own_match else 'Partido neutral',**values}
        publish=result.get('publish') is True
        with session_scope() as db:
            row=domain.save_contribution(db,actor_id=user['id'],season_id=match.season_id,
                match_id=match.id,kind='complete',title=f'Postpartido · {_fixture_label(match)}',
                data=data,contribution_id=prior.id if prior else None,
                expected_revision=prior.revision if prior else None,publish=publish)
        if publish:
            st.session_state.pop('edit_contribution_47',None)
            st.session_state.pop('contrib_mode47',None)
            st.success('Postpartido compartido con Aarón.')
        else:
            st.session_state['edit_contribution_47']=row.id
            st.success('Borrador privado guardado. Solo tú puedes verlo hasta compartirlo.')
        st.rerun()
    except Exception as exc:st.error(f'No se ha guardado el postpartido: {exc}')


def _individual(user, match):
    if not can_report(user): return
    st.markdown('### Valorar un jugador')
    st.caption('Nombre o dorsal, nota y comentario. Si te interesa especialmente, envíaselo a Aarón.')
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
        favorite=st.checkbox('⭐ Destacar este jugador para Aarón',value=False)
        publish=st.checkbox('Compartir esta valoración con Aarón',value=False)
        save=st.form_submit_button('Guardar observación',type='primary',use_container_width=True)
    if save:
        try:
            if player_id and not any(r.player_id==player_id and r.team_id==team for r in roster):
                raise ValueError('El jugador seleccionado no figura en la plantilla de ese equipo.')
            with session_scope() as db:
                subject=names.get(player_id) if player_id else f'Dorsal {shirt or "?"} · {zone} · {match.home_team.name if team==match.home_team_id else match.away_team.name}'
                row=domain.save_contribution(db,actor_id=user['id'],season_id=match.season_id,
                   match_id=match.id,team_id=team,player_id=player_id,
                   kind='individual',title=f'Jugador {subject}',
                   data={'posicion_observada':None if zone=='Sin determinar' else zone,
                         'dorsal_observado':shirt or None,'nota':None if rate=='Sin nota' else rate,
                         'comentario':note,'identidad_confirmada':bool(player_id)},publish=publish or favorite)
                if favorite:
                    domain.propose_player(db,actor_id=user['id'],season_id=match.season_id,
                        subject=subject,reason=note.strip() or 'Jugador señalado para revisar por Dirección Deportiva',
                        player_id=player_id,match_id=match.id,contribution_id=row.id)
            st.success('Observación guardada'+(' y jugador destacado para Aarón.' if favorite else '.'));st.rerun()
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


def _lineup_import472(user, match):
    """One obvious phone-friendly entry for pasted ChatGPT/Federación text.

    A plain dorsal;nombre list updates only the seasonal roster. There is no
    silent assumption that the first eleven are the starters.
    """
    permitted = can_direct(user) or can_admin(user) or (can_report(user) and
                (user.get('participation_profile') or 'full') in {'full','free'})
    if not permitted:
        return
    from core.federation_roster import parse_federation_roster
    from repositories import matches as matches_repo
    with st.popover('＋ Cargar alineación', use_container_width=False):
        st.markdown('**Pegar alineación desde el móvil**')
        st.caption('Puedes copiar aquí lo que ChatGPT te haya transcrito. Dos columnas: `dorsal;nombre`.')
        team_id=st.selectbox('Equipo',[match.home_team_id,match.away_team_id],
             format_func=lambda t:match.home_team.name if t==match.home_team_id else match.away_team.name,
             key=f'load_team472_{match.id}')
        text=st.text_area('Texto para importar',height=175,
             placeholder='TITULARES\n1;Juan García\n3;Pedro López\n...\nSUPLENTES\n12;Otro jugador\n\nO simplemente: 7;Nombre del jugador',
             key=f'load_paste472_{match.id}')
        uploaded=st.file_uploader('O elegir archivo .txt / .csv',type=['txt','csv'],
             key=f'load_file472_{match.id}')
        if uploaded is not None:
            raw=uploaded.getvalue()
            if len(raw)>80_000:
                st.error('El archivo supera 80 KB; utiliza una lista de partido.')
                return
            try: text=raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                try:text=raw.decode('cp1252')
                except UnicodeDecodeError:
                    st.error('Archivo no legible como UTF-8 o Windows-1252.');return
        rows=parse_federation_roster(text)
        if rows:
            if len(rows)>60:
                st.error('Demasiados jugadores para una alineación. Revisa el texto.');return
            st.caption(f'{len(rows)} nombres reconocidos · '
                       f'{sum(r.squad_role=="starter" for r in rows)} titulares · '
                       f'{sum(r.squad_role=="substitute" for r in rows)} suplentes')
            st.dataframe(pd.DataFrame([{'Dorsal':r.shirt_number,'Nombre':r.name,
                   'Tipo':{'starter':'Titular','substitute':'Suplente'}.get(r.squad_role,'Plantilla')} for r in rows]),
                   hide_index=True, use_container_width=True)
            if all(r.squad_role is None for r in rows):
                st.info('No hay etiquetas TITULARES/SUPLENTES: se actualizará la plantilla, pero NO se creará un XI.')
            confirm=st.checkbox('He revisado nombres, dorsales y equipo',key=f'confirm_load472_{match.id}')
            if st.button('Guardar nombres y dorsales',key=f'save_paste472_{match.id}',
                        disabled=not confirm,type='primary',use_container_width=True):
                try:
                    with session_scope() as db:
                        result=matches_repo.import_federation_roster_text(db,
                             team_id=team_id,season_id=match.season_id,actor_id=user['id'],
                             text=text,match_id=match.id)
                    st.success(f'Guardados {result["rows"]} jugadores. La ficha del partido ya puede usarlos.')
                    st.rerun()
                except Exception as exc: st.error(f'No se ha importado: {exc}')
        else: st.caption('Pega al menos un jugador. Ejemplo: `7;Nombre Apellido`.')


def _prepare_rating_release473(user,match):
    """One administrative action: paste both XIs and publish, no collective report."""
    from core.lineup473 import parse_xi
    with session_scope() as db:
        state=publication.readiness(db,match.id)
    if state['published']:
        st.success('Partido publicado · las valoraciones individuales están habilitadas.')
        return
    if not _can_prepare(user):
        st.info('Este partido todavía no está abierto para valorar. Aparecerá aquí cuando se publiquen las dos alineaciones.')
        return
    st.subheader('Preparar y publicar el partido')
    st.caption('Pega los 11 titulares con dorsal;nombre;posición para cada equipo. ' 
               'Las posiciones son las de este partido. No hacen falta horarios, resultado ni notas colectivas.')
    with st.form(f'release473_{match.id}'):
        left,right=st.columns(2)
        texts={}
        for col,team in ((left,match.home_team),(right,match.away_team)):
            with col:
                current=state['teams'][team.id]
                st.markdown(f'**{team.name}**')
                st.caption('XI ya completo' if current['ready'] else f'{current["starters"]}/11 titulares confirmados')
                pasted=st.text_area(f'Alineación de {team.name}',height=210,
                    placeholder='TITULARES\n1;Nombre portero;POR\n2;Nombre lateral;LD\n15;Nombre central;DCD\n...')
                uploaded=st.file_uploader('O subir un TXT / CSV',type=['txt','csv'],
                                          key=f'upload473_{match.id}_{team.id}')
                texts[team.id]=pasted
                if uploaded is not None and not pasted.strip():
                    raw=uploaded.getvalue()
                    if len(raw)>80000:
                        texts[team.id]=None
                    else:
                        try:texts[team.id]=raw.decode('utf-8-sig')
                        except UnicodeDecodeError:
                            try:texts[team.id]=raw.decode('cp1252')
                            except UnicodeDecodeError:texts[team.id]=None
        submit=st.form_submit_button('Revisar los 22 titulares',type='primary',use_container_width=True)
    if submit:
        try:
            if any(text is None for text in texts.values()):
                raise ValueError('Uno de los archivos no se puede leer o supera el límite de 80 KB.')
            parsed={}
            for team in (match.home_team,match.away_team):
                if texts[team.id].strip():
                    parsed[team.id]=parse_xi(texts[team.id],team_name=team.name)
                elif not state['teams'][team.id]['ready']:
                    raise ValueError(f'Falta la alineación completa de {team.name}.')
            # Preview and deliberate second confirmation: do not write before approval.
            st.session_state[f'preview_release473_{match.id}']={
                'home':texts[match.home_team_id], 'away':texts[match.away_team_id]}
        except ValueError as exc:
            st.error(str(exc))
            st.session_state.pop(f'preview_release473_{match.id}',None)
    approval=st.session_state.get(f'preview_release473_{match.id}')
    if approval:
        st.markdown('#### Vista previa · Confirmar publicación')
        with session_scope() as db:
            existing={tid:list(db.scalars(select(Participation).options(joinedload(Participation.player)).where(
                 Participation.match_id==match.id,Participation.team_id==tid,
                 Participation.starter.is_(True))).all()) for tid in (match.home_team_id,match.away_team_id)}
        for team,txt in ((match.home_team,approval['home']),(match.away_team,approval['away'])):
            if txt.strip():
                rows=parse_xi(txt,team_name=team.name)
                display=[{'Dorsal':r.shirt,'Jugador':r.name,'Posición':r.position}
                         for r in rows if r.starter]
            else:
                display=[{'Dorsal':r.shirt_number,'Jugador':r.player.full_name,'Posición':r.position} for r in existing[team.id]]
            st.markdown(f'**{team.name} · 11 titulares**')
            st.dataframe(pd.DataFrame(display),hide_index=True,use_container_width=True)
            with st.expander('Ver distribución por posiciones',expanded=False):
                from ui.lineup473 import lineup_svg
                st.markdown(lineup_svg(display),unsafe_allow_html=True)
        st.caption('Solo después de confirmar el partido quedará disponible para Informadores, Analistas y DD.')
        a,b=st.columns([3,2])
        if a.button('Confirmar y publicar partido',type='primary',key=f'confirm_release473_{match.id}',use_container_width=True):
            try:
                with session_scope() as db:
                    publication.publish_match(db,actor_id=user['id'],match_id=match.id,
                        home_text=approval['home'],away_text=approval['away'])
                st.session_state.pop(f'preview_release473_{match.id}',None)
                st.session_state.pop('contrib_mode47',None)
                st.success('Partido publicado. Ya se pueden valorar los 22 titulares.')
                st.rerun()
            except Exception as exc:st.error(f'No se pudo publicar: {exc}')
        if b.button('Cancelar',key=f'cancel_release473_{match.id}',use_container_width=True):
            st.session_state.pop(f'preview_release473_{match.id}',None)
            st.rerun()


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
    with session_scope() as db:
        released=publication.is_open(db,match.id)
    if not released:
        _prepare_rating_release473(user,match)
        return
    if _can_prepare(user):
        with st.expander('Incorporar un suplente que participó',expanded=False):
            st.caption('Solo se añade el futbolista confirmado. No se modifica ninguno de los 22 titulares.')
            from core.lineup473 import ALLOWED
            with st.form(f'substitute474_{match.id}'):
                team_id=st.selectbox('Equipo',[match.home_team_id,match.away_team_id],
                    format_func=lambda tid:match.home_team.name if tid==match.home_team_id else match.away_team.name)
                name=st.text_input('Nombre del suplente')
                shirt=st.number_input('Dorsal',min_value=1,max_value=99,value=12,step=1)
                position=st.selectbox('Posición observada',sorted(ALLOWED),index=sorted(ALLOWED).index('DC'))
                minute=st.number_input('Minuto de entrada',min_value=0,max_value=130,value=60)
                add=st.form_submit_button('Añadir suplente confirmado')
            if add:
                try:
                    with session_scope() as db:
                        publication.register_substitute(db,actor_id=user['id'],match_id=match.id,
                            team_id=team_id,name=name,shirt=shirt,position=position,minute_in=minute,
                            minute_out=max(90,int(minute)))
                    st.success('Suplente registrado. Ya está disponible para recibir notas.');st.rerun()
                except Exception as exc:st.error(f'No se pudo incorporar el suplente: {exc}')
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
    if working_profile(user)=='own':
        if own_match:
            _mobile_board(user,match,own_id)
        else:
            st.caption('Este encuentro no corresponde a Noname.')
        return
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
            if working_profile(user)=='analyst' or working_profile(user)=='director':
                if st.button('Valorar jugadores',key=f'main_board474_{match.id}',type='primary',use_container_width=True):
                    _open_work(user,match,'board472')
            else:
                _mobile_board(user,match,own_id)
                return
            # Historical complete/post-match narrative remains readable but is
            # no longer offered as a second editor for an individual rating.
        st.markdown('### Información del encuentro')
        a,b=st.columns(2)
        with a:
            st.markdown(f'**{match.home_team.name}**')
            st.caption(f'Estructura de referencia: {match.home_formation if match.home_formation_known and match.home_formation else "Sin confirmar"}')
        with b:
            st.markdown(f'**{match.away_team.name}**')
            st.caption(f'Estructura de referencia: {match.away_formation if match.away_formation_known and match.away_formation else "Sin confirmar"}')
        if False:  # legacy formation editor disabled, evidence remains readable
            with st.expander('Registrar una estructura observada (archivo histórico)',expanded=False):
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
        st.markdown('### Aportaciones disponibles')
        _match_sources(user,match)
        if False:  # former parallel syntheses are available only as historical evidence
            with st.expander('Preparar al próximo rival (archivo histórico)',expanded=False):
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
        elif mode=='board472':
            _mobile_board(user,match,own_id)
            _individual_statistics474(user,match)
        else:
            st.session_state.pop('contrib_mode47',None)
            st.info('Utiliza la valoración individual del partido. Los informes antiguos siguen disponibles en el archivo.')



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
    own_id=_own()
    default_team=match.away_team_id if match.home_team_id==own_id else (match.home_team_id if match.away_team_id==own_id else match.home_team_id)
    teams=[match.home_team_id,match.away_team_id]
    target=st.selectbox('Equipo que estás analizando',teams,
         index=teams.index(default_team),
         format_func=lambda t:match.home_team.name if t==match.home_team_id else match.away_team.name,
         key=f'synth_target472_{match.id}')
    choose=[m for m in all_matches if target in (m.home_team_id,m.away_team_id)]
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
                   match_id=match.id,team_id=target,kind='synthesis',title=f'Síntesis deportiva · {_fixture_label(match)}',
                   data={'equipo_analizado':target,'partidos_revisados':chosen,'conclusion':text},publish=shared)
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
        from repositories.rating_summary474 import observations
        with session_scope() as db:
            own_notes=observations(db,actor_id=user['id'],season_id=sid)
        by_match=defaultdict(list)
        for (pid,mid,author),(when,score,origin) in own_notes.items():
            by_match[mid].append((pid,when,score))
        with session_scope() as db:
            games={m.id:m for m in db.scalars(select(Match).options(
                joinedload(Match.home_team),joinedload(Match.away_team)).where(
                Match.id.in_(by_match.keys()))).unique().all()}
        st.caption('Una fila por encuentro. Las notas siguen siendo privadas; puedes editarlas desde el partido.')
        ids=sorted(by_match,key=lambda x:(games[x].match_date,x) if x in games else (date.min,x),reverse=True)
        if not ids:
            st.info('Todavía no has valorado futbolistas. Abre un partido publicado para empezar.')
        else:
            visible_ids=[mid for mid in ids if mid in games]
            view=pd.DataFrame([{'Partido':_fixture_label(games[mid]),
               'Fecha':f"{games[mid].match_date:%d/%m/%Y}",
               'Futbolistas':len({pid for pid,_,score in by_match[mid]}),
               'Nota media propia':round(sum(score for _,_,score in by_match[mid])/len(by_match[mid]),1)}
               for mid in visible_ids])
            index=_table_select(view,key='my_rating_games474')
            if index is not None and index<len(visible_ids):_go('Partidos',match=visible_ids[index])
        return
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
    if pending:
        if pending in {'Propuestas','Solicitudes'}:
            st.session_state['dd_section47']=pending
        else:
            st.session_state['dd_section47']='Más'
            st.session_state['dd_extra471']=pending
    section=st.selectbox('Qué quieres revisar',['Propuestas','Solicitudes','Más'],key='dd_section47')
    if section=='Más':
        section=st.selectbox('Otras herramientas',['Aportaciones compartidas','Modelo y necesidades','Actividad'],
                             key='dd_extra471')
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
        selected=st.selectbox('Estado de propuesta',['Pendientes','Guardadas','Seguimiento','Descartadas','Todas'],key='proposal_filter47')
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
                    decision=st.selectbox('Qué quieres hacer',[
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
    with session_scope() as db:
        teams=list(db.scalars(select(Team).where(Team.active.is_(True),
                     Team.is_test.is_(False)).order_by(Team.name)).all())
    team_names={t.id:t.name for t in teams}
    with st.expander('Filtrar por equipo o posición',expanded=False):
        team_filter=st.selectbox('Equipo',[None]+list(team_names),
          format_func=lambda tid:team_names.get(tid,'Todos los equipos'),key='catalog_team47')
        pos_filter=st.selectbox('Posición',['Todas','POR','LD','LI','DCI','DCD','DFC','MC','MCO','ED','EI','DC'],
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
        count=25
        maximum=max(1,(total+count-1)//count)
        # A changing filter resets the page without mutating a live widget key.
        signature=f'{search}|{team_filter}|{pos_filter}|{count}'
        if st.session_state.get('catalog_signature47')!=signature:
            st.session_state['catalog_signature47']=signature
            st.session_state['catalog_page_input47']=1
        page=st.selectbox('Página',range(1,maximum+1),key='catalog_page_input47') if maximum>1 else 1
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
                  player_id=player_id,limit=250) if sid else []
        from repositories.rating_summary474 import observations, summary_for
        totals=summary_for(observations(db,actor_id=user['id'],season_id=sid,
                                        player_ids=[player_id]),player_id) if sid else None
        legacy=[]
        if can_direct(user) or can_admin(user) or can_report(user):
            stmt=select(PlayerEvaluation,Report).options(joinedload(Report.match)).join(Report,Report.id==PlayerEvaluation.report_id).where(
                    PlayerEvaluation.player_id==player_id,Report.status.in_(FINAL_REPORT_STATUSES))
            if not (can_direct(user) or can_admin(user)):
                stmt=stmt.where(Report.reporter_id==user['id'])
            legacy=list(db.execute(stmt.order_by(Report.submitted_at.desc())).all())
        opinions_stmt=select(MatchOpinionPlayer,MatchOpinion).join(
            MatchOpinion,MatchOpinion.id==MatchOpinionPlayer.opinion_id).where(
            MatchOpinionPlayer.player_id==player_id)
        if not (can_direct(user) or can_admin(user)):
            opinions_stmt=opinions_stmt.where(MatchOpinion.user_id==user['id'])
        neutral_notes=list(db.execute(opinions_stmt).all())
        decision=db.scalar(select(PlayerSeasonDecision).where(PlayerSeasonDecision.player_id==player_id,
                PlayerSeasonDecision.season_id==sid)) if sid and can_direct(user) else None
    page_header(p.display_name or p.full_name,'Ficha deportiva · evidencia identificada y muestra disponible')
    st.caption(' · '.join([p.primary_position or 'Posición desconocida',
                          ', '.join(r.team.name for r in rosters) if rosters else 'Equipo no confirmado']))
    totals=totals or {'matches':0,'opinions':0,'average':None,'trend':'—','history':[]}
    c1,c2,c3=st.columns(3)
    c1.metric('Partidos evaluados',totals['matches'])
    c2.metric('Nota · fuentes visibles',
        f"{totals['average']:.1f}" if totals['average'] is not None else 'Sin muestra')
    c3.metric('Opiniones con nota',totals['opinions'])
    if totals['history']:
        st.caption('Evolución: '+totals['trend']+' · '+str(len(totals['history']))+' encuentros distintos.')
    if decision: st.caption(f'Decisión DD actual: {decision.status} · Prioridad {decision.priority}')
    st.markdown('### Evidencia disponible')
    if not contributions and not legacy and not neutral_notes:
        st.info('Todavía no existen valoraciones accesibles con tu perfil. No se interpreta como un 0.')
    for row in contributions:
        with st.expander(f'{row.updated_at:%d/%m} · {row.title}'):
            try: details=json.loads(row.data_json or '{}')
            except (TypeError,ValueError):details={}
            if details.get('source')=='metrics474':
                stats=details.get('estadisticas') or {}
                st.write(f"Pases: **{stats.get('pases_correctos','—')}/{stats.get('pases_intentados','—')}** · "
                         f"Duelos: **{stats.get('duelos_ganados','—')}/{stats.get('duelos_disputados','—')}**")
                st.caption('Fuente: '+str(details.get('procedencia') or 'No especificada'))
            else:_show_contribution(row,user['id'])
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
    from repositories.rating_summary474 import observations,summary_for
    with session_scope() as db:
        roster=list(db.scalars(select(TeamRoster).options(joinedload(TeamRoster.player)).where(
             TeamRoster.team_id==own_id,TeamRoster.season_id==sid,TeamRoster.active.is_(True))
             .order_by(TeamRoster.shirt_number)).unique().all())
        grade_map=observations(db,actor_id=user['id'],season_id=sid,
                               player_ids=[r.player_id for r in roster])
    records=[]
    for r in roster:
        item=summary_for(grade_map,r.player_id)
        records.append({'Jugador':r.player.display_name or r.player.full_name,
            'Pos.':r.usual_position or r.player.primary_position or '—',
            'PJ evaluados':item['matches'],'Opiniones':item['opinions'],
            'Media':f"{item['average']:.1f}" if item['average'] is not None else '—',
            'Tendencia':item['trend']})
    if not records: st.info('No hay plantilla propia documentada. No se inventa un once.');return
    idx=_table_select(pd.DataFrame(records),key=f'squad47_{st.session_state.get("selection_epoch47",0)}')
    if idx is not None: _go('Jugadores',player=roster[idx].player_id)
    with st.expander('Exportar resumen para DD',expanded=False):
        st.download_button('Descargar tabla CSV',data=pd.DataFrame(records).to_csv(index=False,sep=';').encode('utf-8-sig'),
                           file_name='noname_plantilla_evaluaciones.csv',mime='text/csv')
    st.caption('Tendencia solo con 4+ partidos distintos; es un indicio, no una recomendación automática. Las medias muestran fuente y muestra al entrar al jugador.')
    by_pos=defaultdict(int)
    for rec in records: by_pos[rec['Pos.']]+=1
    st.caption('Cobertura registrada: '+', '.join(f'{pos} {n}' for pos,n in sorted(by_pos.items())))


def _admin_players471(user):
    """Clear entry point to correct or remove a player without hidden submenus."""
    from repositories import permanent_deletion as purge
    st.markdown('### Corregir o eliminar un jugador')
    search=st.text_input('Buscar por nombre',key='admin_player_search471',
                         placeholder='Escribe un nombre o apellido...')
    if not search.strip():
        st.caption('Escribe parte del nombre para encontrar la ficha que quieres corregir o borrar.')
        return
    with session_scope() as db:
        found=list(db.scalars(select(Player).where(
            or_(Player.full_name.ilike(f'%{search.strip()}%'),
                Player.display_name.ilike(f'%{search.strip()}%')))
            .order_by(Player.full_name).limit(60)).all())
    if not found:
        st.info('No hay jugadores con ese nombre.');return
    from ui.mobile472 import player_list_component
    names={p.id:f'{p.full_name} · ID {p.id}' for p in found}
    previous=st.session_state.get('admin_selected_player472')
    pid=previous if previous in names else found[0].id
    selection=player_list_component(key='admin_player_list472',
        data={'items':[{'id':p.id,'name':p.full_name,
                        'detail':p.primary_position or 'Posición sin especificar'} for p in found],
              'selected':pid})
    if selection.select is not None and selection.select in names and selection.select != pid:
        st.session_state['admin_selected_player472']=int(selection.select)
        st.rerun()
    item=next(p for p in found if p.id==pid)
    st.markdown('**Ficha seleccionada**')
    with st.form(f'admin_player_edit471_{pid}'):
        new_name=st.text_input('Nombre correcto',value=item.full_name)
        position=st.text_input('Posición (opcional)',value=item.primary_position or '')
        update=st.form_submit_button('Guardar corrección',type='primary',use_container_width=True)
    if update:
        try:
            if not new_name.strip():raise ValueError('El nombre no puede quedar vacío.')
            with session_scope() as db:
                players_repo.update_player(db,pid,user['id'],full_name=new_name.strip(),
                      primary_position=position.strip() or None)
            st.success('Jugador corregido. Su histórico se conserva.')
            st.rerun()
        except Exception as exc:st.error(f'No se ha actualizado el jugador: {exc}')
    with st.expander('Eliminar este jugador definitivamente',expanded=False):
        st.warning('Si tiene informes o valoraciones, también pueden verse afectados. Comprueba el impacto antes de borrar.')
        if st.button('Ver qué se eliminaría',key=f'admin_player_preview471_{pid}',use_container_width=True):
            try:
                with session_scope() as db:
                    plan=purge.build_plan(db,{'jugadores':[pid]},user['id'])
                st.session_state['admin_player_delete_preview471']={'id':pid,'fingerprint':plan.fingerprint}
            except Exception as exc:st.error(str(exc))
        preview=st.session_state.get('admin_player_delete_preview471')
        if preview and preview['id']==pid:
            try:
                with session_scope() as db:
                    plan=purge.build_plan(db,{'jugadores':[pid]},user['id'])
                if plan.fingerprint!=preview['fingerprint']:
                    st.warning('Los datos han cambiado. Revisa de nuevo el impacto.')
                    st.session_state.pop('admin_player_delete_preview471',None)
                    return
                st.write(f'**Se eliminarían {plan.total} registros de la base de datos.**')
                for name,ids in plan.rows.items():
                    st.caption(f'{purge.LABELS.get(name,name)}: {len(ids)}')
                for (table,col),ids in plan.detach.items():
                    st.caption(f'Se desvincularían {len(ids)} referencias de {table}.{col}')
                if plan.external_files:
                    st.error('Hay archivos externos vinculados: el borrado de la base no elimina sus bytes. Revisa las rutas y la copia.')
                backup=st.checkbox('Tengo una copia de seguridad recuperable',key=f'admin_player_backup471_{pid}')
                word=st.text_input('Para eliminar, escribe BORRAR',key=f'admin_player_confirm471_{pid}')
                if st.button('Eliminar jugador definitivamente',key=f'admin_player_delete471_{pid}',
                             disabled=not (backup and word=='BORRAR'),use_container_width=True):
                    with session_scope() as db:
                        purge.execute_plan(db,{'jugadores':[pid]},user['id'],plan.fingerprint)
                    st.session_state.pop('admin_player_delete_preview471',None)
                    st.success('Jugador eliminado. Se ha registrado la operación en auditoría.')
                    st.rerun()
            except Exception as exc:st.error(f'No se ha borrado nada: {exc}')


def admin(user):
    if not can_admin(user): st.error('Acceso reservado a Administración.');return
    page_header('Administración técnica','Mantenimiento ocasional. Horarios y valoraciones voluntarias no generan incidencias.')
    sid=_season();oid=_own()
    if sid and oid:
        fixtures=_fixtures(sid,own_id=oid,count=100)
        last,_=current_fixtures(fixtures,local_today())
        if last:
            with session_scope() as db:
                open_for_rating=publication.is_open(db,last.id)
            if not open_for_rating:
                with st.container(border=True):
                    st.markdown(f'**Abrir valoraciones · {_fixture_label(last)}**')
                    st.caption('Importa los once titulares de cada equipo y publica una sola vez.')
                    if st.button('Preparar y publicar partido',type='primary',key=f'admin_start473_{last.id}',use_container_width=True):
                        _go('Partidos',match=last.id)
    section=st.selectbox('Sección',['Jugadores','Incidencias','Usuarios y permisos','Datos deportivos','Mantenimiento'],key='admin_section47')
    if section=='Jugadores':
        _admin_players471(user)
    elif section=='Incidencias':
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
