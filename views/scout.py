from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

from core.constants import POSITIONS, SCOUT_MISSION_STATUSES, SCOUT_MISSION_TYPES
from core.database import session_scope
from core.schedule import is_schedule_confirmed
from repositories import calendar as calendar_repo
from repositories import planning as planning_repo
from repositories import scouting as repo
from ui.styles import page_header


def _mission_focus(mission) -> list[str]:
    try:
        return list(json.loads(mission.focus_json or "[]"))
    except Exception:
        return []


def _observation_form(observation, player, user: dict) -> None:
    with session_scope() as session:
        roles = planning_repo.list_model_roles(session)
    st.markdown(f"### {player.display_name or player.full_name}")
    if observation.match:
        st.caption(f"{observation.match.home_team.name} - {observation.match.away_team.name} · {calendar_repo.schedule_label(observation.match)}")
    try:
        saved_attrs = json.loads(observation.attributes_json or "{}")
    except Exception:
        saved_attrs = {}
    saved_role = saved_attrs.get("model_role_id")
    try:
        saved_role = int(saved_role) if saved_role is not None else None
    except Exception:
        saved_role = None
    role_options = [None] + [r.id for r in roles]
    if saved_role not in role_options:
        saved_role = None
    # Outside the form on purpose: changing the role reruns immediately and reveals
    # the correct model criteria instead of requiring a dummy submit.
    model_role_id = st.selectbox(
        "Rol No Name a contrastar", role_options,
        index=role_options.index(saved_role),
        format_func=lambda rid: "Sin rol concreto" if rid is None else next(f"{r.position} · {r.name}" for r in roles if r.id == rid),
        key=f"scout_model_role_{observation.id}",
    )
    criteria = []
    if model_role_id:
        with session_scope() as session:
            criteria = planning_repo.list_model_criteria(session, model_role_id)
    recommendations = ["Sin conclusión", "No encaja", "Volver a ver", "Seguimiento", "Prioritario", "Descartar"]
    saved_recommendation = observation.recommendation if observation.recommendation in recommendations else "Sin conclusión"
    with st.form(f"scout_observation_{observation.id}"):
        a,b = st.columns(2)
        pos = a.selectbox("Posición observada", POSITIONS, index=POSITIONS.index(observation.observed_position) if observation.observed_position in POSITIONS else 0)
        recommendation = b.selectbox("Recomendación", recommendations, index=recommendations.index(saved_recommendation))
        st.caption("Solo puntúa aquello que realmente puedas sostener con lo observado.")
        general = st.slider("Nota de este visionado", 0.0, 10.0, float(observation.general_rating or 0), .5, help="Rendimiento/impresión de este partido; no sustituye a nivel actual ni se mezcla automáticamente con la media postpartido.")
        r1,r2,r3,r4 = st.columns(4)
        technical = r1.slider("Técnico", 0.0, 10.0, float(observation.technical_rating or 0), .5)
        tactical = r2.slider("Táctico", 0.0, 10.0, float(observation.tactical_rating or 0), .5)
        physical = r3.slider("Físico", 0.0, 10.0, float(observation.physical_rating or 0), .5)
        mental = r4.slider("Mental", 0.0, 10.0, float(observation.mental_rating or 0), .5)
        c1,c2,c3 = st.columns(3)
        current = c1.slider("Nivel actual", 0.0, 10.0, float(observation.current_level or 0), .5)
        potential = c2.slider("Proyección", 0.0, 10.0, float(observation.potential_score or 0), .5)
        fit = c3.slider("Encaje preliminar No Name", 0.0, 10.0, float(observation.model_fit_score or 0), .5)
        criteria_scores = {}
        if criteria:
            st.markdown("**Criterios de nuestro modelo**")
            for criterion in criteria:
                default = float(saved_attrs.get(str(criterion.id), 0) or 0)
                criteria_scores[criterion.id] = st.slider(f"{criterion.name} · peso {criterion.weight}", 0.0, 10.0, default, .5, key=f"crit_{observation.id}_{criterion.id}")
            weighted = planning_repo.weighted_model_fit(criteria, criteria_scores)
            if weighted is not None:
                st.caption(f"Encaje ponderado por criterios: **{weighted:.2f}/10**")
        strengths = st.text_area("Fortalezas", value=observation.strengths or "", height=80)
        weaknesses = st.text_area("Riesgos / debilidades", value=observation.weaknesses or "", height=80)
        summary = st.text_area("Resumen scout", value=observation.summary or "", height=110)
        save, submit = st.columns(2)
        save_btn = save.form_submit_button("Guardar borrador", use_container_width=True)
        submit_btn = submit.form_submit_button("Entregar observación", type="primary", use_container_width=True)
    if save_btn or submit_btn:
        attrs = {str(k): v for k,v in criteria_scores.items() if v > 0}
        if model_role_id:
            attrs["model_role_id"] = model_role_id
        with session_scope() as session:
            planning_repo.save_observation(
                session, observation.id, user["id"], observed_position=pos, general_rating=general or None,
                technical_rating=technical or None, tactical_rating=tactical or None,
                physical_rating=physical or None, mental_rating=mental or None,
                current_level=current or None, potential_score=potential or None,
                model_fit_score=fit or None, attributes=attrs, strengths=strengths,
                weaknesses=weaknesses, summary=summary, recommendation=recommendation,
                submit=bool(submit_btn),
            )
        st.success("Observación entregada a Dirección Deportiva." if submit_btn else "Borrador guardado.")
        st.session_state.pop("scout_observation_id", None)
        st.rerun()


