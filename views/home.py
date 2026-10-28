"""4.6 consultation-first workspaces; actions remain opt-in and permission-gated."""
from __future__ import annotations

import streamlit as st
from core.database import session_scope
from core.navigation import request_navigation
from core.permissions import roles_for, can_report, can_direct, can_admin
from repositories import calendar as calendar_repo
from repositories import workspaces, staff_feed
from ui.styles import page_header


def _go(destination: str, *, player_id=None, match_id=None, report=False) -> None:
    if player_id is not None:
        st.session_state["workspace_player_id"] = int(player_id)
    if match_id is not None:
        st.session_state["workspace_match_id"] = int(match_id)
        st.session_state["match_hub_mode"] = "report" if report else None
    request_navigation(destination)
    st.rerun()


def _open_match(match_id: int) -> None:
    _go("Jornada", match_id=match_id)


def _open_report(match_id: int) -> None:
    _go("Jornada", match_id=match_id, report=True)


def _open_director_reading() -> None:
    st.session_state["dd_area_42"] = "Lectura deportiva"
    st.session_state["dd_reading_area_421"] = "Jugadores señalados"
    _go("Dirección Deportiva")


def _render_activity(entries: list[dict]) -> None:
    st.markdown("### Novedades del cuerpo técnico")
    st.caption("Decisiones explícitas, lecturas entregadas y observaciones registradas. Los borradores no aparecen.")
    if not entries:
        st.info("Aún no hay actividad deportiva registrada en la temporada. Puedes consultar partidos y jugadores sin hacer ninguna aportación.")
        return
    for i, event in enumerate(entries):
        left, right = st.columns([6, 1], vertical_alignment="center")
        with left:
            date = event.get("date")
            date_text = date.strftime("%d/%m · %H:%M") if date else "Sin fecha"
            st.markdown(f"**{event['title']}** · {event['detail']}")
            st.caption(f"{date_text} · {event['source']}")
        with right:
            if event.get("player_id") and st.button("Ver jugador", key=f"activity_player_46_{i}", use_container_width=True):
                _go("Jugadores", player_id=event["player_id"])
            if event.get("match_id") and st.button("Ver partido", key=f"activity_match_46_{i}", use_container_width=True):
                _open_match(event["match_id"])
        if i < len(entries)-1:
            st.divider()


def _compact_fixture(match, label: str, *, own_report=None, key: str) -> None:
    with st.container(border=True):
        a, b = st.columns([5, 1], vertical_alignment="center")
        a.markdown(f"**{label}: {match.home_team.name} – {match.away_team.name}**")
        a.caption(f"{match.round_name} · {calendar_repo.schedule_label(match)}")
        if own_report:
            a.caption("Tu lectura: " + ("entregada" if own_report.status not in {"draft", "returned"} else "borrador"))
        if b.button("Consultar", key=f"home_open_46_{key}_{match.id}", use_container_width=True):
            _open_match(match.id)


def _render_reporting_option(user: dict, data: dict) -> None:
    """Reporting is a voluntary action, never the main homepage or a fake pending task."""
    from views.reports import _available_work_matches
    from core.clock import local_today
    if not can_report(user):
        return
    matches, assignments, reports = _available_work_matches(user)
    if not matches:
        return
    today = local_today()
    def distance(match):
        start = match.window_start or match.match_date
        end = match.window_end or start
        if hasattr(start, 'date'): start = start.date()
        if hasattr(end, 'date'): end = end.date()
        if start <= today <= end:
            return 0
        return min(abs((today-start).days), abs((today-end).days))
    current = min(matches, key=lambda m: (distance(m), abs((m.match_date-today).days)))
    by_match = {r.match_id: r for r in reports}
    _compact_fixture(current, "Partido de No Name", own_report=by_match.get(current.id), key="current")
    with st.expander("Aportar una lectura (voluntario)", expanded=False):
        st.caption("Puedes valorar solo No Name, ambos equipos, algún jugador o una observación sin nota. No necesitas que Admin prepare el encuentro.")
        if st.button("Abrir editor de este partido", key=f"home_voluntary_report_46_{current.id}",
                     use_container_width=True, disabled=bool(current.id in by_match and by_match[current.id].status not in {'draft', 'returned'})):
            _open_report(current.id)
        previous = [m for m in matches if m.id != current.id and m.match_date <= today]
        previous.sort(key=lambda m: m.match_date, reverse=True)
        if previous:
            ids = [m.id for m in previous[:40]]
            label = {m.id: f"{m.match_date:%d/%m} · {m.home_team.name} – {m.away_team.name}" for m in previous[:40]}
            chosen = st.selectbox("Partidos anteriores", ids, format_func=lambda mid: label[mid], key="home_previous_46")
            if st.button("Consultar el anterior", key="home_past_open_46", use_container_width=True):
                _open_match(chosen)
            if st.button("Aportar sobre el anterior", key="home_past_report_46", use_container_width=True,
                         disabled=bool(chosen in by_match and by_match[chosen].status not in {'draft','returned'})):
                _open_report(chosen)


