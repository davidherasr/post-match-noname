from __future__ import annotations

import streamlit as st

from core.constants import POSITIONS
from core.database import session_scope
from core.permissions import can_direct
from core.presentation import PLAYER_STATES
from core.schedule import is_schedule_confirmed
from repositories import planning as planning_repo
from repositories import players as players_repo
from repositories import scouting as base_repo
from repositories import workspaces
from reports.player_report_pdf import generate_player_360_pdf, generate_player_executive_pdf, player_report_filename
from ui import player_report as player_ui
from ui.styles import page_header

FILTERS = ["Todos", "Destacados", "Seguimiento", "Scout", "Prioritarios", "Descartados"]


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
        state=c1.selectbox("Estado",PLAYER_STATES,index=PLAYER_STATES.index(existing.status) if existing and existing.status in PLAYER_STATES else 0)
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


def _next_action_editor(user: dict, payload: dict) -> None:
    if not can_direct(user) or not payload.get("season_id"):
        return
    player=payload["player"]
    st.markdown("### Próxima acción")
    if payload.get("next_action"):
        mission=payload["next_action"]; match=mission.match
        when=match.kickoff_at.strftime("%d/%m/%Y · %H:%M") if match.kickoff_at else f"{match.match_date.strftime('%d/%m/%Y')} · horario pendiente"
        st.info(f"{mission.title} · {match.home_team.name} - {match.away_team.name} · {when} · {mission.assignee.full_name}")
    with session_scope() as session:
        matches=workspaces.candidate_next_matches(session,player_id=player.id,season_id=payload["season_id"])
        scouts=planning_repo.list_scout_users(session)
    if not matches or not scouts:
        st.caption("No hay un próximo partido del jugador o un Scout disponible para programar la acción.")
        return
    with st.form(f"next_action38_{player.id}"):
        match_id=st.selectbox("Partido objetivo",[m.id for m in matches],format_func=lambda mid:next(f"{m.round_name} · {m.home_team.name} - {m.away_team.name} · {'confirmado' if is_schedule_confirmed(m) else 'horario pendiente'}" for m in matches if m.id==mid))
        assignee=st.selectbox("Responsable",[u.id for u in scouts],format_func=lambda uid:next(u.full_name for u in scouts if u.id==uid))
        purpose=st.text_input("Qué queremos resolver",value="Volver a observar y confirmar encaje")
        priority=st.selectbox("Prioridad",[1,2,3],index=1,format_func=lambda x:{1:"Alta",2:"Media",3:"Baja"}[x])
        create=st.form_submit_button("Asignar próxima acción",type="primary",use_container_width=True)
    if create:
        target=next(m for m in matches if m.id==match_id)
        with session_scope() as session:
            planning_repo.create_mission(
                session,match_id=match_id,mission_type="player",title=f"Observar · {player.display_name or player.full_name}",assigned_to=assignee,
                requested_by=user["id"],player_ids=[player.id],purpose=purpose,priority=priority,due_at=target.kickoff_at if is_schedule_confirmed(target) else None,
            )
        st.success("Próxima acción asignada.")
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
        payload=workspaces.load_player_workspace(session,player_id=player_id,season_id=active.id if active else None)
    player_ui.render_vertical_profile(payload,next_action=payload.get("next_action"))
    _decision_editor(user,payload)
    _next_action_editor(user,payload)
    with st.expander("Ver dossier completo",expanded=False):
        player_ui.render_evolution(payload)
        player_ui.render_observations(payload)
        player_ui.render_comparison(payload)
        player_ui.render_data(payload)
    _export(payload)


def _compare_players(ids: list[int]) -> None:
    if len(ids)!=2:
        return
    with session_scope() as session:
        active=players_repo.get_active_season(session)
        payloads=[workspaces.load_player_workspace(session,player_id=pid,season_id=active.id if active else None) for pid in ids]
    st.markdown("### Comparación")
    cols=st.columns(2)
    for col,payload in zip(cols,payloads):
        with col:
            p=payload["player"]
            st.markdown(f"**{p.display_name or p.full_name}**")
            st.metric("Rendimiento",payload["postmatch"]["average"] or "-")
            st.metric("Encaje",payload.get("fit_score") or "-")
            st.metric("Confianza",f"{payload['postmatch']['confidence']['score']}/100")
            st.caption(f"Estado: {payload['decision'].status if payload.get('decision') else 'Sin decisión'}")


def render(user: dict) -> None:
    opened=st.session_state.get("workspace_player_id")
    if opened:
        _render_player(user,int(opened)); return
    page_header("Jugadores","Una única ficha para todo lo que sabemos y decidimos de cada jugador.")
    with session_scope() as session:
        active=players_repo.get_active_season(session)
    c1,c2,c3=st.columns([3,1,2])
    search=c1.text_input("Buscar",placeholder="Nombre del jugador")
    position=c2.selectbox("Posición",["Todas"]+POSITIONS)
    state=c3.segmented_control("Filtro",FILTERS,default="Todos") or "Todos"
    with session_scope() as session:
        rows=workspaces.list_player_cards(session,season_id=active.id if active else None,search=search or None,position=None if position=="Todas" else position,state_filter=state,limit=80)
    if not rows:
        st.info("No hay jugadores con estos filtros."); return
    compare=st.multiselect("Comparar",[row["player"].id for row in rows],max_selections=2,format_func=lambda pid:next(row["player"].display_name or row["player"].full_name for row in rows if row["player"].id==pid))
    _compare_players(compare)
    for row in rows:
        p=row["player"]
        with st.container(border=True):
            a,b=st.columns([5,1])
            team=row["team"].name if row.get("team") else "Equipo no confirmado"
            a.markdown(f"**{p.display_name or p.full_name}** · {p.primary_position or '-'}")
            rating="—" if row["rating"] is None else f"{row['rating']:.1f}"
            a.caption(f"{team} · {row['state']} · rendimiento {rating} · 👁 {row['scout_count']} Scout")
            if b.button("Abrir",type="primary",use_container_width=True,key=f"open_player38_{p.id}"):
                _open_player(p.id)