def _mission_card(mission, user: dict) -> None:
    targets = []
    with session_scope() as session:
        targets = planning_repo.mission_targets(session, mission.id)
    with st.container(border=True):
        a,b = st.columns([4,1])
        a.markdown(f"**{mission.title}**")
        a.caption(f"{mission.match.home_team.name} - {mission.match.away_team.name} · {calendar_repo.schedule_label(mission.match)}")
        b.metric("Prioridad", {1:"Alta",2:"Media",3:"Normal"}.get(mission.priority, mission.priority))
        st.write(mission.purpose or "Sin indicaciones adicionales.")
        focus = _mission_focus(mission)
        if focus:
            st.caption("Foco: " + " · ".join(focus))
        if targets:
            st.caption("Jugadores: " + ", ".join(t.player.display_name or t.player.full_name for t in targets))
        if not is_schedule_confirmed(mission.match):
            st.warning("Tarea planificada · horario pendiente. Podrás abrir el informe cuando Administración confirme fecha y hora.")
            return
        if mission.mission_type in {"team", "rival_analysis"} and not targets:
            st.markdown("**Informe de equipo / rival**")
            with st.form(f"team_mission_{mission.id}"):
                system = st.text_input("Estructura / sistema observado", placeholder="4-2-3-1; cambia a 4-4-2 sin balón")
                with_ball = st.text_area("Con balón", height=80, placeholder="Inicio, progresión, amenazas, patrones...")
                without_ball = st.text_area("Sin balón", height=80, placeholder="Altura, presión, bloque, espacios...")
                transitions = st.text_area("Transiciones", height=70, placeholder="Tras pérdida / tras recuperación")
                set_pieces = st.text_area("ABP relevantes", height=70, placeholder="Solo lo útil para preparar el enfrentamiento")
                key_players = st.text_area("Jugadores clave", height=70)
                plan = st.text_area("Claves para No Name", height=90, placeholder="Qué deberíamos explotar, evitar o vigilar")
                summary = st.text_area("Conclusión", value=mission.result_summary or "", height=100)
                c1,c2 = st.columns(2)
                save_progress = c1.form_submit_button("Guardar avance", use_container_width=True)
                complete = c2.form_submit_button("Completar tarea", type="primary", use_container_width=True)
            if save_progress or complete:
                result = "\n\n".join([
                    f"Sistema: {system}" if system.strip() else "",
                    f"CON BALÓN\n{with_ball}" if with_ball.strip() else "",
                    f"SIN BALÓN\n{without_ball}" if without_ball.strip() else "",
                    f"TRANSICIONES\n{transitions}" if transitions.strip() else "",
                    f"ABP\n{set_pieces}" if set_pieces.strip() else "",
                    f"JUGADORES CLAVE\n{key_players}" if key_players.strip() else "",
                    f"CLAVES PARA NO NAME\n{plan}" if plan.strip() else "",
                    f"CONCLUSIÓN\n{summary}" if summary.strip() else "",
                ]).strip()
                with session_scope() as session:
                    planning_repo.update_mission_status(session, mission.id, user["id"], status="completed" if complete else "in_progress", result_summary=result)
                st.success("Análisis entregado." if complete else "Avance guardado."); st.rerun()
        for target in targets:
            if st.button(f"Observar · {target.player.display_name or target.player.full_name}", key=f"mission_target_{mission.id}_{target.player_id}", use_container_width=True):
                with session_scope() as session:
                    obs = planning_repo.create_observation(session, player_id=target.player_id, reviewer_id=user["id"], match_id=mission.match_id, mission_id=mission.id, source_type="specific")
                st.session_state["scout_observation_id"] = obs.id
                st.rerun()



