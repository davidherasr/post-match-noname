from __future__ import annotations

import streamlit as st

from core.navigation import request_navigation

from core.constants import POSITIONS
from core.database import session_scope
from core.permissions import can_direct
from core.presentation import NEED_STATES, normalize_need_state
from repositories import planning as planning_repo
from repositories import players as players_repo
from ui.styles import page_header


def _open_player(pid: int) -> None:
    st.session_state["workspace_player_id"]=int(pid)
    request_navigation("Jugadores")
    st.rerun()


def _configure_model(user: dict) -> None:
    with st.expander("Configurar Modelo No Name",expanded=False):
        with st.form("new_role_38"):
            c1,c2=st.columns(2)
            name=c1.text_input("Nombre del rol",placeholder="Base / Profundidad / Dominador...")
            pos=c2.selectbox("Posición",POSITIONS)
            description=st.text_area("Descripción",height=70)
            create=st.form_submit_button("Crear rol",type="primary",use_container_width=True)
        if create and name.strip():
            try:
                with session_scope() as session:
                    planning_repo.create_model_role(session,user["id"],name=name,position=pos,description=description)
                st.success("Rol creado."); st.rerun()
            except Exception as exc: st.error(str(exc))
        with session_scope() as session:
            roles=planning_repo.list_model_roles(session)
        if roles:
            role_id=st.selectbox("Añadir criterio a",[r.id for r in roles],format_func=lambda rid:next(f"{r.position} · {r.name}" for r in roles if r.id==rid),key="criterion_role38")
            with st.form(f"criterion_new38_{role_id}"):
                c1,c2,c3=st.columns([3,2,1])
                cname=c1.text_input("Criterio",placeholder="Ataque de profundidad")
                category=c2.selectbox("Bloque",["Técnico","Táctico","Físico","Mental","Mixto"])
                weight=c3.number_input("Peso",1,5,3)
                detail=st.text_input("Qué observar",placeholder="Descripción operativa")
                add=st.form_submit_button("Añadir criterio",use_container_width=True)
            if add and cname.strip():
                with session_scope() as session:
                    planning_repo.add_model_criterion(session,user["id"],role_id,name=cname,category=category,weight=weight,description=detail)
                st.success("Criterio añadido."); st.rerun()


def _map_own_players(user: dict, season, role) -> None:
    with session_scope() as session:
        own=players_repo.get_own_team(session)
        roster=players_repo.get_roster(session,own.id,season.id) if own else []
        decisions=planning_repo.list_season_decisions(session,season.id)
    mapped={d.player_id for d in decisions if d.model_role_id==role.id}
    options=[r.player_id for r in roster if r.player_id not in mapped]
    if not options: return
    player_map={r.player_id:r.player for r in roster}
    with st.expander("Mapear nuestra plantilla al rol",expanded=False):
        selected=st.multiselect("Jugadores",options,format_func=lambda pid:player_map[pid].display_name or player_map[pid].full_name,key=f"map_own38_{role.id}")
        if st.button("Asignar al rol",use_container_width=True,key=f"map_own_save38_{role.id}") and selected:
            with session_scope() as session:
                for pid in selected:
                    planning_repo.upsert_season_decision(session,user["id"],season_id=season.id,player_id=pid,status="Observado",priority=3,model_role_id=role.id)
            st.success("Plantilla mapeada."); st.rerun()


