from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from core.constants import NEED_LEVELS, POSITIONS
from core.database import session_scope
from repositories import advanced_scouting as scout_repo
from repositories import planning as planning_repo
from repositories import scouting as repo
from repositories import players as players_repo
from ui.styles import page_header


def _roles(user: dict) -> None:
    with session_scope() as session:
        roles = planning_repo.list_model_roles(session, active_only=False)
    st.markdown("### Roles de nuestro modelo")
    st.caption("Define para qué queremos a un futbolista, no solo dónde juega.")
    if roles:
        st.dataframe(pd.DataFrame([{"ID":r.id,"Posición":r.position,"Rol":r.name,"Descripción":r.description,"Activo":r.active} for r in roles]), hide_index=True, use_container_width=True)
    with st.form("new_model_role"):
        a,b = st.columns(2)
        pos = a.selectbox("Posición", POSITIONS)
        name = b.text_input("Nombre del rol", placeholder="MCD Base")
        description = st.text_area("Qué esperamos de este rol", height=80)
        save = st.form_submit_button("Crear rol", type="primary")
    if save and name.strip():
        try:
            with session_scope() as session:
                planning_repo.create_model_role(session, user["id"], name=name, position=pos, description=description)
            st.success("Rol añadido al Modelo No Name."); st.rerun()
        except Exception as exc: st.error(str(exc))
    if roles:
        role_id = st.selectbox("Editar criterios del rol", [r.id for r in roles], format_func=lambda rid: next(f"{r.position} · {r.name}" for r in roles if r.id==rid))
        with session_scope() as session:
            criteria = planning_repo.list_model_criteria(session, role_id)
        if criteria:
            st.dataframe(pd.DataFrame([{"Criterio":c.name,"Categoría":c.category,"Peso":c.weight,"Descripción":c.description} for c in criteria]), hide_index=True, use_container_width=True)
        with st.form(f"criterion_{role_id}"):
            a,b,c = st.columns([2,1,1])
            crit_name = a.text_input("Criterio", placeholder="Defensa de espacios")
            category = b.selectbox("Bloque", ["Técnico","Táctico","Físico","Mental"])
            weight = c.selectbox("Peso", [1,2,3,4,5], index=2)
            desc = st.text_input("Definición / qué observar")
            add = st.form_submit_button("Añadir criterio")
        if add and crit_name.strip():
            with session_scope() as session:
                planning_repo.add_model_criterion(session, user["id"], role_id, name=crit_name, category=category, weight=weight, description=desc)
            st.success("Criterio añadido."); st.rerun()


def _needs(user: dict) -> None:
    with session_scope() as session:
        season = repo.get_active_season(session)
        roles = planning_repo.list_model_roles(session)
        needs = planning_repo.list_squad_needs(session, season.id) if season else []
    if not season:
        st.warning("No hay temporada activa."); return
    st.markdown(f"### Mapa de necesidades · {season.name}")
    needs_by_role = {n.model_role_id:n for n in needs}
    if roles:
        st.dataframe(pd.DataFrame([{
            "Posición":r.position,"Rol":r.name,
            "Necesidad":needs_by_role[r.id].need_level if r.id in needs_by_role else "Sin definir",
            "Estado":needs_by_role[r.id].status if r.id in needs_by_role else "-",
            "Nota":needs_by_role[r.id].note if r.id in needs_by_role else "",
        } for r in roles]), hide_index=True, use_container_width=True)
    if not roles:
        st.info("Primero define al menos un rol de vuestro modelo."); return
    role_id = st.selectbox("Rol / posición", [r.id for r in roles], format_func=lambda rid: next(f"{r.position} · {r.name}" for r in roles if r.id==rid))
    existing = needs_by_role.get(role_id)
    with st.form("squad_need"):
        level = st.selectbox("Necesidad", NEED_LEVELS, index=NEED_LEVELS.index(existing.need_level) if existing and existing.need_level in NEED_LEVELS else 1)
        status = st.selectbox("Estado", ["Abierta","Cubierta","No prioritaria"], index=0)
        note = st.text_area("Contexto", value=existing.note if existing else "", height=80)
        save = st.form_submit_button("Guardar necesidad", type="primary")
    if save:
        with session_scope() as session:
            planning_repo.upsert_squad_need(session, user["id"], season_id=season.id, model_role_id=role_id, need_level=level, status=status, note=note)
        st.success("Mapa de plantilla actualizado."); st.rerun()