def _my_day(user: dict) -> None:
    today = date.today()
    with session_scope() as session:
        active = repo.get_active_season(session)
        missions = planning_repo.list_missions(session, assigned_to=user["id"], limit=200)
        matches = calendar_repo.list_calendar(session, season_id=active.id if active else None, date_from=today, date_to=date.fromordinal(today.toordinal()+10), limit=200) if active else []
    pending = [m for m in missions if m.status in {"pending", "in_progress"}]
    mission_by_match = {}
    for mission in pending:
        mission_by_match.setdefault(mission.match_id, []).append(mission)
    c1,c2,c3 = st.columns(3)
    c1.metric("Misiones activas", len(pending))
    c2.metric("Partidos próximos", len(matches))
    c3.metric("Con tarea DD", len(mission_by_match))
    if pending:
        st.markdown("### Prioridad de trabajo")
        for mission in pending[:6]:
            _mission_card(mission, user)
    st.markdown("### Partidos disponibles · próximos 10 días")
    if not matches:
        st.info("No hay partidos próximos cargados en el calendario.")
        return
    for match in matches[:30]:
        tasks = mission_by_match.get(match.id, [])
        with st.container(border=True):
            a,b = st.columns([4,1])
            a.markdown(f"**{match.home_team.name} - {match.away_team.name}**")
            a.caption(f"{match.round_name or ''} · {calendar_repo.schedule_label(match)}")
            b.metric("Tareas", len(tasks))
            if tasks:
                st.caption(" · ".join(t.title for t in tasks))
            ready = is_schedule_confirmed(match)
            if st.button("Observar este partido", key=f"scout_day_match_{match.id}", use_container_width=True, disabled=not ready):
                st.session_state["scout_match_id"] = match.id
                st.session_state["scout_section"] = "Observar partido"
                st.rerun()
            if not ready:
                st.caption("Horario pendiente · visible para planificar, todavía no para registrar el visionado.")

def _my_missions(user: dict) -> None:
    with session_scope() as session:
        missions = planning_repo.list_missions(session, assigned_to=user["id"], limit=200)
    pending = [m for m in missions if m.status in {"pending", "in_progress"}]
    done = [m for m in missions if m.status == "completed"]
    a,b = st.columns(2); a.metric("Pendientes", len(pending)); b.metric("Completadas", len(done))
    if not pending:
        st.info("No tienes tareas pendientes de Dirección Deportiva.")
    for m in pending:
        _mission_card(m, user)
    if done:
        with st.expander("Tareas completadas"):
            st.dataframe(pd.DataFrame([{"Partido": f"{m.match.home_team.name} - {m.match.away_team.name}", "Tarea": m.title, "Completada": m.completed_at} for m in done]), hide_index=True, use_container_width=True)