def _role_detail(user: dict, season, role_id: int) -> None:
    if st.button("← Volver al tablero",key="back_role38"):
        st.session_state.pop("workspace_role_id",None); st.rerun()
    with session_scope() as session:
        roles=planning_repo.list_model_roles(session)
        role=next((r for r in roles if r.id==role_id),None)
        if not role:
            st.warning("Rol no encontrado."); return
        criteria=planning_repo.list_model_criteria(session,role.id)
        shadow=next((b for b in planning_repo.shadow_squad(session,season.id) if b["role"].id==role.id),None)
        candidates=shadow["candidates"] if shadow else []
        own_players=shadow["own_players"] if shadow else []
        evidence=planning_repo.scouting_evidence_many(session,[d.player_id for d in candidates],season_id=season.id)
        opportunities=planning_repo.scouting_opportunities(session,season_id=season.id,days_ahead=120,limit=50)
    page_header(f"{role.position} · {role.name}",role.description or "Rol del Modelo No Name")
    if criteria:
        st.markdown("### Criterios")
        for c in criteria:
            st.markdown(f"- **{c.name}** · {c.category} · peso {c.weight}" + (f" — {c.description}" if c.description else ""))
    else: st.caption("Este rol todavía no tiene criterios configurados.")
    st.markdown("### Nuestra plantilla")
    if own_players:
        for d in own_players:
            with st.container(border=True):
                a,b=st.columns([5,1]); a.markdown(f"**{d.player.display_name or d.player.full_name}** · encaje {'—' if d.fit_score is None else f'{d.fit_score:.1f}'}")
                if b.button("Abrir",key=f"role_own38_{d.player_id}",use_container_width=True): _open_player(d.player_id)
    else: st.caption("Sin referencias internas mapeadas.")
    _map_own_players(user,season,role)
    st.markdown("### Candidatos")
    if candidates:
        for d in candidates:
            ev=evidence.get(d.player_id,{})
            with st.container(border=True):
                a,b=st.columns([5,1]); a.markdown(f"**{d.player.display_name or d.player.full_name}** · {d.status}")
                a.caption(f"Encaje {'—' if d.fit_score is None else f'{d.fit_score:.1f}'} · 👁 {ev.get('specific_observations',0)} observaciones Scout")
                if b.button("Abrir",key=f"role_candidate38_{d.player_id}",use_container_width=True): _open_player(d.player_id)
    else: st.caption("Sin candidatos asignados a este rol.")
    relevant=[o for o in opportunities if o.get("role") and o["role"].id==role.id]
    if relevant:
        st.markdown("### Próximas oportunidades")
        for item in relevant[:8]:
            match=item["match"]; player=item["decision"].player
            st.caption(f"{player.display_name or player.full_name} · {match.round_name} · {match.home_team.name} - {match.away_team.name} · {match.match_date.strftime('%d/%m/%Y')}")


def render(user: dict) -> None:
    if not can_direct(user):
        st.error("No tienes permiso de Dirección Deportiva."); return
    with session_scope() as session:
        season=players_repo.get_active_season(session)
    if not season:
        st.warning("No hay temporada activa."); return
    opened=st.session_state.get("workspace_role_id")
    if opened:
        _role_detail(user,season,int(opened)); return
    page_header("Plantilla","Modelo No Name, necesidades, plantilla propia y candidatos en un único tablero.")
    _configure_model(user)
    with session_scope() as session:
        blocks=planning_repo.shadow_squad(session,season.id)
        all_candidate_ids=[d.player_id for block in blocks for d in block["candidates"]]
        evidence=planning_repo.scouting_evidence_many(session,all_candidate_ids,season_id=season.id)
    if not blocks:
        st.info("Configura el primer rol del Modelo No Name para empezar."); return
    for block in blocks:
        role=block["role"]; need=block.get("need"); need_value=normalize_need_state(need.need_level if need else "Media")
        with st.container(border=True):
            h1,h2,h3=st.columns([4,1,1])
            h1.markdown(f"### {role.position} · {role.name}")
            h2.metric("Necesidad",need_value)
            if h3.button("Abrir rol",use_container_width=True,key=f"open_role38_{role.id}"):
                st.session_state["workspace_role_id"]=role.id; st.rerun()
            own_names=[d.player.display_name or d.player.full_name for d in block["own_players"][:4]]
            st.markdown("**No Name:** "+(", ".join(own_names) if own_names else "sin referencia mapeada"))
            if block["candidates"]:
                candidate_text=[]
                for d in block["candidates"][:5]:
                    ev=evidence.get(d.player_id,{})
                    candidate_text.append(f"{d.player.display_name or d.player.full_name} ({'—' if d.fit_score is None else f'{d.fit_score:.1f}'} · 👁 {ev.get('specific_observations',0)})")
                st.caption("Candidatos: "+" · ".join(candidate_text))
            else: st.caption("Candidatos: —")
            with st.expander("Actualizar necesidad"):
                with st.form(f"need38_{role.id}"):
                    level=st.selectbox("Estado",NEED_STATES,index=NEED_STATES.index(need_value),key=f"needlevel38_{role.id}")
                    note=st.text_input("Nota",value=need.note if need else "",key=f"neednote38_{role.id}")
                    save=st.form_submit_button("Guardar",use_container_width=True)
                if save:
                    with session_scope() as session:
                        planning_repo.upsert_squad_need(session,user["id"],season_id=season.id,model_role_id=role.id,need_level=level,note=note)
                    st.success("Necesidad actualizada."); st.rerun()
