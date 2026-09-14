from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from core.constants import ASSIGNMENT_STATUSES, REPORT_STATUSES
from core.database import session_scope
from core.utils import safe_html
from repositories import scouting as repo
from repositories import calendar as calendar_repo
from repositories import planning as planning_repo
from repositories import league_intelligence as league_repo
from ui.styles import page_header


def _navigate(label: str, match_id: int | None = None) -> None:
    if match_id is not None:
        st.session_state["report_selected_match_id"] = match_id
    st.session_state["main_navigation"] = label


def _open_schedule_issues() -> None:
    st.session_state["calendar_admin_mode"] = "Horarios pendientes"
    st.session_state["main_navigation"] = "Calendario"


def _continue_postmatch_draft(draft_id: int) -> None:
    st.session_state["postmatch_open_cloud_draft_id"] = int(draft_id)
    st.session_state["main_navigation"] = "Nuevo postpartido"


def _open_director_player(player_id: int) -> None:
    st.session_state["director_player_id"] = int(player_id)
    st.session_state["director_section"] = "Jugadores"
    st.session_state["main_navigation"] = "Revisar y decidir"


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
    page_header("Inicio · Dirección deportiva", "Nuestra liga, resumida en decisiones: qué revisar, quién destaca y a quién volver a ver.")
    with session_scope() as session:
        active = repo.get_active_season(session)
        season_id = active.id if active else None
        metrics = repo.league_panorama(session, season_id=season_id)
        queue = league_repo.enhanced_decision_queue(session, season_id=season_id, limit=5)
        highlights = repo.recent_rival_highlights(session, limit=6, minimum_rating=8.0)
        trends = league_repo.robust_trends(session, season_id=season_id, min_observations=4, limit=5)

    st.caption(f"{active.name if active else 'Todas las temporadas'} · solo información generada en nuestra competición")
    cols = st.columns(5)
    cols[0].metric("Jugadores vistos", metrics["players_observed"])
    cols[1].metric("2+ observaciones", metrics["players_repeated"])
    cols[2].metric("Seguimiento", metrics["followups_active"])
    cols[3].metric("Prioritarios", metrics["priority_players"])
    cols[4].metric("Por revisar", metrics["reports_pending_review"])

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Necesitan una decisión")
        if not queue:
            st.success("No hay perfiles con muestra suficiente esperando decisión.")
        for row in queue:
            with st.container(border=True):
                a, b, c = st.columns([3.4, 1, 1.15])
                a.markdown(f"**{safe_html(row['full_name'])}** · {safe_html(row.get('team_name') or '-')}", unsafe_allow_html=True)
                a.caption(f"{row.get('primary_position') or '-'} · {row['observations']} obs. · confianza {row['confidence']} · {'; '.join(row.get('reasons', [])[:2])}")
                b.metric("Media", f"{row['avg_general']:.2f}")
                c.button(
                    "Abrir", use_container_width=True, key=f"director_open_{row['player_id']}",
                    on_click=_open_director_player, args=(int(row["player_id"]),),
                )
        st.button("Abrir bandeja de decisión", type="primary", use_container_width=True, on_click=_navigate, args=("Revisar y decidir",))
    with right:
        st.subheader("Destacados recientes")
        if not highlights:
            st.info("Aparecerán cuando existan informes aprobados con notas ≥ 8.")
        else:
            st.dataframe(pd.DataFrame([{
                "Jugador": x["player"].full_name,
                "Nota": x["evaluation"].general_rating,
                "Partido": f"{x['match'].home_team.name} - {x['match'].away_team.name}",
            } for x in highlights]), use_container_width=True, hide_index=True)

    st.subheader("En evolución")
    if not trends:
        st.caption("Se activará cuando tengamos al menos cuatro observaciones del mismo jugador.")
    else:
        st.dataframe(pd.DataFrame([{
            "Jugador": r["full_name"], "Obs.": r["observations"],
            "Media inicial": round(r["early_average"],2), "Media reciente": round(r["recent_average"],2), "Cambio": round(r["delta"], 2),
        } for r in trends]), use_container_width=True, hide_index=True)