def _spontaneous(user: dict) -> None:
    with session_scope() as session:
        active = repo.get_active_season(session)
        matches = calendar_repo.list_calendar(session, season_id=active.id if active else None, limit=400)
    if not matches:
        st.info("No hay calendario cargado."); return
    preset = st.session_state.pop("scout_match_id", None)
    ids = [m.id for m in matches]
    match_id = st.selectbox("Partido", ids, index=ids.index(preset) if preset in ids else 0, format_func=lambda mid: next(f"{m.round_name} · {m.home_team.name} - {m.away_team.name} · {calendar_repo.schedule_label(m)}" for m in matches if m.id == mid))
    match = next(m for m in matches if m.id == match_id)
    if not is_schedule_confirmed(match):
        st.warning("Este partido aún tiene horario pendiente. Puedes consultarlo en el calendario, pero no registrar observaciones hasta confirmar fecha y hora.")
        return
    with session_scope() as session:
        roster = repo.get_roster(session, match.home_team_id, match.season_id) + repo.get_roster(session, match.away_team_id, match.season_id)
    players = {r.player_id:r.player for r in roster}
    with st.expander("Añadir jugador que no está en plantilla", expanded=not bool(players)):
        st.caption("Úsalo si estás viendo un partido neutral y el futbolista todavía no existe en nuestra base.")
        with st.form(f"scout_quick_player_{match.id}"):
            team_id_new = st.selectbox("Equipo", [match.home_team_id, match.away_team_id], format_func=lambda tid: match.home_team.name if tid == match.home_team_id else match.away_team.name)
            a,b,c=st.columns([3,1,1])
            new_name=a.text_input("Nombre")
            new_pos=b.selectbox("POS", POSITIONS)
            new_shirt=c.number_input("Dorsal",0,99,value=None,step=1)
            add=st.form_submit_button("Añadir a la plantilla de esta temporada")
        if add and new_name.strip():
            with session_scope() as session:
                player=repo.find_or_create_player(session,new_name.strip(),primary_position=new_pos,actor_id=user["id"])
                repo.assign_player_to_roster(session,team_id_new,match.season_id,player.id,int(new_shirt) if new_shirt is not None else None,actor_id=user["id"])
            st.success("Jugador añadido. Ya puedes seleccionarlo."); st.rerun()
    if not players:
        st.warning("Añade al menos un jugador para comenzar la observación.")
        return

    st.markdown("### Barrido rápido del partido")
    st.caption("Para cuando ves el encuentro completo y quieres dejar una primera impresión de varios jugadores sin abrir una ficha avanzada para cada uno.")
    scan_ids = st.multiselect("Jugadores para valoración rápida", list(players), format_func=lambda x: players[x].display_name or players[x].full_name, key=f"scan_players_{match.id}")
    if scan_ids:
        with st.form(f"quick_scan_{match.id}"):
            scan_rows = []
            for player_id in scan_ids:
                player = players[player_id]
                a,b = st.columns([1,3])
                rating = a.slider(f"{player.display_name or player.full_name} · nota", 0.0, 10.0, 0.0, .5, key=f"scan_rating_{match.id}_{player_id}")
                note = b.text_input(f"{player.display_name or player.full_name} · apunte", key=f"scan_note_{match.id}_{player_id}", placeholder="Opcional")
                scan_rows.append({"player_id":player_id,"general_rating":rating,"observed_position":player.primary_position,"summary":note})
            save_scan = st.form_submit_button("Guardar barrido rápido", type="primary", use_container_width=True)
        if save_scan:
            with session_scope() as session:
                count = planning_repo.save_quick_match_observations(session, match_id=match.id, reviewer_id=user["id"], rows=scan_rows)
            if count:
                st.success(f"{count} observaciones rápidas guardadas como scouting del partido.")
            else:
                st.warning("No se guardó ninguna observación: asigna una nota superior a 0.")
            st.rerun()

    st.markdown("### Observación individual / ficha avanzada")
    pid = st.selectbox("Jugador", list(players), format_func=lambda x: players[x].display_name or players[x].full_name)
    if st.button("Crear observación espontánea", type="primary", use_container_width=True):
        with session_scope() as session:
            obs = planning_repo.create_observation(session, player_id=pid, reviewer_id=user["id"], match_id=match.id, source_type="spontaneous")
        st.session_state["scout_observation_id"] = obs.id
        st.rerun()


