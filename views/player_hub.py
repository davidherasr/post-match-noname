from __future__ import annotations

import streamlit as st

from core.constants import POSITIONS
from core.database import session_scope
from core.permissions import can_direct
from core.presentation import PLAYER_STATES
from repositories import planning as planning_repo
from repositories import players as players_repo
from repositories import scouting as base_repo
from repositories import workspaces
from repositories import player_catalog as catalog_repo
from reports.player_report_pdf import generate_player_360_pdf, generate_player_executive_pdf, player_report_filename
from ui import player_report as player_ui
from ui.styles import page_header

FILTERS = ["Todos", "Destacados", "Seguimiento", "Con observaciones", "Prioritarios", "Descartados"]


def _open_player(player_id: int) -> None:
    st.session_state["workspace_player_id"] = int(player_id)
    st.rerun()


def _decision_editor(user: dict, payload: dict) -> None:
    if not can_direct(user) or not payload.get("season_id"):
        return
    player = payload["player"]
    existing = payload.get("decision")
    with session_scope() as session:
        roles = planning_repo.list_model_roles(session)
    st.markdown("### Decisión y encaje")
    role_ids = [None] + [r.id for r in roles]
    current_role = existing.model_role_id if existing else None
    role_index = role_ids.index(current_role) if current_role in role_ids else 0
    role_id = st.selectbox(
        "Rol del Modelo No Name", role_ids, index=role_index,
        format_func=lambda rid: "Sin rol" if rid is None else next(f"{r.position} · {r.name}" for r in roles if r.id == rid),
        key=f"dd_role38_{player.id}",
    )
    with session_scope() as session:
        criteria = planning_repo.list_model_criteria(session, role_id) if role_id else []
    with st.form(f"dd_decision38_{player.id}_{role_id}"):
        c1,c2=st.columns(2)
        states=["Sin decisión"]+PLAYER_STATES
        state=c1.selectbox("Estado",states,index=states.index(existing.status) if existing and existing.status in states else 0)
        priority=c2.selectbox("Prioridad",[1,2,3],index=(existing.priority-1) if existing and existing.priority in {1,2,3} else 1,format_func=lambda x:{1:"Alta",2:"Media",3:"Baja"}[x])
        scores={}
        existing_scores={row["id"]:row.get("score") for row in payload.get("criteria",[]) if row.get("score") is not None}
        if criteria:
            st.markdown("**Criterios del rol**")
            for criterion in criteria:
                scores[criterion.id]=st.number_input(
                    f"{criterion.name} · peso {criterion.weight}",0.0,10.0,float(existing_scores.get(criterion.id) or 0),.5,
                    key=f"ddcrit38_{player.id}_{criterion.id}",
                )
        c3,c4,c5=st.columns(3)
        fit=c3.number_input("Encaje",0.0,10.0,float(existing.fit_score if existing and existing.fit_score is not None else 0),.5)
        current=c4.number_input("Nivel actual",0.0,10.0,float(existing.current_level if existing and existing.current_level is not None else 0),.5)
        potential=c5.number_input("Proyección",0.0,10.0,float(existing.potential_score if existing and existing.potential_score is not None else 0),.5)
        note=st.text_area("Conclusión DD",value=existing.director_note if existing and existing.director_note else "",height=90)
        save=st.form_submit_button("Guardar decisión",type="primary",use_container_width=True)
    if save:
        clean={cid:value for cid,value in scores.items() if value and value>0}
        with session_scope() as session:
            weighted=planning_repo.weighted_model_fit(planning_repo.list_model_criteria(session,role_id),clean) if role_id and clean else None
            planning_repo.upsert_season_decision(
                session,user["id"],season_id=payload["season_id"],player_id=player.id,status=state,priority=priority,
                model_role_id=role_id,director_note=note,fit_score=weighted if weighted is not None else (fit if fit>0 else None),
                current_level=current if current>0 else None,potential_score=potential if potential>0 else None,criteria_scores=clean,
            )
        st.success("Decisión actualizada.")
        st.rerun()


def _export(payload: dict) -> None:
    player=payload["player"]
    with st.expander("Exportar"):
        with session_scope() as session:
            settings=base_repo.get_all_settings(session)
        c1,c2=st.columns(2)
        if c1.button("Preparar ficha breve",use_container_width=True,key=f"export_exec38_{player.id}"):
            st.session_state[f"exec38_{player.id}"]=generate_player_executive_pdf(payload,settings)
        if c2.button("Preparar dossier completo",use_container_width=True,key=f"export_dossier38_{player.id}"):
            st.session_state[f"dossier38_{player.id}"]=generate_player_360_pdf(payload,settings)
        if st.session_state.get(f"exec38_{player.id}"):
            st.download_button("Descargar ficha breve",st.session_state[f"exec38_{player.id}"],player_report_filename(payload,"executive"),"application/pdf",use_container_width=True,key=f"download_exec38_{player.id}")
        if st.session_state.get(f"dossier38_{player.id}"):
            st.download_button("Descargar dossier completo",st.session_state[f"dossier38_{player.id}"],player_report_filename(payload,"360"),"application/pdf",use_container_width=True,key=f"download_dossier38_{player.id}")


