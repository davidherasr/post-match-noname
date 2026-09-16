"""Role-aware operational workspace: actions before informative statistics."""
from __future__ import annotations

import streamlit as st

from core.database import session_scope
from core.navigation import request_navigation
from core.permissions import roles_for, can_direct
from core.schedule import is_schedule_confirmed
from core.presentation import status_badge
from repositories import calendar as calendar_repo
from repositories import workspaces
from repositories import tracking as tracking_repo
from ui.styles import page_header


def _open_match(match_id: int) -> None:
    st.session_state["workspace_match_id"] = int(match_id)
    st.session_state.pop("match_hub_mode", None)
    request_navigation("Jornada")
    st.rerun()


def _open_report(match_id: int) -> None:
    st.session_state["workspace_match_id"] = int(match_id)
    st.session_state["match_hub_mode"] = "report"
    request_navigation("Jornada")
    st.rerun()


def _open_director_reading() -> None:
    st.session_state["dd_area_42"] = "Lectura deportiva"
    st.session_state["dd_reading_area_421"] = "Jugadores señalados"
    request_navigation("Dirección Deportiva")
    st.rerun()


def _fixture_card(match, *, label: str, progress: dict, key: str, primary: bool) -> None:
    with st.container(border=True):
        st.caption(label.upper())
        st.markdown(f"**{match.home_team.name} – {match.away_team.name}**")
        st.caption(f"{match.round_name} · {calendar_repo.schedule_label(match)}")
        if match.home_score is not None and match.away_score is not None:
            st.markdown(f"**Resultado: {match.home_score} – {match.away_score}**")
        elif not is_schedule_confirmed(match):
            st.caption("Horario por confirmar")
        if match.status == "published":
            assigned = progress.get("assigned", 0)
            finished = progress.get("incorporated", 0)
            st.caption(f"Informes incorporados: {finished}/{assigned}" if assigned else "Postpartido sin Informadores asignados")
        elif label == "Último partido":
            st.caption("Postpartido pendiente de preparar")
        if st.button("Abrir partido", type="primary" if primary else "secondary",
                     use_container_width=True, key=key):
            _open_match(match.id)


def _task_action(task: dict) -> str:
    return {
        "report": "Rellenar informe", "prepare": "Preparar partido",
        "assign": "Asignar Informadores", "schedule": "Confirmar horario",
    }.get(task.get("kind"), "Abrir partido")