def _history(user: dict) -> None:
    with session_scope() as session:
        rows = planning_repo.list_observations(session, reviewer_id=user["id"], limit=300)
    if not rows:
        st.info("Todavía no has registrado observaciones scout."); return
    state = st.selectbox("Estado", ["Todos", "draft", "submitted"], format_func=lambda x: {"Todos":"Todos","draft":"Borradores","submitted":"Entregadas"}.get(x,x), key="scout_history_state")
    visible = rows if state == "Todos" else [o for o in rows if o.status == state]
    st.dataframe(pd.DataFrame([{
        "Fecha": o.observed_at, "Jugador": o.profile.player.display_name or o.profile.player.full_name,
        "Partido": "-" if not o.match else f"{o.match.home_team.name} - {o.match.away_team.name}",
        "Tipo": "Específica" if o.source_type == "specific" else ("Barrido" if o.source_type == "match_scan" else "Espontánea"), "Estado": o.status,
        "Posición": o.observed_position, "Nota": o.general_rating, "Encaje": o.model_fit_score, "Recomendación": o.recommendation,
    } for o in visible]), hide_index=True, use_container_width=True)
    drafts = [o for o in visible if o.status == "draft"]
    if drafts:
        oid = st.selectbox("Continuar borrador", [o.id for o in drafts], format_func=lambda x: next(o.profile.player.display_name or o.profile.player.full_name for o in drafts if o.id == x))
        if st.button("Abrir borrador", type="primary", use_container_width=True):
            st.session_state["scout_observation_id"] = oid
            st.rerun()



def _model_reference(user: dict) -> None:
    with session_scope() as session:
        season = repo.get_active_season(session)
        roles = planning_repo.list_model_roles(session)
        needs = planning_repo.list_squad_needs(session, season.id) if season else []
        criteria_map = {role.id: planning_repo.list_model_criteria(session, role.id) for role in roles}
    st.markdown("### Modelo No Name · referencia Scout")
    st.caption("Consulta qué busca Dirección Deportiva. El Scout no modifica el modelo desde aquí; utiliza estos criterios en sus observaciones.")
    need_map = {n.model_role_id: n for n in needs}
    if not roles:
        st.info("Dirección Deportiva todavía no ha configurado roles del Modelo No Name.")
        return
    for role in roles:
        with st.container(border=True):
            a,b = st.columns([3,1])
            a.markdown(f"**{role.position} · {role.name}**")
            a.caption(role.description or "Sin descripción")
            need = need_map.get(role.id)
            b.metric("Necesidad", need.need_level if need else "Sin definir")
            criteria = criteria_map.get(role.id, [])
            if criteria:
                st.dataframe(pd.DataFrame([{
                    "Criterio": c.name, "Bloque": c.category, "Peso": c.weight, "Qué observar": c.description or ""
                } for c in criteria]), hide_index=True, use_container_width=True)
            else:
                st.caption("Sin criterios específicos todavía.")

def render(user: dict) -> None:
    if user["role"] not in {"scout", "admin", "director"}:
        st.error("Este espacio pertenece al perfil Scout."); return
    page_header("Scout", "Observa partidos de toda la liga, cumple tareas de DD y registra hallazgos espontáneos sin convertir cada visionado en un dossier obligatorio.")
    observation_id = st.session_state.get("scout_observation_id")
    if observation_id:
        with session_scope() as session:
            observation = session.get(__import__('models.entities', fromlist=['ScoutObservation']).ScoutObservation, int(observation_id))
            if observation:
                # Load relationships while the session is alive.
                player = session.get(__import__('models.entities', fromlist=['ScoutedPlayerProfile']).ScoutedPlayerProfile, observation.profile_id).player
                _ = observation.match.home_team.name if observation.match else None
                session.expunge(observation); session.expunge(player)
        # Re-load through repository with relationships to avoid detached relations.
        with session_scope() as session:
            rows = [o for o in planning_repo.list_observations(session, reviewer_id=user["id"], limit=500) if o.id == int(observation_id)]
            if rows:
                obs = rows[0]
                player = obs.profile.player
                # Rendering occurs before session closes to keep joined objects available.
                _observation_form(obs, player, user)
                return
        st.session_state.pop("scout_observation_id", None)
    section = st.radio("Área Scout", ["Mi jornada", "Misiones", "Observar partido", "Mis observaciones", "Modelo No Name"], horizontal=True, key="scout_section")
    if section == "Mi jornada":
        _my_day(user)
    elif section == "Misiones":
        _my_missions(user)
    elif section == "Observar partido":
        _spontaneous(user)
    elif section == "Mis observaciones":
        _history(user)
    else:
        _model_reference(user)