def _render_player(user: dict, player_id: int) -> None:
    if st.button("← Volver a jugadores",key=f"back_player38_{player_id}"):
        st.session_state.pop("workspace_player_id",None); st.rerun()
    with session_scope() as session:
        active=players_repo.get_active_season(session)
        requested_season = st.session_state.get('catalog_season_423')
        payload=workspaces.load_player_workspace(session,player_id=player_id,season_id=requested_season if requested_season else (active.id if active else None))
        pending_question = None
        if payload.get('season_id') and can_direct(user):
            from repositories import observation_requests as requests_repo
            pending = requests_repo.list_requests(session,season_id=payload['season_id'],active_only=True)
            pending_question = next((r.question for r in pending if r.player_id == player_id),None)
    player_ui.render_vertical_profile(payload,next_action={'question':pending_question} if pending_question else None)
    if can_direct(user) and not payload.get("is_own_player") and payload.get("season_id"):
        with st.expander("Pedir opinión al cuerpo técnico", expanded=False):
            from views.observation_requests import composer
            composer(user, payload["season_id"], selected_player_id=payload["player"].id,
                     key_prefix=f"dd_player_{player_id}")
    if can_direct(user):
        with st.expander('Registrar o modificar decisión deportiva', expanded=False):
            _decision_editor(user,payload)
    sections = ['Rendimiento', 'Evidencias', 'Modelo No Name', 'Comparación', 'Datos', 'Documentos']
    section = st.pills('Consultar la ficha', sections, selection_mode='single',
        key=f'player_profile_section_444_{player_id}') or sections[0]
    if section == 'Rendimiento':
        player_ui.render_monthly_profile(payload)
        player_ui.render_season_profile(payload)
    elif section == 'Evidencias':
        player_ui.render_evolution(payload)
        player_ui.render_observations(payload)
    elif section == 'Modelo No Name':
        player_ui.render_model(payload)
    elif section == 'Comparación':
        player_ui.render_comparison(payload)
    elif section == 'Datos':
        player_ui.render_data(payload)
    else:
        _export(payload)


def _compare_players(ids: list[int], season_id: int | None = None) -> None:
    if len(ids)!=2:
        return
    with session_scope() as session:
        payloads=[workspaces.load_player_workspace(session,player_id=pid,season_id=season_id) for pid in ids]
    st.markdown("### Comparación")
    cols=st.columns(2)
    for col,payload in zip(cols,payloads):
        with col:
            p=payload["player"]
            st.markdown(f"**{p.display_name or p.full_name}**")
            st.metric("Rendimiento",payload["postmatch"]["average"] or "-")
            st.metric("Encaje",payload.get("fit_score") or "-")
            confidence = payload['postmatch']['confidence']
            st.metric("Confianza",f"{confidence['score']}/100" if confidence['sample'] else "No evaluable")
            st.caption(f"Estado: {payload['decision'].status if payload.get('decision') else 'Sin decisión'}")


def _reset_catalog_filters() -> None:
    # This callback runs before Streamlit instantiates the widgets again.
    for key in ('catalog_search_423','catalog_season_423','catalog_team_423',
                'catalog_position_423','catalog_scope_423','catalog_state_423',
                'catalog_evidence_423','catalog_order_423'):
        st.session_state.pop(key, None)
    st.session_state['catalog_page_423'] = 1


