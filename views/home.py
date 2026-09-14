from __future__ import annotations

import streamlit as st

from core.database import session_scope
from core.permissions import roles_for, can_direct
from core.presentation import status_badge
from core.schedule import is_schedule_confirmed
from repositories import calendar as calendar_repo
from repositories import workspaces
from ui.styles import page_header


def _open_match(match_id: int) -> None:
    st.session_state["workspace_match_id"] = int(match_id)
    st.session_state["main_navigation"] = "Jornada"
    st.rerun()


def render(user: dict) -> None:
    page_header("Inicio", "Lo que requiere tu atención ahora.")
    with session_scope() as session:
        data = workspaces.load_home_workspace(session, user_id=user["id"], roles=roles_for(user))

    match = data.get("next_match")
    if match:
        matchday = bool(data.get("is_matchday"))
        st.markdown("### Partido de hoy" if matchday else "### Próximo partido")
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{match.round_name} · {match.home_team.name} - {match.away_team.name}**")
            schedule = calendar_repo.schedule_label(match)
            if matchday:
                c1.caption(f"HOY · {schedule}")
            else:
                c1.caption(schedule)
            if match.home_score is not None and match.away_score is not None:
                c1.markdown(status_badge("ready", f"Resultado {match.home_score}-{match.away_score}"))
            elif not is_schedule_confirmed(match):
                c1.markdown(status_badge("action" if matchday else "pending", "Horario pendiente"))
            else:
                c1.markdown(status_badge("ready", "Partido operativo"))
            if c2.button("Abrir partido", type="primary", use_container_width=True, key=f"home_match_{match.id}"):
                _open_match(match.id)
    else:
        st.info("No hay un próximo partido de No Name en la temporada activa.")

    st.markdown("### Tus tareas")
    tasks = data.get("tasks") or []
    if not tasks:
        st.success("No tienes acciones pendientes.")
    for i, task in enumerate(tasks[:12]):
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"{status_badge(task['severity'], task['title'])}")
            due = task.get("due")
            if due:
                c1.caption(f"Fecha objetivo: {due.strftime('%d/%m/%Y · %H:%M') if hasattr(due, 'hour') else due.strftime('%d/%m/%Y')}")
            if task.get("match_id") and c2.button("Abrir", use_container_width=True, key=f"home_task_{i}_{task['match_id']}"):
                _open_match(task["match_id"])

    if can_direct(user):
        dd = data.get("director") or {}
        actionable = []
        if dd.get("decision_count"):
            actionable.append(f"{dd['decision_count']} jugadores requieren decisión")
        if dd.get("high_needs"):
            actionable.append(f"{dd['high_needs']} necesidades altas")
        if dd.get("new_scout"):
            actionable.append(f"{dd['new_scout']} observaciones Scout disponibles")
        if actionable:
            st.markdown("### Dirección Deportiva")
            with st.container(border=True):
                for text in actionable:
                    st.markdown(f"- {text}")
                if st.button("Abrir jugadores", use_container_width=True, key="home_to_players"):
                    st.session_state["main_navigation"] = "Jugadores"
                    st.rerun()
