from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from core.calendar_import import parse_calendar_text
from core.constants import ROLES, SCOUT_MISSION_TYPES, SCHEDULE_STATUSES
from core.database import session_scope
from repositories import calendar as calendar_repo
from repositories import planning as planning_repo
from repositories import scouting as repo
from ui.styles import page_header


def _match_title(match) -> str:
    return f"{match.round_name} · {match.home_team.name} - {match.away_team.name}"


def _is_own(match, own_id: int | None) -> bool:
    return bool(own_id and own_id in {match.home_team_id, match.away_team_id})


def _fixture_table(matches, own_id: int | None) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Jornada": m.round_name,
            "Partido": f"{m.home_team.name} - {m.away_team.name}",
            "Programación": calendar_repo.schedule_label(m),
            "Estado": SCHEDULE_STATUSES.get(m.schedule_status, m.schedule_status),
            "No Name": "Sí" if _is_own(m, own_id) else "",
            "Resultado": "" if m.home_score is None or m.away_score is None else f"{m.home_score}-{m.away_score}",
        }
        for m in matches
    ])


def _admin_import(user: dict, season, competitions) -> None:
    st.markdown("### Importar calendario completo")
    st.caption("Pega toda la liga. No hace falta conocer todavía la hora. Una sola confirmación crea o actualiza los partidos.")
    if not competitions:
        st.warning("Crea primero la competición en Base de datos.")
        return
    comp_id = st.selectbox("Competición", [c.id for c in competitions], format_func=lambda cid: next(c.name for c in competitions if c.id == cid), key="cal_import_comp")
    example = "1;15-16/08/2026;La Bañeza;Laguna\n1;15-16/08/2026;No Name;Benavente\n2;22/08/2026;18:00;Laguna;No Name"
    raw = st.text_area("Calendario", height=220, placeholder=example, help="Formatos: jornada;fin de semana;local;visitante o jornada;fecha;hora;local;visitante")
    parsed, errors = parse_calendar_text(raw, default_year=season.start_date.year if season and season.start_date else date.today().year) if raw.strip() else ([], [])
    if parsed:
        st.dataframe(pd.DataFrame([{**r, "kickoff_at": r["kickoff_at"] or "Pendiente"} for r in parsed]), use_container_width=True, hide_index=True)
    if errors:
        st.error("Hay líneas que no se pueden importar.")
        for err in errors[:20]:
            st.write(f"- {err}")
    if st.button(f"Importar {len(parsed)} partidos", type="primary", disabled=not parsed or bool(errors), use_container_width=True):
        try:
            with session_scope() as session:
                result = calendar_repo.import_fixtures(session, season_id=season.id, competition_id=comp_id, rows=parsed, actor_id=user["id"])
            st.success(f"Calendario sincronizado: {result['created']} creados · {result['updated']} actualizados.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _admin_schedule(user: dict, season) -> None:
    with session_scope() as session:
        issues = calendar_repo.schedule_issues(session, season_id=season.id, horizon_days=60)
    st.markdown("### Incidencias de horario")
    if not issues:
        st.success("No hay horarios próximos pendientes de confirmar.")
        return
    for issue in issues:
        m = issue["match"]
        with st.container(border=True):
            a, b = st.columns([3, 1])
            a.markdown(f"**{_match_title(m)}**")
            a.caption(calendar_repo.schedule_label(m))
            b.metric("Prioridad", issue["urgency"])
            with st.form(f"schedule_{m.id}"):
                d1, d2, d3 = st.columns(3)
                definitive_date = d1.date_input("Fecha", value=m.match_date, key=f"date_{m.id}")
                has_time = d2.checkbox("Hora confirmada", value=bool(m.kickoff_at), key=f"has_time_{m.id}")
                kickoff_time = d2.time_input("Hora", value=m.kickoff_at.time() if m.kickoff_at else time(17, 0), disabled=not has_time, key=f"time_{m.id}")
                venue = d3.text_input("Campo", value=m.venue or "", key=f"venue_{m.id}")
                save = st.form_submit_button("Confirmar programación", type="primary")
            if save:
                with session_scope() as session:
                    calendar_repo.update_schedule(
                        session, m.id, user["id"], definitive_date=definitive_date,
                        kickoff_at=datetime.combine(definitive_date, kickoff_time) if has_time else None,
                        schedule_status="date_confirmed" if not has_time else "confirmed", venue=venue,
                    )
                st.success("Horario actualizado.")
                st.rerun()


def _mission_form(user: dict, match) -> None:
    with session_scope() as session:
        scouts = planning_repo.list_scout_users(session)
        roster_home = repo.get_roster(session, match.home_team_id, match.season_id)
        roster_away = repo.get_roster(session, match.away_team_id, match.season_id)
    if not scouts:
        st.warning("No hay usuarios con perfil Scout.")
        return
    players = {r.player.id: r.player for r in roster_home + roster_away}
    with st.form(f"mission_{match.id}"):
        mission_type = st.selectbox("Tipo de tarea", list(SCOUT_MISSION_TYPES), format_func=lambda x: SCOUT_MISSION_TYPES[x])
        assigned = st.selectbox("Scout", [u.id for u in scouts], format_func=lambda uid: next(u.full_name for u in scouts if u.id == uid))
        target_team = st.selectbox("Equipo foco", [None, match.home_team_id, match.away_team_id], format_func=lambda tid: "Sin equipo único" if tid is None else (match.home_team.name if tid == match.home_team_id else match.away_team.name))
        player_ids = st.multiselect("Jugadores objetivo", list(players), format_func=lambda pid: players[pid].display_name or players[pid].full_name, help="Opcional para análisis de equipo/rival.")
        title = st.text_input("Título", value=f"{SCOUT_MISSION_TYPES[mission_type]} · {match.home_team.name} - {match.away_team.name}")
        purpose = st.text_area("Motivo / qué queremos resolver", height=80)
        focus_text = st.text_input("Focos", placeholder="juego de espaldas; profundidad; presión")
        priority = st.select_slider("Prioridad", options=[3, 2, 1], value=2, format_func=lambda x: {1:"Alta",2:"Media",3:"Normal"}[x])
        save = st.form_submit_button("Asignar observación", type="primary")
    if save:
        focus = [x.strip() for x in focus_text.split(";") if x.strip()]
        with session_scope() as session:
            planning_repo.create_mission(
                session, match_id=match.id, mission_type=mission_type, title=title, assigned_to=assigned,
                requested_by=user["id"], target_team_id=target_team, player_ids=player_ids, purpose=purpose,
                focus=focus, priority=priority, due_at=match.kickoff_at,
            )
        st.success("Tarea de scouting creada y vinculada a este partido.")
        st.rerun()


def _calendar_actions(user: dict, match, own_id: int | None) -> None:
    with st.expander(f"Abrir · {_match_title(match)}", expanded=False):
        st.caption(calendar_repo.schedule_label(match))
        if user["role"] == "admin" and _is_own(match, own_id):
            if st.button("Preparar postpartido desde este partido", key=f"prepare_{match.id}", use_container_width=True):
                st.session_state["postmatch_existing_match_id"] = match.id
                st.session_state["main_navigation"] = "Nuevo postpartido"
                st.rerun()
        if user["role"] in {"director", "admin"}:
            with session_scope() as session:
                existing_missions = planning_repo.list_missions(session, match_id=match.id, limit=50)
            if existing_missions:
                st.markdown("**Tareas ya vinculadas**")
                st.dataframe(pd.DataFrame([{
                    "Scout": m.assignee.full_name, "Tipo": SCOUT_MISSION_TYPES.get(m.mission_type,m.mission_type),
                    "Estado": m.status, "Objetivo": m.title, "Resultado": m.result_summary or "",
                } for m in existing_missions]), hide_index=True, use_container_width=True)
            _mission_form(user, match)
        if user["role"] == "scout":
            if st.button("Observar este partido", key=f"observe_{match.id}", type="primary", use_container_width=True):
                st.session_state["scout_match_id"] = match.id
                st.session_state["main_navigation"] = "Misiones"
                st.rerun()


def render(user: dict) -> None:
    page_header("Calendario de la liga", "Toda la competición en un único lugar: horarios, partidos de No Name y planificación de scouting.")
    with session_scope() as session:
        active = repo.get_active_season(session)
        seasons = repo.list_seasons(session, active_only=True)
        competitions = repo.list_competitions(session, active_only=True)
        own = repo.get_own_team(session)
    if not active or not seasons:
        st.warning("No hay temporada activa.")
        return
    season_id = st.selectbox("Temporada", [s.id for s in seasons], index=next((i for i,s in enumerate(seasons) if s.id == active.id),0), format_func=lambda sid: next(s.name for s in seasons if s.id == sid), key="calendar_season")
    season = next(s for s in seasons if s.id == season_id)
    comp_options = [None] + [c.id for c in competitions]
    comp_id = st.selectbox("Competición", comp_options, format_func=lambda cid: "Todas" if cid is None else next(c.name for c in competitions if c.id == cid), key="calendar_comp")
    own_only = user["role"] == "reporter"
    if user["role"] != "reporter":
        own_only = st.toggle("Solo partidos de No Name", value=False, key="calendar_own_only")
    with session_scope() as session:
        matches = calendar_repo.list_calendar(session, season_id=season_id, competition_id=comp_id, team_id=own.id if own_only and own else None, limit=600)
    if user["role"] == "admin":
        mode = st.radio("Herramienta", ["Calendario", "Importar", "Horarios pendientes"], horizontal=True, key="calendar_admin_mode")
        if mode == "Importar":
            _admin_import(user, season, competitions); return
        if mode == "Horarios pendientes":
            _admin_schedule(user, season); return
    if not matches:
        st.info("Todavía no hay partidos cargados para estos filtros.")
        return
    st.dataframe(_fixture_table(matches, own.id if own else None), use_container_width=True, hide_index=True)
    st.markdown("### Abrir partido")
    # Show future first, but keep the whole season available.
    ordered = sorted(matches, key=lambda m: (m.match_date < date.today(), m.kickoff_at or datetime.combine(m.match_date, time(23,59))))
    for match in ordered[:80]:
        _calendar_actions(user, match, own.id if own else None)