def _render_director_attention(data: dict, user: dict) -> None:
    if not can_direct(user) or not data.get("active_season"):
        return
    from repositories import dd_attention
    with session_scope() as session:
        feed = dd_attention.attention_feed(session, data["active_season"].id)
    external = [row for row in feed if not row.get("own_team")]
    st.markdown("### Para Dirección Deportiva")
    st.caption("Señales que necesitan interpretación; una nota alta nunca crea por sí sola interés DD.")
    if not external:
        st.caption("Sin nuevas señales de jugadores externos. Los informes incorporados aparecerán cuando existan.")
    for i, row in enumerate(external[:3]):
        a, b = st.columns([5, 1], vertical_alignment="center")
        a.markdown(f"**{row['name']}** · {', '.join(row['reasons'][:2])}")
        average = f" · nota {row['average']:.1f}" if row.get('average') is not None else ""
        a.caption(f"{row['matches']} partidos · {row['authors']} autores · {row['coverage']}{average}")
        if row.get("player_id") and b.button("Ver", key=f"home_dd_attention_46_{i}", use_container_width=True):
            _go("Jugadores", player_id=row["player_id"])
    if st.button("Abrir Dirección Deportiva", key="home_dd_board_46"):
        _open_director_reading()


def _render_admin_options(user: dict) -> None:
    if not can_admin(user):
        return
    st.markdown("### Administración")
    st.caption("Mantenimiento por necesidad. Los horarios, alineaciones y asignaciones opcionales no generan tareas semanales.")
    a, b = st.columns(2)
    if a.button("Usuarios y permisos", key="home_admin_users_46", use_container_width=True):
        st.session_state['admin_section_current_423'] = 'Usuarios'
        _go("Administración")
    if b.button("Calidad de datos", key="home_admin_data_46", use_container_width=True):
        st.session_state['admin_section_current_423'] = 'Datos'
        _go("Administración")


def render(user: dict) -> None:
    page_header("Inicio", "Lo que ha cambiado en el club, sin tareas obligatorias por defecto.")
    delivered = st.session_state.pop("report_submission_notice", None)
    if delivered:
        st.success(f"Lectura de {delivered['title']} incorporada.")
    for notice_key in ("assignment_declined_notice", "tracking_saved_notice_442"):
        message = st.session_state.pop(notice_key, None)
        if message:
            st.success(message)
    roles = roles_for(user)
    with session_scope() as session:
        data = workspaces.load_home_workspace(session, user_id=user['id'], roles=roles)
        entries = staff_feed.load_activity(session,
            season_id=data['active_season'].id, roles=roles, limit=6) if data.get('active_season') else []

    if not data.get('active_season'):
        st.warning("No hay temporada activa. Administración debe configurarla.")
    if not data.get('own_team'):
        st.warning("No hay equipo propio configurado.")
    _render_activity(entries)

    # DD is shown *after* recent facts: context first, decisions and tasks second.
    _render_director_attention(data, user)

    if can_report(user):
        st.markdown("### Partidos")
        _render_reporting_option(user, data)
        # Explicit requests are work, but only for their actual recipients.
        if data.get('active_season'):
            from views.observation_requests import reporter_inbox
            with st.expander('Peticiones que te ha enviado Dirección Deportiva', expanded=False):
                reporter_inbox(user, data['active_season'].id, compact=True)
    else:
        match = data.get('last_match') or data.get('next_match')
        if match:
            st.markdown("### Partido de No Name")
            _compact_fixture(match, "Consultar", key="general")

    _render_admin_options(user)
    st.markdown("### Consultar")
    a, b = st.columns(2)
    if a.button("Calendario y partidos", use_container_width=True, key="home_calendar_46"):
        _go("Jornada")
    if b.button("Buscar jugadores", use_container_width=True, key="home_players_46"):
        _go("Jugadores")
