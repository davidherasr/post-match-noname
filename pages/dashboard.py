from __future__ import annotations

import pandas as pd
import streamlit as st

from core.constants import ASSIGNMENT_STATUSES, REPORT_STATUSES
from core.database import session_scope
from core.utils import safe_html
from repositories import scouting as repo
from ui.styles import page_header


def render(user: dict) -> None:
    page_header("Inicio", "Resumen operativo, entregas pendientes y observaciones aprobadas.")
    with session_scope() as session:
        counts = repo.dashboard_counts(session, user["id"])
        recent_matches = repo.list_matches(session, limit=6)
        reports = repo.list_reports(session, reporter_id=None if user["role"] in {"admin", "director"} else user["id"], limit=6)
        rankings = repo.player_rankings(session, min_observations=1, limit=6)
        assignments = repo.list_assignments(session, user_id=user["id"])

    cols = st.columns(5)
    labels = [
        ("Partidos publicados", counts["published_matches"]),
        ("Asignaciones pendientes", counts["pending_assignments"]),
        ("Mis borradores", counts["draft_reports"]),
        ("Informes aprobados", counts["final_reports"]),
        ("Rivales observados", counts["players_observed"]),
    ]
    for col, (label, value) in zip(cols, labels):
        col.metric(label, value)

    pending = [a for a in assignments if a.status in {"pending", "in_progress", "returned"}]
    if pending:
        st.subheader("Trabajo pendiente")
        st.dataframe(pd.DataFrame([{
            "Partido": f"{a.match.home_team.name} - {a.match.away_team.name}",
            "Estado": ASSIGNMENT_STATUSES.get(a.status, a.status),
            "Fecha límite": a.due_at,
            "Obligatorio": a.required,
        } for a in pending]), use_container_width=True, hide_index=True)

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Partidos recientes")
        if not recent_matches:
            st.info("Todavía no hay partidos creados.")
        for match in recent_matches:
            score = "-" if match.home_score is None or match.away_score is None else f"{match.home_score}-{match.away_score}"
            with session_scope() as session:
                progress = repo.assignment_progress(session, match.id)
            st.markdown(
                f"""
                <div class="pm-card">
                  <div class="pm-kicker">{safe_html(match.competition.name)} · {safe_html(match.round_name)}</div>
                  <div class="pm-player-name">{safe_html(match.home_team.name)} · {score} · {safe_html(match.away_team.name)}</div>
                  <div class="pm-player-meta">{match.match_date.strftime('%d/%m/%Y')} · informes aprobados {progress['approved']}/{progress['total']}</div>
                </div>
                """, unsafe_allow_html=True,
            )
    with right:
        st.subheader("Últimos informes")
        if not reports:
            st.info("No hay informes todavía.")
        for report in reports:
            st.markdown(
                f"""
                <div class="pm-card">
                  <div class="pm-player-name">{safe_html(report.match.home_team.name)} - {safe_html(report.match.away_team.name)}</div>
                  <div class="pm-player-meta">{safe_html(report.reporter.full_name)} · {safe_html(REPORT_STATUSES.get(report.status, report.status))} · V{report.version}</div>
                </div>
                """, unsafe_allow_html=True,
            )

    st.subheader("Jugadores rivales mejor valorados · solo informes aprobados")
    if rankings:
        df = pd.DataFrame(rankings).rename(columns={
            "full_name": "Jugador", "primary_position": "Posición", "observations": "Observaciones",
            "avg_general": "Nota media", "rating_dispersion": "Dispersión", "standouts": "Destacados",
            "last_observed": "Última observación", "reporter_count": "Informadores",
        })
        for col in ["Nota media", "Dispersión"]:
            df[col] = df[col].round(2)
        st.dataframe(df[["Jugador", "Posición", "Observaciones", "Informadores", "Nota media", "Dispersión", "Destacados", "Última observación"]], use_container_width=True, hide_index=True)
    else:
        st.info("Las clasificaciones aparecerán cuando dirección deportiva apruebe los primeros informes.")