def _scout_dashboard(user: dict) -> None:
    page_header("Inicio · Scout", "Tu jornada: partidos disponibles, tareas de Dirección Deportiva y observaciones por completar.")
    with session_scope() as session:
        active = repo.get_active_season(session)
        missions = planning_repo.list_missions(session, assigned_to=user["id"], limit=100)
        observations = planning_repo.list_observations(session, reviewer_id=user["id"], limit=100)
        fixtures = calendar_repo.list_calendar(session, season_id=active.id if active else None, date_from=datetime.now().date(), limit=40)
    pending=[m for m in missions if m.status in {"pending","in_progress"}]
    a,b,c=st.columns(3)
    a.metric("Misiones pendientes",len(pending)); b.metric("Observaciones entregadas",len([o for o in observations if o.status=="submitted"])); c.metric("Partidos próximos",len(fixtures))
    unscheduled = [m for m in pending if getattr(m.match, "schedule_status", None) != "confirmed"]
    if unscheduled:
        st.warning(f"{len(unscheduled)} tareas asignadas todavía no tienen horario exacto. Se actualizarán automáticamente cuando Administración confirme el calendario.")
    if pending:
        st.subheader("Prioridad de esta jornada")
        for m in pending[:5]:
            with st.container(border=True):
                x,y=st.columns([4,1])
                x.markdown(f"**{m.title}**")
                x.caption(f"{m.match.home_team.name} - {m.match.away_team.name} · {calendar_repo.schedule_label(m.match)}")
                y.button("Abrir",key=f"scout_dash_{m.id}",use_container_width=True,on_click=_navigate,args=("Misiones",))
    else:
        st.success("No tienes observaciones asignadas pendientes.")
    st.subheader("Partidos disponibles")
    for m in fixtures[:6]:
        st.caption(f"{m.round_name} · {m.home_team.name} - {m.away_team.name} · {calendar_repo.schedule_label(m)}")
    st.button("Abrir calendario completo",use_container_width=True,on_click=_navigate,args=("Calendario de liga",))


def _admin_dashboard(user: dict) -> None:
    with session_scope() as session:
        own_team = repo.get_own_team(session)
        active_season = repo.get_active_season(session)
        counts = repo.dashboard_counts(session)
        matches = repo.list_matches(session, limit=8)
        submitted = repo.list_reports(session, status="submitted", limit=20)
        users = repo.list_users(session, active_only=True)
        drafts = repo.list_postmatch_drafts(session, user["id"], limit=5)
        progress_by_match = repo.assignment_progress_many(session, [m.id for m in matches])
        schedule_issues = calendar_repo.schedule_issues(session, season_id=active_season.id if active_season else None, horizon_days=21)

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

    if drafts:
        latest_draft = drafts[0]
        with st.container(border=True):
            left, action = st.columns([4, 1.25])
            left.markdown("**Borrador pendiente**")
            left.write(latest_draft.title or "Postpartido sin título")
            left.caption(f"Último guardado: {latest_draft.updated_at.strftime('%d/%m/%Y %H:%M')}")
            action.button(
                "Continuar", type="secondary", use_container_width=True,
                key=f"continue_cloud_draft_{latest_draft.id}",
                on_click=_continue_postmatch_draft, args=(int(latest_draft.id),),
            )

    if schedule_issues:
        urgent = [x for x in schedule_issues if x["urgency"] == "Urgente"]
        with st.container(border=True):
            left, action = st.columns([4,1.2])
            left.markdown(f"**Horarios por confirmar: {len(schedule_issues)}**")
            left.caption(f"{len(urgent)} próximos en menos de 7 días" if urgent else "Sin urgencias de menos de 7 días")
            action.button("Resolver", use_container_width=True, on_click=_open_schedule_issues)

    cols = st.columns(4)
    cols[0].metric("Partidos publicados", counts["published_matches"])
    cols[1].metric("Informes por revisar", len(submitted))
    cols[2].metric("Jugadores rivales observados", counts["players_observed"])
    cols[3].metric("Usuarios activos", len(users))
    if drafts:
        st.caption(f"Tienes {len(drafts)} borrador{'es' if len(drafts) != 1 else ''} de postpartido guardado{'s' if len(drafts) != 1 else ''} en la nube.")

    st.subheader("Partidos recientes")
    if not matches:
        st.info("Todavía no hay partidos. Pulsa Nuevo postpartido para empezar.")
    else:
        for match in matches:
            progress = progress_by_match.get(match.id, {"total": 0, "submitted": 0, "approved": 0})
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
    elif user["role"] == "scout":
        _scout_dashboard(user)
    else:
        _reporter_dashboard(user)