def _shadow(user: dict) -> None:
    with session_scope() as session:
        season = repo.get_active_season(session)
        board = planning_repo.shadow_squad(session, season.id) if season else []
        profiles = scout_repo.list_profiles(session, limit=400)
        roles = planning_repo.list_model_roles(session)
        own_team = repo.get_own_team(session)
        own_roster = players_repo.get_roster(session, own_team.id, season.id, active_only=True) if season and own_team else []
        all_decisions = planning_repo.list_season_decisions(session, season.id) if season else []
    if not season:
        st.warning("No hay temporada activa."); return
    st.markdown(f"### Plantilla sombra · {season.name}")
    st.caption("Por cada rol de No Name: jugadores de nuestra plantilla ya ubicados, necesidad actual y candidatos de nuestra liga.")
    for item in board:
        role=item["role"]; need=item["need"]; own_players=item.get("own_players",[]); candidates=item["candidates"]
        with st.container(border=True):
            a,b=st.columns([3,1])
            a.markdown(f"**{role.position} · {role.name}**")
            a.caption(role.description or "Sin descripción")
            b.metric("Necesidad", need.need_level if need else "Sin definir")
            if own_players:
                st.markdown("**Plantilla No Name**")
                st.dataframe(pd.DataFrame([{"Jugador":d.player.display_name or d.player.full_name,"Encaje":d.fit_score,"Nivel":d.current_level,"Proyección":d.potential_score,"Nota DD":d.director_note or ""} for d in own_players]), hide_index=True, use_container_width=True)
            else:
                st.caption("Sin jugadores de No Name vinculados todavía a este rol.")
            if candidates:
                st.markdown("**Candidatos de la liga**")
                st.dataframe(pd.DataFrame([{"Jugador":d.player.display_name or d.player.full_name,"Estado":d.status,"Prioridad":d.priority,"Encaje":d.fit_score,"Conclusión":d.director_note} for d in candidates]), hide_index=True, use_container_width=True)
            else:
                st.caption("Todavía no hay candidatos externos vinculados a este rol.")

    st.markdown("### Mapear nuestra plantilla al modelo")
    st.caption("Esto permite comparar un candidato con futbolistas de No Name usando el mismo rol y los mismos criterios, sin convertir a nuestros jugadores en fichas Scout.")
    if own_roster and roles:
        own_map={r.player_id:r.player for r in own_roster}
        own_pid=st.selectbox("Jugador de No Name",list(own_map),format_func=lambda x:own_map[x].display_name or own_map[x].full_name,key="own_model_player")
        role_id=st.selectbox("Rol No Name",[r.id for r in roles],format_func=lambda x:next(f"{r.position} · {r.name}" for r in roles if r.id==x),key="own_model_role")
        with session_scope() as session:
            criteria=planning_repo.list_model_criteria(session,role_id)
        existing=next((d for d in all_decisions if d.player_id==own_pid and d.model_role_id==role_id),None)
        old_scores={}
        if existing and existing.criteria_json:
            try:
                old_scores={int(k):float(v) for k,v in json.loads(existing.criteria_json).items()}
            except Exception:
                old_scores={}
        with st.form(f"own_model_assessment_{own_pid}_{role_id}"):
            c1,c2,c3=st.columns(3)
            fit=c1.slider("Encaje DD",0.0,10.0,float(existing.fit_score or 0) if existing else 0.0,.5)
            current=c2.slider("Nivel actual",0.0,10.0,float(existing.current_level or 0) if existing else 0.0,.5)
            potential=c3.slider("Proyección",0.0,10.0,float(existing.potential_score or 0) if existing else 0.0,.5)
            scores={}
            if criteria:
                st.markdown("**Criterios del rol**")
                for criterion in criteria:
                    scores[criterion.id]=st.slider(f"{criterion.name} · peso {criterion.weight}",0.0,10.0,float(old_scores.get(criterion.id,0)),.5,key=f"owncrit_{own_pid}_{role_id}_{criterion.id}")
            note=st.text_area("Nota DD interna",value=existing.director_note if existing else "",height=70)
            save_own=st.form_submit_button("Guardar perfil interno",type="primary",use_container_width=True)
        if save_own:
            with session_scope() as session:
                planning_repo.upsert_season_decision(session,user["id"],season_id=season.id,player_id=own_pid,status="Plantilla",priority=2,model_role_id=role_id,director_note=note,fit_score=fit or None,current_level=current or None,potential_score=potential or None,criteria_scores=scores)
            st.success("Jugador de No Name ubicado en el modelo."); st.rerun()
    else:
        st.info("Necesitas una plantilla activa de No Name y al menos un rol configurado.")

    st.markdown("### Ubicar candidato")
    if not profiles or not roles:
        st.info("Necesitas jugadores ojeados y roles del modelo."); return
    player_map={p.player_id:p.player for p in profiles}
    with st.form("shadow_assign"):
        pid=st.selectbox("Jugador",list(player_map),format_func=lambda x:player_map[x].display_name or player_map[x].full_name)
        rid=st.selectbox("Rol No Name",[r.id for r in roles],format_func=lambda x:next(f"{r.position} · {r.name}" for r in roles if r.id==x))
        status=st.selectbox("Decisión de temporada",["Base","Interesante","Seguimiento","Prioritario","Descartado"],index=2)
        priority=st.selectbox("Prioridad",[1,2,3],index=1,format_func=lambda x:{1:"Alta",2:"Media",3:"Normal"}[x])
        fit=st.slider("Encaje DD",0.0,10.0,0.0,.5)
        note=st.text_area("Conclusión DD")
        save=st.form_submit_button("Guardar en plantilla sombra",type="primary")
    if save:
        with session_scope() as session:
            planning_repo.upsert_season_decision(session,user["id"],season_id=season.id,player_id=pid,status=status,priority=priority,model_role_id=rid,director_note=note,fit_score=fit or None)
        st.success("Candidato ubicado en el modelo para esta temporada."); st.rerun()


