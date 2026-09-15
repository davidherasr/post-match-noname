from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from core.navigation import request_navigation

from core.calendar_import import CALENDAR_PARSER_VERSION, parse_calendar_text
from core.clock import local_today
from core.constants import SCHEDULE_STATUSES
from core.database import session_scope
from core.schedule import is_schedule_confirmed
from core.permissions import can_admin, roles_for
from repositories import calendar as calendar_repo
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
    st.caption(f"Importador {CALENDAR_PARSER_VERSION} · una sola fecha orientativa por jornada. Sin rangos. La hora queda pendiente hasta que Administración la confirme.")
    if not competitions:
        st.warning("Crea primero la competición en Administración → Configuración.")
        return
    comp_id = st.selectbox("Competición", [c.id for c in competitions], format_func=lambda cid: next(c.name for c in competitions if c.id == cid), key="cal_import_comp")
    example = "1;13/09/2026;La Cistérniga C.F.;C.D. Noname\n1;13/09/2026;Otro local;Otro visitante\n8;01/11/2026;Otro equipo;C.D. Noname"
    uploaded = st.file_uploader("O cargar archivo TXT", type=["txt"], key="cal_import_txt")
    raw = st.text_area("Calendario", height=220, placeholder=example, help="Formato normal: jornada;fecha de jornada;local;visitante. Esa fecha es orientativa y NO confirma el día real. Si ya conoces el horario: jornada;fecha;hora;local;visitante.")
    source_text = raw
    if uploaded is not None:
        try:
            source_text = uploaded.getvalue().decode("utf-8-sig")
            st.info(f"TXT cargado: {uploaded.name}")
        except UnicodeDecodeError:
            st.error("El TXT no está en UTF-8. Guárdalo como UTF-8 y vuelve a cargarlo.")
            source_text = ""
    parsed, errors = parse_calendar_text(source_text, default_year=season.start_date.year if season and season.start_date else local_today().year) if source_text.strip() else ([], [])
    if source_text.strip():
        c1, c2 = st.columns(2)
        c1.metric("Partidos reconocidos", len(parsed))
        c2.metric("Errores", len(errors))
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
            st.success(f"Calendario sincronizado: {result['created']} creados · {result['updated']} actualizados. Los horarios ya confirmados se conservan si vuelves a importar el calendario.")
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
                st.caption("La fecha que vino del calendario es orientativa. Para activar informes/observaciones debes confirmar fecha y hora.")
                d1, d2, d3 = st.columns(3)
                definitive_date = d1.date_input("Fecha definitiva", value=m.kickoff_at.date() if m.kickoff_at else m.match_date, key=f"date_{m.id}")
                kickoff_text = d2.text_input(
                    "Hora definitiva (HH:MM)",
                    value=m.kickoff_at.strftime("%H:%M") if m.kickoff_at else "",
                    placeholder="Ej. 17:30",
                    key=f"time_{m.id}",
                )
                venue = d3.text_input("Campo", value=m.venue or "", key=f"venue_{m.id}")
                save = st.form_submit_button("Confirmar fecha y hora", type="primary")
            if save:
                try:
                    if not kickoff_text.strip():
                        raise ValueError("Escribe una hora real. La aplicación no propone ni guarda una hora por defecto.")
                    parsed_time = datetime.strptime(kickoff_text.strip(), "%H:%M").time()
                    with session_scope() as session:
                        calendar_repo.update_schedule(
                            session, m.id, user["id"],
                            kickoff_at=datetime.combine(definitive_date, parsed_time), venue=venue,
                        )
                    st.success("Fecha y hora confirmadas. El partido ya está operativo para informes y lecturas.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def _calendar_actions(user: dict, match, own_id: int | None) -> None:
    with st.expander(f"Abrir · {_match_title(match)}", expanded=False):
        st.caption(calendar_repo.schedule_label(match))
        own_match = _is_own(match, own_id)
        if own_match and not is_schedule_confirmed(match):
            st.warning("Horario pendiente: Administración debe confirmar fecha y hora antes del trabajo operativo.")
        label = "Abrir postpartido" if own_match else "Abrir lectura del partido"
        if st.button(label, key=f"open_calendar_{match.id}", use_container_width=True):
            st.session_state["workspace_match_id"] = match.id
            request_navigation("Jornada")
            st.rerun()


def render(user: dict) -> None:
    page_header("Calendario de la liga", "Toda la competición en un único lugar: horarios, partidos de No Name y partidos neutrales.")
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
    pure_reporter = roles_for(user) == {"reporter"}
    own_only = pure_reporter
    if not pure_reporter:
        own_only = st.toggle("Solo partidos de No Name", value=False, key="calendar_own_only")
    with session_scope() as session:
        matches = calendar_repo.list_calendar(session, season_id=season_id, competition_id=comp_id, team_id=own.id if own_only and own else None, limit=600)
    if can_admin(user):
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
    ordered = sorted(matches, key=lambda m: (m.match_date < local_today(), m.kickoff_at or datetime.combine(m.match_date, time(23,59))))
    for match in ordered[:80]:
        _calendar_actions(user, match, own.id if own else None)
