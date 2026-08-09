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
    page_header("Inicio", "Entra, valora el partido y termina. No hay apartados generales obligatorios.")
    with session_scope() as session:
        assignments = repo.list_assignments(session, user_id=user["id"])
        reports = repo.list_reports(session, reporter_id=user["id"], limit=20)

    work = [a for a in assignments if a.status in {"pending", "in_progress", "returned"}]
    work.sort(key=lambda a: (a.due_at is None, a.due_at or datetime.max, a.match.match_date))

    if work:
        next_assignment = work[0]
        with st.container(border=True):
            st.markdown("### Tu siguiente informe")
            left, action = st.columns([4, 1.2])
            left.markdown(f"**{safe_html(_match_title(next_assignment.match))}**", unsafe_allow_html=True)
            due = next_assignment.due_at.strftime("%d/%m/%Y %H:%M") if next_assignment.due_at else "Sin fecha límite"
            left.caption(
                f"{next_assignment.match.competition.name} · {next_assignment.match.round_name} · "
                f"{next_assignment.match.match_date.strftime('%d/%m/%Y')} · {due}"
            )
            action.button(
                "Continuar" if next_assignment.status in {"in_progress", "returned"} else "Valorar",
                type="primary",
                use_container_width=True,
                key=f"dashboard_next_{next_assignment.id}",
                on_click=_navigate,
                args=("Valorar partido", next_assignment.match_id),
            )
    else:
        st.success("No tienes informes pendientes.")

    status_counts = {
        "pending": len(work),
        "submitted": len([r for r in reports if r.status == "submitted"]),
        "approved": len([r for r in reports if r.status in {"approved", "final"}]),
    }
    cols = st.columns(3)
    cols[0].metric("Pendientes", status_counts["pending"])
    cols[1].metric("Entregados", status_counts["submitted"])
    cols[2].metric("Aprobados", status_counts["approved"])

    if len(work) > 1:
        st.subheader("Después")
        for assignment in work[1:6]:
            with st.container(border=True):
                left, action = st.columns([4, 1])
                left.markdown(f"**{safe_html(_match_title(assignment.match))}**", unsafe_allow_html=True)
                left.caption(f"{assignment.match.round_name} · {ASSIGNMENT_STATUSES.get(assignment.status, assignment.status)}")
                action.button(
                    "Abrir",
                    use_container_width=True,
                    key=f"dashboard_assignment_{assignment.id}",
                    on_click=_navigate,
                    args=("Valorar partido", assignment.match_id),
                )

    st.subheader("Últimos informes")
    if not reports:
        st.info("Todavía no has iniciado ningún informe.")
    else:
        st.dataframe(pd.DataFrame([{
            "Partido": f"{r.match.home_team.name} - {r.match.away_team.name}",
            "Fecha": r.match.match_date,
            "Estado": REPORT_STATUSES.get(r.status, r.status),
            "Versión": f"V{r.version}",
        } for r in reports[:8]]), use_container_width=True, hide_index=True)