def render(user: dict) -> None:
    opened = st.session_state.get('workspace_player_id')
    if opened:
        _render_player(user, int(opened))
        return
    page_header('Jugadores', 'Consulta la plantilla, las señales y los informes sin confundir sus niveles de evidencia.')
    with session_scope() as session:
        seasons = players_repo.list_seasons(session)
        active = players_repo.get_active_season(session)
    season_ids = [None] + [s.id for s in seasons]
    season_labels = {None: 'Todas las temporadas', **{s.id:s.name for s in seasons}}
    if 'catalog_season_423' not in st.session_state:
        st.session_state['catalog_season_423'] = active.id if active else None
    if st.session_state['catalog_season_423'] not in season_ids:
        st.session_state['catalog_season_423'] = None
    with st.container(border=True):
        st.markdown('#### Buscar y filtrar')
        search = st.text_input('Buscar jugador', placeholder='Nombre o apellido...', key='catalog_search_423')
        season_id = st.selectbox('Temporada', season_ids, format_func=lambda sid: season_labels[sid], key='catalog_season_423')
        with session_scope() as session:
            teams = catalog_repo.teams_for_filter(session, season_id)
        team_labels = {None:'Todos los equipos', 'Sin equipo':'Sin equipo confirmado',
                       **{t.id:t.name for t in teams}}
        team_options = list(team_labels)
        if st.session_state.get('catalog_team_423') not in team_options:
            st.session_state['catalog_team_423'] = None
        a,b = st.columns(2)
        team_id = a.selectbox('Equipo', team_options, format_func=lambda key:team_labels[key], key='catalog_team_423')
        position = b.selectbox('Posición', ['Todas'] + POSITIONS, key='catalog_position_423')
        a,b = st.columns(2)
        scope = a.selectbox('Ámbito', ['Todos','Propios','Externos'], key='catalog_scope_423')
        state_options = ['Todos','Sin decisión','Observado','Interesante','Seguimiento','Prioritario','Descartado','Destacados','Con observaciones']
        state = b.selectbox('Estado deportivo', state_options, key='catalog_state_423')
        with st.expander('Más filtros y ordenación', expanded=False):
            evidence = st.selectbox('Información disponible',
                ['Cualquiera','Postpartidos','Señales neutrales','Seguimiento formal','Sin valoraciones'],
                key='catalog_evidence_423', help='No mezcla menciones con observaciones profundas.')
            order = st.selectbox('Ordenar', ['Nombre','Posición','Partidos evaluados','Última evaluación'], key='catalog_order_423')
        st.button('Limpiar filtros', on_click=_reset_catalog_filters, key='catalog_reset_423')
    if not can_direct(user):
        st.caption('Las decisiones deportivas y la gestión de seguimientos requieren los permisos correspondientes.')
    # Any changed search/filter/order begins at page 1; do not silently leave
    # the user on an unrelated last page from a previous filter.
    signature = (search, season_id, team_id, position, scope, state, evidence, order)
    previous_signature = st.session_state.get('catalog_filter_signature_423')
    if previous_signature is not None and previous_signature != signature:
        st.session_state['catalog_page_423'] = 1
    st.session_state['catalog_filter_signature_423'] = signature
    page = st.session_state.get('catalog_page_423', 1)
    with session_scope() as session:
        data = catalog_repo.search_players(session, season_id=season_id, search=search,
            position=None if position == 'Todas' else position, team_id=team_id,
            scope=scope, state_filter=state, evidence=evidence, order=order,
            page=page, page_size=catalog_repo.PAGE_SIZE)
    rows = data['rows']
    if page != data['page']:
        st.session_state['catalog_page_423'] = data['page']
    total = data['total']
    st.markdown(f'**{total} jugador(es)** · Página {data["page"]} de {data["pages"]}')
    st.caption('Las medias consideran solo informes oficiales de partidos reales. Una señal neutral no cuenta como informe ni como seguimiento formal.')
    if not rows:
        st.info('No hay jugadores para esta combinación. Revisa equipo, temporada y estado, o limpia los filtros.')
    else:
        with st.expander('Comparar dos jugadores', expanded=False):
            names = st.session_state.setdefault('catalog_compare_names_423', {})
            for item in rows:
                player = item['player']
                names[int(player.id)] = player.display_name or player.full_name
            current_selected = st.session_state.get('catalog_compare_423') or []
            available = list(dict.fromkeys([*current_selected, *[int(x['player'].id) for x in rows]]))
            selected = st.multiselect('Jugadores', available, max_selections=2,
                format_func=lambda pid:names.get(pid, 'Jugador no disponible'),key='catalog_compare_423')
            if len(selected) == 2:
                _compare_players(selected, season_id)
            else:
                st.caption('Elige dos jugadores del catálogo; la selección se conserva al cambiar de filtro.')
        for item in rows:
            p = item['player']
            team = item['team'].name if item['team'] else 'Equipo no confirmado'
            own_player = item['scope'] == 'Propio'
            with st.container(border=True):
                st.markdown(f'**{p.display_name or p.full_name}** · {p.primary_position or "Posición sin registrar"}')
                status_text = item['state'] if item.get('decision') else 'Sin decisión deportiva'
                st.caption(f'{team} · {"Plantilla propia" if own_player else "Futbolista externo"} · {status_text}' +
                           (f' · Prioridad {item["priority"]}' if item.get('priority') else ''))
                avg = f'{item["rating"]:.1f}/10' if item['rating'] is not None else 'Sin calificación'
                a,b,c = st.columns(3)
                a.metric('Rendimiento propio' if own_player else 'Rendimiento rival', avg)
                b.metric('Partidos evaluados', item['match_count'])
                c.metric('Informadores', item['authors'])
                if not own_player:
                    st.caption(f'Señales neutrales: {item["neutral_mentions"]} · Partidos señalados: {item["neutral_matches"]} · Autores: {item["neutral_authors"]}')
                    st.caption(f'Seguimiento formal: {item["tracking_count"]} observaciones')
                else:
                    st.caption('Evolución del equipo propio; las señales externas no se confunden con el rendimiento de la plantilla.')
                if st.button('Abrir ficha', type='secondary', use_container_width=True, key=f'catalog_open_{p.id}'):
                    _open_player(p.id)
    if data['pages'] > 1:
        prev, middle, nxt = st.columns([1,2,1])
        if prev.button('← Anterior', disabled=data['page'] == 1, use_container_width=True):
            st.session_state['catalog_page_423'] = data['page'] - 1; st.rerun()
        middle.caption(f'{data["page"]}/{data["pages"]} · {catalog_repo.PAGE_SIZE} por página')
        if nxt.button('Siguiente →', disabled=data['page'] == data['pages'], use_container_width=True):
            st.session_state['catalog_page_423'] = data['page'] + 1; st.rerun()
