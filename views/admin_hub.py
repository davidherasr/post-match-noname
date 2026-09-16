from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from core.navigation import request_navigation

from core.database import session_scope
from core.permissions import can_admin
from repositories import data_quality as quality_repo
from repositories import players as players_repo
from repositories import scouting as repo
from repositories import workspaces
from repositories import calendar as calendar_repo
from ui.styles import page_header



def _real_data_status(user: dict) -> None:
    st.markdown("### Estado operativo de la temporada")
    with session_scope() as session:
        data = workspaces.load_operational_readiness(session)
    season = data.get("active_season")
    own = data.get("own_team")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temporada", season.name if season else "—")
    c2.metric("Partidos", data.get("fixture_count", 0))
    c3.metric("Jornadas", data.get("round_count", 0))
    c4.metric("Plantilla No Name", data.get("own_roster_count", 0))
    match = data.get("today_match") or data.get("next_match")
    if match:
        label = "Partido de hoy" if data.get("today_match") else "Próximo partido"
        with st.container(border=True):
            a, b = st.columns([5, 1])
            a.markdown(f"**{label} · {match.round_name} · {match.home_team.name} - {match.away_team.name}**")
            a.caption(calendar_repo.schedule_label(match))
            if b.button("Abrir", type="primary", use_container_width=True, key=f"admin_ready_match39_{match.id}"):
                st.session_state["workspace_match_id"] = match.id
                request_navigation("Jornada")
                st.rerun()
    for warning in data.get("warnings") or []:
        st.warning(warning)
    if not data.get("warnings"):
        st.success("Temporada, calendario y plantilla están disponibles para trabajar con datos reales.")

def _data_search(user: dict) -> None:
    st.markdown("### Buscar datos")
    with st.form("admin_data_search39"):
        query=st.text_input("Buscar jugador o equipo",placeholder="Nombre")
        submit=st.form_submit_button("Buscar",type="primary",use_container_width=True)
    if submit and len(query.strip())>=2:
        with session_scope() as session:
            result=repo.global_catalog_search(session,query.strip())
        for p in result.get("players",[]):
            with st.container(border=True):
                a,b=st.columns([5,1]); a.markdown(f"**{p.full_name}** · {p.primary_position or '-'}"); 
                if b.button("Abrir",key=f"admin_data_player38_{p.id}",use_container_width=True):
                    st.session_state["workspace_player_id"]=p.id; request_navigation("Jugadores"); st.rerun()
        for t in result.get("teams",[]):
            with st.container(border=True):
                st.markdown(f"**{t.name}**"); 
        if not result.get("players") and not result.get("teams"):
            st.info("Sin coincidencias.")


def _issue_player_ids(issue: dict) -> list[int]:
    return [int(x) for x in re.findall(r"\b(\d+)\s*·",str(issue.get("detail") or ""))]


def _quality(user: dict) -> None:
    st.markdown("### Calidad de datos")
    with session_scope() as session:
        issues=quality_repo.quality_issues(session)
    if not issues:
        st.success("No se han detectado incidencias."); return
    for idx,issue in enumerate(issues[:40]):
        with st.container(border=True):
            a,b=st.columns([5,1])
            a.markdown(f"**{issue['type']}** · {issue['severity']}")
            a.caption(issue["detail"])
            if b.button("Revisar",key=f"quality39_{idx}",use_container_width=True):
                st.session_state["quality_issue39"]=idx
    selected=st.session_state.get("quality_issue39")
    if selected is None or selected>=len(issues): return
    issue=issues[selected]
    st.divider(); st.markdown(f"### Revisar · {issue['type']}")
    ids=_issue_player_ids(issue)
    if issue["type"]=="Posible duplicado" and len(ids)>=2:
        with session_scope() as session:
            players=[session.get(__import__('models.entities',fromlist=['Player']).Player,pid) for pid in ids]
        players=[p for p in players if p]
        st.dataframe(pd.DataFrame([{"Jugador":p.full_name,"POS":p.primary_position,"Nacimiento":p.date_of_birth} for p in players]),hide_index=True,use_container_width=True)
        if len(players)>=2:
            with st.form(f"merge_issue39_{selected}"):
                target=st.selectbox("Conservar",[p.id for p in players],format_func=lambda pid:next(p.full_name for p in players if p.id==pid))
                source=st.selectbox("Fusionar en el anterior",[p.id for p in players],index=1 if len(players)>1 else 0,format_func=lambda pid:next(p.full_name for p in players if p.id==pid))
                merge=st.form_submit_button("Fusionar jugadores",type="primary",use_container_width=True)
            if merge:
                if source==target: st.error("Origen y destino deben ser distintos.")
                else:
                    with session_scope() as session: players_repo.merge_players(session,source,target,user["id"])
                    st.success("Jugadores fusionados."); st.session_state.pop("quality_issue39",None); st.rerun()
    elif ids:
        pid=ids[0]
        with session_scope() as session:
            player=session.get(__import__('models.entities',fromlist=['Player']).Player,pid)
        if player:
            with st.form(f"fix_player39_{pid}"):
                name=st.text_input("Nombre",value=player.full_name)
                pos=st.text_input("Posición",value=player.primary_position or "")
                save=st.form_submit_button("Guardar",type="primary",use_container_width=True)
            if save:
                with session_scope() as session: players_repo.update_player(session,pid,user["id"],full_name=name.strip(),primary_position=pos.strip() or None)
                st.success("Registro actualizado."); st.rerun()