def render(user: dict) -> None:
    page_header("Inicio", "Tu trabajo y la actividad deportiva del club.")
    declined = st.session_state.pop("assignment_declined_notice", None)
    if declined:
        st.success(declined)
    delivered = st.session_state.pop("report_submission_notice", None)
    if delivered:
        st.success(f"Informe de {delivered['title']} entregado e incorporado correctamente.")
        if st.button("Consultar el partido", key="submitted_report_match_441", use_container_width=True):
            _open_match(int(delivered["match_id"]))
    tracked = st.session_state.pop("tracking_saved_notice_442", None)
    if tracked:
        st.success(tracked)
    roles = roles_for(user)
    with session_scope() as session:
        data = workspaces.load_home_workspace(session, user_id=user["id"], roles=roles)
        received_requests = []
        if "reporter" in roles and data.get("active_season"):
            from repositories import observation_requests as requests_repo
            received_requests = requests_repo.list_requests(session,
                season_id=data["active_season"].id, reporter_id=user["id"], active_only=True)

    st.markdown("### Mi trabajo")
    tasks = data.get("tasks") or []
    if not data.get("active_season"):
        st.warning("No hay una temporada activa. Administración debe seleccionarla.")
    elif not data.get("own_team"):
        st.warning("No se ha configurado el equipo propio. Administración debe seleccionarlo.")
    elif not tasks:
        if received_requests:
            st.caption(f"Sin postpartidos asignados pendientes; tienes {len(received_requests)} petición(es) voluntaria(s) de DD debajo.")
        else:
            st.info("No se han encontrado tareas pendientes para tus permisos en la temporada activa.")
    else:
        st.caption(f"{data.get('task_count', len(tasks))} tareas pendientes · Se muestran primero las que requieren atención.")
        visible_limit = 1
        if len(tasks) > visible_limit:
            show_all = st.checkbox(f"Mostrar otras {len(tasks)-visible_limit} tareas", key="home_all_tasks_44")
        else:
            show_all = True
        for i, task in enumerate(tasks if show_all else tasks[:visible_limit]):
            with st.container(border=True):
                # Use a vertical action layout that remains usable on narrow screens.
                st.caption(task.get("role", "Trabajo"))
                st.markdown(f"**{status_badge(task['severity'], task['title'])}**")
                due = task.get("due")
                if due:
                    st.caption("Fecha: " + (due.strftime("%d/%m/%Y · %H:%M") if hasattr(due, "hour") else due.strftime("%d/%m/%Y")))
                if task.get("match_id") and st.button(_task_action(task), use_container_width=True,
                                                      type="primary" if i == 0 else "secondary",
                                                      key=f"home_task44_{i}_{task['match_id']}"):
                    if task.get("kind") == "report":
                        _open_report(task["match_id"])
                    else:
                        _open_match(task["match_id"])
                if task.get("kind") == "report" and task.get("match_id"):
                    from views.reports import render_decline_control
                    render_decline_control(user, task["match_id"],
                                           key_prefix=f"home_441_{task['match_id']}")

    if data.get("active_season") and "reporter" in roles:
        from views.observation_requests import reporter_inbox
        reporter_inbox(user, data["active_season"].id, compact=True)

    st.markdown("### Partidos de No Name")
    last_match = data.get("last_match")
    next_match = data.get("next_match")
    if last_match is None and next_match is None:
        st.info("Todavía no hay partidos oficiales para mostrar en esta temporada.")
    else:
        if last_match:
            _fixture_card(last_match, label="Último partido",
                          progress=data.get("match_progress", {}).get(last_match.id, {}),
                          key=f"home_last44_{last_match.id}", primary=False)
        if next_match and (not last_match or next_match.id != last_match.id):
            _fixture_card(next_match, label="Partido de hoy" if data.get("is_matchday") else "Próximo partido",
                          progress=data.get("match_progress", {}).get(next_match.id, {}),
                          key=f"home_next44_{next_match.id}", primary=False)

    if can_direct(user):
        from views.observation_requests import director_board
        if data.get("active_season"):
            director_board(user, data["active_season"].id, compact=True)
        dd = data.get("director") or {}
        st.markdown("### Actividad para Dirección Deportiva")
        a, b, c = st.columns(3)
        a.metric("Jugadores señalados", dd.get("neutral_signals", 0), help="Solo partidos oficiales de la temporada activa.")
        b.metric("Necesidades altas", dd.get("high_needs", 0))
        c.metric("Jugadores en evaluación", dd.get("decision_count", 0))
        tracking_events = []
        if data.get("active_season"):
            with session_scope() as session:
                tracking_events = tracking_repo.tracking_activity(session, data["active_season"].id, limit=4)
        with st.container(border=True):
            st.markdown("**Seguimientos recientes**")
            if not tracking_events:
                st.caption("Todavía no hay seguimientos individuales registrados en la temporada.")
            for event in tracking_events:
                obs, person, author = event["observation"], event["player"], event["author"]
                name = person.display_name or person.full_name
                action = "amplió el postpartido con seguimiento de" if obs.player_evaluation_id else "registró seguimiento de"
                st.write(f"{author.full_name} {action} **{name}**")
                st.caption(f"{event['match'].home_team.name} – {event['match'].away_team.name}")
            if st.button("Ver seguimiento y decisiones", use_container_width=True, key="home_dd_tracking_442"):
                st.session_state["dd_area_42"] = "Seguimiento"
                request_navigation("Dirección Deportiva")
                st.rerun()
        recent_reports = dd.get("latest_reports") or []
        recent_neutral = dd.get("latest_neutral") or []
        with st.container(border=True):
            st.markdown("**Informes incorporados recientemente**")
            if not recent_reports:
                st.caption("Todavía no hay informes incorporados en la temporada.")
            for report in recent_reports:
                st.write(f"{report.match.home_team.name} – {report.match.away_team.name} · {report.reporter.full_name}")
                if st.button("Abrir informe en el partido", key=f"home_dd_report44_{report.id}", use_container_width=True):
                    _open_match(report.match_id)
        with st.container(border=True):
            st.markdown("**Lecturas neutrales recientes**")
            if not recent_neutral:
                st.caption("Todavía no hay lecturas neutrales en la temporada.")
            for opinion in recent_neutral:
                st.write(f"{opinion.match.home_team.name} – {opinion.match.away_team.name} · {opinion.user.full_name}")
                if st.button("Abrir partido", key=f"home_dd_neutral44_{opinion.id}", use_container_width=True):
                    _open_match(opinion.match_id)
        if st.button("Consultar inteligencia deportiva", key="home_dd_reading44", use_container_width=True):
            _open_director_reading()

    st.markdown("### Accesos rápidos")
    for destination in ("Jornada", "Jugadores"):
        if st.button(destination, key=f"home_shortcut44_{destination}", use_container_width=True):
            request_navigation(destination)
            st.rerun()
