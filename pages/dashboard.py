from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from core.constants import ASSIGNMENT_STATUSES, REPORT_STATUSES
from core.database import session_scope
from core.utils import safe_html
from repositories import scouting as repo
from ui.styles import page_header


def _navigate(label: str, match_id: int | None = None) -> None:
    if match_id is not None:
        st.session_state["report_selected_match_id"] = match_id
    st.session_state["main_navigation"] = label


def _match_title(match) -> str:
    score = "-" if match.home_score is None or match.away_score is None else f"{match.home_score}-{match.away_score}"
    return f"{match.home_team.name} · {score} · {match.away_team.name}"


def _reporter_dashboard(user: dict) -> None:
    page_header("Mi panel", "Tus partidos asignados y el estado de tus informes.")
    with session_scope() as session:
        assignments = repo.list_assignments(session, user_id=user["id"])
        reports = repo.list_reports(session, reporter_id=user["id"], limit=20)

    status_counts = {
        "pending": len([a for a in assignments if a.status in {"pending", "returned"}]),
        "in_progress": len([a for a in assignments if a.status == "in_progress"]),
        "submitted": len([r for r in reports if r.status == "submitted"]),
        "approved": len([r for r in reports if r.status in {"approved", "final"}]),
    }
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [
        ("Pendientes", status_counts["pending"]),
        ("En curso", status_counts["in_progress"]),
        ("Entregados", status_counts["submitted"]),
        ("Aprobados", status_counts["approved"]),
    ]):
        col.metric(label, value)

    work = [a for a in assignments if a.status in {"pending", "in_progress", "returned"}]
    work.sort(key=lambda a: (a.due_at is None, a.due_at or datetime.max, a.match.match_date))
    st.subheader("Qué tienes que hacer")
    if not work:
        st.success("No tienes informes pendientes.")
    else:
        for assignment in work:
            with st.container(border=True):
                left, action = st.columns([4, 1])
                with left:
                    st.markdown(f"**{safe_html(_match_title(assignment.match))}**", unsafe_allow_html=True)
                    due = assignment.due_at.strftime("%d/%m/%Y %H:%M") if assignment.due_at else "Sin fecha límite"
                    st.caption(
                        f"{assignment.match.competition.name} · {assignment.match.round_name} · "
                        f"{assignment.match.match_date.strftime('%d/%m/%Y')} · "
                        f"{ASSIGNMENT_STATUSES.get(assignment.status, assignment.status)} · {due}"
                    )
                action.button(
                    "Continuar" if assignment.status in {"in_progress", "returned"} else "Empezar",
                    type="primary",
                    use_container_width=True,
                    key=f"dashboard_assignment_{assignment.id}",
                    on_click=_navigate,
                    args=("Hacer informe", assignment.match_id),
                )

    st.subheader("Tus últimos informes")
    if not reports:
        st.info("Todavía no has iniciado ningún informe.")
    else:
        rows = [{
            "Partido": f"{r.match.home_team.name} - {r.match.away_team.name}",
            "Fecha": r.match.match_date,
            "Estado": REPORT_STATUSES.get(r.status, r.status),
            "Versión": f"V{r.version}",
            "Último cambio": r.updated_at,
        } for r in reports[:8]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.button("Abrir mis informes", use_container_width=True, on_click=_navigate, args=("Mis informes",))


def _director_dashboard(user: dict) -> None:
    page_header("Panel de dirección", "Informes por revisar, jugadores observados y seguimientos activos.")
    with session_scope() as session:
        submitted = repo.list_reports(session, status="submitted", limit=30)
        approved = repo.list_reports(session, status="approved", limit=30)
        rankings = repo.player_rankings(session, min_observations=1, limit=8)
        follow_ups = repo.list_follow_ups(session)
        counts = repo.dashboard_counts(session)

    active_followups = [f for f in follow_ups if f.status not in {"Descartado", "Cerrado"}]
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [
        ("Pendientes de revisión", len(submitted)),
        ("Informes aprobados", len(approved)),
        ("Rivales observados", counts["players_observed"]),
        ("Seguimientos activos", len(active_followups)),
    ]):
        col.metric(label, value)

    st.subheader("Informes que necesitan revisión")
    if not submitted:
        st.success("No hay informes pendientes de revisión.")
    else:
        for report in submitted[:6]:
            with st.container(border=True):
                left, action = st.columns([4, 1])
                left.markdown(f"**{safe_html(report.match.home_team.name)} - {safe_html(report.match.away_team.name)}**", unsafe_allow_html=True)
                left.caption(f"{report.reporter.full_name} · {report.match.match_date.strftime('%d/%m/%Y')} · V{report.version}")
                action.button("Revisar", type="primary", use_container_width=True, key=f"review_{report.id}", on_click=_navigate, args=("Revisar y analizar",))

    st.subheader("Jugadores mejor valorados")
    if not rankings:
        st.info("Aparecerán cuando se aprueben evaluaciones rivales.")
    else:
        frame = pd.DataFrame([{
            "Jugador": row["full_name"],
            "Posición": row["primary_position"] or "-",
            "Observaciones": row["observations"],
            "Nota media": round(row["avg_general"], 2),
            "Informadores": row["reporter_count"],
            "Última observación": row["last_observed"],
        } for row in rankings])
        st.dataframe(frame, use_container_width=True, hide_index=True)
        st.button("Abrir dirección deportiva", use_container_width=True, on_click=_navigate, args=("Revisar y analizar",))


def _admin_dashboard(user: dict) -> None:
    page_header("Panel de administración", "Control de usuarios, partidos, asignaciones y estado general de la aplicación.")
    with session_scope() as session:
        counts = repo.dashboard_counts(session)
        users = repo.list_users(session, active_only=True)
        matches = repo.list_matches(session, limit=8)
        reports = repo.list_reports(session, limit=8)

    cols = st.columns(4)
    for col, (label, value) in zip(cols, [
        ("Partidos publicados", counts["published_matches"]),
        ("Usuarios activos", len(users)),
        ("Asignaciones pendientes", counts["pending_assignments"]),
        ("Informes aprobados", counts["final_reports"]),
    ]):
        col.metric(label, value)

    st.subheader("Acciones rápidas")
    actions = st.columns(4)
    actions[0].button("Gestionar partidos", use_container_width=True, on_click=_navigate, args=("Partidos",))
    actions[1].button("Base de datos", use_container_width=True, on_click=_navigate, args=("Base de datos",))
    actions[2].button("Usuarios y ajustes", use_container_width=True, on_click=_navigate, args=("Administración",))
    actions[3].button("Dirección deportiva", use_container_width=True, on_click=_navigate, args=("Dirección deportiva",))

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Partidos recientes")
        if not matches:
            st.info("No hay partidos creados.")
        for match in matches:
            with st.container(border=True):
                st.markdown(f"**{safe_html(_match_title(match))}**", unsafe_allow_html=True)
                st.caption(f"{match.competition.name} · {match.round_name} · {match.match_date.strftime('%d/%m/%Y')} · {match.status}")
    with right:
        st.subheader("Últimos informes")
        if not reports:
            st.info("No hay informes.")
        for report in reports:
            with st.container(border=True):
                st.markdown(f"**{safe_html(report.match.home_team.name)} - {safe_html(report.match.away_team.name)}**", unsafe_allow_html=True)
                st.caption(f"{report.reporter.full_name} · {REPORT_STATUSES.get(report.status, report.status)} · V{report.version}")


def render(user: dict) -> None:
    if user["role"] == "admin":
        _admin_dashboard(user)
    elif user["role"] == "director":
        _director_dashboard(user)
    else:
        _reporter_dashboard(user)