def _history(user: dict) -> None:
    with session_scope() as session:
        seasons=repo.list_seasons(session)
    if not seasons: return
    sid=st.selectbox("Temporada",[s.id for s in seasons],format_func=lambda x:next(s.name for s in seasons if s.id==x),key="model_history_season")
    with session_scope() as session:
        rows=planning_repo.list_season_decisions(session,sid)
    if not rows: st.info("No hay decisiones guardadas en esta temporada."); return
    st.dataframe(pd.DataFrame([{"Jugador":d.player.display_name or d.player.full_name,"Rol":f"{d.model_role.position} · {d.model_role.name}" if d.model_role else "-","Estado":d.status,"Prioridad":d.priority,"Encaje":d.fit_score,"Conclusión":d.director_note} for d in rows]),hide_index=True,use_container_width=True)



def _opportunities(user: dict) -> None:
    with session_scope() as session:
        season = repo.get_active_season(session)
        if not season:
            opportunities = []
            scouts = []
        else:
            opportunities = planning_repo.scouting_opportunities(session, season_id=season.id, days_ahead=120, limit=40)
            scouts = planning_repo.list_scout_users(session)
    if not season:
        st.warning("No hay temporada activa."); return
    st.markdown(f"### Oportunidades de observación · {season.name}")
    st.caption("Cruza necesidades abiertas de la plantilla sombra con los próximos partidos reales de los candidatos.")
    if not opportunities:
        st.info("No hay oportunidades próximas. Define necesidades y ubica candidatos en la plantilla sombra para que el calendario pueda proponer visionados.")
        return
    if not scouts:
        st.warning("No hay perfiles Scout disponibles para asignar tareas."); return
    default_scout = st.selectbox("Scout para asignaciones rápidas", [u.id for u in scouts], format_func=lambda uid: next(u.full_name for u in scouts if u.id == uid), key="model_opportunity_scout")
    for idx, item in enumerate(opportunities):
        role, need, decision, match, evidence = item["role"], item["need"], item["decision"], item["match"], item["evidence"]
        player = decision.player
        with st.container(border=True):
            a,b,c = st.columns([3,2,1])
            a.markdown(f"**{player.display_name or player.full_name}** · {role.position} · {role.name}")
            a.caption(f"Necesidad {need.need_level} · Estado {decision.status} · Encaje {decision.fit_score if decision.fit_score is not None else '-'}")
            b.markdown(f"**{match.home_team.name} - {match.away_team.name}**")
            b.caption(f"{match.match_date.strftime('%d/%m/%Y')} · {match.kickoff_at.strftime('%H:%M') if match.kickoff_at else 'horario pendiente'}")
            c.metric("Scout específico", evidence["specific_observations"])
            st.caption(f"Evidencia actual: {evidence['postmatch_observations']} postpartido · {evidence['specific_observations']} específicas · {evidence['specific_strength']}")
            if st.button("Planificar observación", key=f"model_opportunity_{idx}_{decision.player_id}_{match.id}", type="primary", use_container_width=True):
                with session_scope() as session:
                    planning_repo.create_mission(
                        session, match_id=match.id, mission_type="player",
                        title=f"Observar {player.display_name or player.full_name} · {role.name}",
                        assigned_to=default_scout, requested_by=user["id"], target_team_id=item["team_id"],
                        player_ids=[decision.player_id],
                        purpose=f"Contrastar a este jugador para la necesidad {need.need_level.lower()} del rol {role.position} · {role.name}.",
                        focus=[f"Encaje {role.name}", "Segunda evidencia específica" if evidence['specific_observations'] else "Primera observación específica"],
                        priority=1 if need.need_level == "Alta" else 2, due_at=match.kickoff_at,
                    )
                st.success("Observación asignada al Scout y vinculada al partido.")
                st.rerun()

def render(user: dict) -> None:
    if user["role"] not in {"director","admin"}:
        st.error("Solo Dirección Deportiva puede definir el Modelo No Name."); return
    page_header("Modelo No Name", "Define perfiles, necesidades y una plantilla sombra con candidatos de nuestra propia liga.")
    section=st.radio("Área",["Roles y criterios","Necesidades","Plantilla sombra","Planificación","Histórico por temporada"],horizontal=True,key="model_section")
    if section=="Roles y criterios": _roles(user)
    elif section=="Necesidades": _needs(user)
    elif section=="Plantilla sombra": _shadow(user)
    elif section=="Planificación": _opportunities(user)
    else: _history(user)