def _technical(user: dict) -> None:
    from views import admin as legacy
    with st.expander("Herramientas técnicas",expanded=False):
        tool=st.selectbox("Herramienta",["Seguridad","Almacenamiento","Auditoría","Backup","Rendimiento"],key="admin_tech39")
        if tool=="Seguridad": legacy._section_security(user)
        elif tool=="Almacenamiento": legacy._section_storage(user)
        elif tool=="Auditoría": legacy._section_audit(user)
        elif tool=="Backup": legacy._section_backup(user)
        elif tool=="Rendimiento": legacy._section_performance(user)



def _report_corrections_423(user: dict) -> None:
    """Exceptional correction, not a DD approval queue."""
    st.markdown('#### Reabrir informe por corrección')
    st.caption('Solo Administración; requiere motivo y conserva la versión entregada. Hasta volver a entregar, la revisión en curso no participa en las estadísticas oficiales.')
    with session_scope() as session:
        from repositories import reports as report_repo
        candidates = [item for item in report_repo.list_reports(session, limit=200)
                      if item.status in {'incorporated', 'approved', 'final', 'submitted'}]
    if not candidates:
        st.info('No hay informes entregados que necesiten corrección.'); return
    labels = {item.id: f'{item.match.match_date} · {item.match.home_team.name} – {item.match.away_team.name} · {item.reporter.full_name} · Versión {item.version} ({item.status})'
              for item in candidates}
    report_id = st.selectbox('Informe que debe corregirse', list(labels), format_func=lambda item_id: labels[item_id], key='admin_report_reopen_423')
    reason = st.text_area('Motivo de corrección obligatorio', key='admin_report_reopen_reason_423', placeholder='Qué debe revisar el Informador y por qué...')
    confirm = st.checkbox('Confirmo que quiero reabrir el informe seleccionado y conservar su versión anterior.', key=f'admin_report_confirm_{report_id}_423')
    if st.button('Reabrir para corrección', type='primary', key='admin_report_reopen_submit_423',
                 disabled=not (confirm and reason.strip()), use_container_width=True):
        try:
            with session_scope() as session:
                from repositories import reports as report_repo
                report_repo.reopen_report(session, report_id, user['id'], reason.strip())
            st.success('Informe reabierto y auditado. Volverá a las tareas del Informador; la versión entregada permanece en el histórico.'); st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render(user: dict) -> None:
    if not can_admin(user):
        st.error("No tienes permiso de administración."); return
    page_header("Administración","Usuarios, roles, calendario y datos. Las decisiones deportivas se realizan desde Dirección Deportiva.")
    pending_section = st.session_state.pop('admin_section_423', None)
    if pending_section in {'Usuarios', 'Club', 'Datos', 'Configuración', 'Mantenimiento avanzado'}:
        st.session_state['admin_section_current_423'] = pending_section
    section=st.selectbox("Sección",["Usuarios","Club","Datos","Configuración","Mantenimiento avanzado"],key="admin_section_current_423")
    from views import admin as legacy_admin
    from views import catalog as legacy_catalog
    if section=="Usuarios": legacy_admin._section_users(user)
    elif section=="Club":
        from views import data_governance
        data_governance.render(user)
        with st.expander("Identidad visual y documentos", expanded=False):
            legacy_admin._section_brand(user)
    elif section=="Datos":
        _real_data_status(user)
        _data_search(user)
        _quality(user)
    elif section == "Mantenimiento avanzado":
        st.warning("Estas operaciones pueden afectar al histórico. Comprueba las dependencias y dispone de una copia restaurable antes de borrar registros.")
        with st.expander('Corrección excepcional de informes incorporados', expanded=False):
            _report_corrections_423(user)
        with st.expander("Eliminación definitiva de datos", expanded=False):
            from views import permanent_deletion
            permanent_deletion.render(user)
        _technical(user)
    else:
        config=st.radio("Configurar",["Temporadas","Competiciones","Equipos","Plantillas"],horizontal=True,key="admin_config38")
        if config=="Temporadas": legacy_catalog._section_seasons(user)
        elif config=="Competiciones": legacy_catalog._section_competitions(user)
        elif config=="Equipos": legacy_catalog._section_teams(user)
        else: legacy_catalog._section_rosters(user)