def _director_dashboard(user: dict) -> None:
    page_header("Inicio · Dirección deportiva", "Primero las decisiones: qué revisar y qué jugadores han llamado la atención.")
    with session_scope() as session:
        submitted = repo.list_reports(session, status="submitted", limit=20)
        highlights = repo.recent_rival_highlights(session, limit=10, minimum_rating=8.0)
        repeated = repo.player_rankings(session, min_observations=2, limit=8)
        follow_ups = repo.list_follow_ups(session)

    active_followups = [f for f in follow_ups if f.status not in {"Descartado", "Cerrado"}]
    cols = st.columns(3)
    cols[0].metric("Informes por revisar", len(submitted))
    cols[1].metric("Seguimientos activos", len(active_followups))
    cols[2].metric("Perfiles repetidos", len(repeated))

    if submitted:
        st.subheader("Necesita tu decisión")
        for report in submitted[:5]:
            with st.container(border=True):
                left, right = st.columns([4, 1])
                left.markdown(f"**{safe_html(report.match.home_team.name)} - {safe_html(report.match.away_team.name)}**", unsafe_allow_html=True)
                left.caption(f"{report.reporter.full_name} · {report.match.match_date.strftime('%d/%m/%Y')} · V{report.version}")
                right.button("Revisar", type="primary", use_container_width=True, key=f"review_{report.id}", on_click=_navigate, args=("Revisar y decidir",))
    else:
        st.success("No hay informes pendientes de revisión.")

    left, right = st.columns(2)
    with left:
        st.subheader("Últimas notas ≥ 8")
        if not highlights:
            st.info("Aparecerán cuando existan informes aprobados.")
        else:
            for item in highlights[:6]:
                ev, player, match = item["evaluation"], item["player"], item["match"]
                st.markdown(f"**{safe_html(player.full_name)} · {ev.general_rating:.1f}**", unsafe_allow_html=True)
                st.caption(f"{match.match_date.strftime('%d/%m/%Y')} · {match.home_team.name} - {match.away_team.name}")
    with right:
        st.subheader("Observados varias veces")
        if not repeated:
            st.info("Todavía no hay jugadores con varias observaciones aprobadas.")
        else:
            st.dataframe(pd.DataFrame([{
                "Jugador": r["full_name"],
                "Obs.": r["observations"],
                "Media": round(r["avg_general"], 2),
                "Última": r["last_observed"],
            } for r in repeated[:6]]), use_container_width=True, hide_index=True)
    st.button("Abrir dirección deportiva", type="primary", use_container_width=True, on_click=_navigate, args=("Revisar y decidir",))


def _admin_dashboard(user: dict) -> None:
    with session_scope() as session:
        own_team = repo.get_own_team(session)
        active_season = repo.get_active_season(session)
        counts = repo.dashboard_counts(session)
        matches = repo.list_matches(session, limit=8)
        submitted = repo.list_reports(session, status="submitted", limit=20)
        users = repo.list_users(session, active_only=True)

    club = own_team.name if own_team else "No Name"
    page_header(f"{club} · Administración", "Prepara el postpartido en una sola pantalla. La base de datos queda para mantenimiento.")

    with st.container(border=True):
        left, right = st.columns([3, 1.15])
        left.markdown("### Nuevo postpartido")
        if own_team:
            season_text = active_season.name if active_season else "sin temporada activa"
            left.write(f"Partido → alineación {club} → alineación rival → publicar. Temporada: **{season_text}**.")
        else:
            left.write("Configura No Name y prepara el primer partido sin salir del mismo flujo.")
        right.button("＋ NUEVO POSTPARTIDO", type="primary", use_container_width=True, on_click=_navigate, args=("Nuevo postpartido",))

    cols = st.columns(4)
    cols[0].metric("Partidos publicados", counts["published_matches"])
    cols[1].metric("Informes por revisar", len(submitted))
    cols[2].metric("Jugadores rivales observados", counts["players_observed"])
    cols[3].metric("Usuarios activos", len(users))

    st.subheader("Partidos recientes")
    if not matches:
        st.info("Todavía no hay partidos. Pulsa Nuevo postpartido para empezar.")
    else:
        for match in matches:
            with session_scope() as session:
                progress = repo.assignment_progress(session, match.id)
            with st.container(border=True):
                left, middle, action = st.columns([4, 1.3, 1.2])
                left.markdown(f"**{safe_html(_match_title(match))}**", unsafe_allow_html=True)
                left.caption(f"{match.competition.name} · {match.round_name} · {match.match_date.strftime('%d/%m/%Y')} · {match.status}")
                middle.metric("Informes", f"{progress.get('submitted', 0) + progress.get('approved', 0)}/{progress.get('total', 0)}")
                action.button("Abrir partidos", use_container_width=True, key=f"admin_match_{match.id}", on_click=_navigate, args=("Partidos",))

    with st.expander("Mantenimiento y configuración"):
        a, b, c = st.columns(3)
        a.button("Base de datos", use_container_width=True, on_click=_navigate, args=("Base de datos",))
        b.button("Usuarios y ajustes", use_container_width=True, on_click=_navigate, args=("Administración",))
        c.button("Dirección deportiva", use_container_width=True, on_click=_navigate, args=("Dirección deportiva",))


def render(user: dict) -> None:
    if user["role"] == "admin":
        _admin_dashboard(user)
    elif user["role"] == "director":
        _director_dashboard(user)
    else:
        _reporter_dashboard(user)
