from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import select

from core.constants import POSITIONS
from core.database import session_scope
from core.utils import safe_html
from models.entities import Player
from repositories import scouting as repo
from ui.styles import page_header


def _fmt(value, digits: int = 2) -> str:
    return "Sin muestra" if value is None else f"{float(value):.{digits}f}"


def _history_block(player, history: list[dict], scope_label: str) -> None:
    st.markdown(
        f'''<div class="pm-card">
        <div class="pm-kicker">{safe_html(scope_label)}</div>
        <div class="pm-player-name">{safe_html(player.display_name or player.full_name)}</div>
        <div class="pm-player-meta">{safe_html(player.primary_position or '-')} · {len(history)} observaciones aprobadas</div>
        </div>''',
        unsafe_allow_html=True,
    )
    if not history:
        st.info("Todavía no hay valoraciones aprobadas para este jugador.")
        return

    trend_rows = []
    for item in reversed(history):
        ev, match = item["evaluation"], item["match"]
        if ev.general_rating is not None:
            trend_rows.append({"Fecha": match.match_date, "Nota": float(ev.general_rating)})
    if len(trend_rows) >= 2:
        trend = pd.DataFrame(trend_rows).set_index("Fecha")
        st.line_chart(trend)

    st.subheader("Historial")
    for item in history:
        ev, match, participation = item["evaluation"], item["match"], item["participation"]
        minutes = (participation.minute_out - participation.minute_in) if participation else None
        position = participation.position if participation and participation.position else player.primary_position
        title = f"{match.match_date.strftime('%d/%m/%Y')} · {match.home_team.name} - {match.away_team.name} · {ev.general_rating:.1f}" if ev.general_rating is not None else f"{match.match_date.strftime('%d/%m/%Y')} · {match.home_team.name} - {match.away_team.name}"
        with st.expander(title):
            c1, c2, c3 = st.columns(3)
            c1.metric("Nota", _fmt(ev.general_rating, 1))
            c2.metric("Posición", position or "-")
            c3.metric("Minutos", minutes if minutes is not None else "-")
            st.caption(f"Informador: {item['reporter'].full_name} · {item['competition'].name}")
            if ev.short_note:
                st.write(ev.short_note)
            else:
                st.caption("Sin observación escrita.")


def _render_own_team() -> None:
    with session_scope() as session:
        own = repo.get_own_team(session)
        season = repo.get_active_season(session)
        rankings = repo.own_player_rankings(session, min_observations=1, season_id=season.id if season else None)
        roster = repo.get_roster(session, own.id, season.id) if own and season else []
    if not own:
        st.info("No Name todavía no está configurado como equipo propio.")
        return

    st.markdown(f"### {safe_html(own.name)}", unsafe_allow_html=True)
    st.caption("Memoria interna del cuerpo técnico: el histórico nace de las valoraciones postpartido, sin formularios adicionales.")

    ranking_by_id = {int(r["player_id"]): r for r in rankings}
    roster_players = [item.player for item in roster]
    known_ids = {p.id for p in roster_players}
    missing_ids = [int(row["player_id"]) for row in rankings if int(row["player_id"]) not in known_ids]
    if missing_ids:
        with session_scope() as session:
            roster_players.extend(list(session.scalars(select(Player).where(Player.id.in_(missing_ids))).all()))

    if rankings:
        st.dataframe(pd.DataFrame([{
            "Jugador": r["full_name"],
            "Posición": r["primary_position"] or "-",
            "Partidos valorados": r["observations"],
            "Nota media": round(r["avg_general"], 2),
            "Destacados": r["standouts"],
            "Último": r["last_observed"],
        } for r in rankings]), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay valoraciones propias aprobadas. La plantilla seguirá disponible para consultar cuando empiecen a acumularse.")

    if not roster_players:
        return
    roster_players = sorted({p.id: p for p in roster_players}.values(), key=lambda p: p.full_name)
    selected = st.selectbox(
        "Abrir jugador de No Name",
        [p.id for p in roster_players],
        format_func=lambda pid: next(f"{p.display_name or p.full_name} · {p.primary_position or '-'}" for p in roster_players if p.id == pid),
    )
    with session_scope() as session:
        player = session.get(Player, selected)
        history = repo.player_history_by_scope(session, selected, scope="own")
    if player:
        _history_block(player, history, "Rendimiento No Name")


def _render_rivals() -> None:
    filters = st.session_state.setdefault("rival_query_filters", {"search": "", "position": "Todas", "min_reports": 1})
    with st.form("rival_query_form", border=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        search = c1.text_input("Buscar rival por nombre", value=filters["search"])
        position = c2.selectbox("Posición", ["Todas"] + POSITIONS, index=(["Todas"] + POSITIONS).index(filters["position"]))
        min_reports = c3.number_input("Mínimo observaciones", min_value=1, value=int(filters["min_reports"]), step=1)
        apply = st.form_submit_button("Consultar", type="primary", use_container_width=True)
    if apply:
        st.session_state["rival_query_filters"] = {"search": search, "position": position, "min_reports": int(min_reports)}
        filters = st.session_state["rival_query_filters"]

    page = int(st.number_input("Página", min_value=1, value=int(st.session_state.get("rival_players_page", 1)), step=1, key="rival_players_page_input"))
    st.session_state["rival_players_page"] = page
    per_page = 50
    with session_scope() as session:
        rankings = repo.player_rankings(
            session, min_observations=int(filters["min_reports"]), position=filters["position"],
            search=filters["search"], limit=per_page, offset=(page-1)*per_page,
        )
    if not rankings:
        st.info("No hay rivales observados que coincidan con los filtros.")
        return

    st.caption(f"Página {page} · hasta {per_page} resultados · búsqueda y filtros ejecutados en PostgreSQL")
    st.dataframe(pd.DataFrame([{
        "Jugador": r["full_name"],
        "Posición": r["primary_position"] or "-",
        "Observaciones": r["observations"],
        "Media": round(r["avg_general"], 2),
        "Informadores": r["reporter_count"],
        "Destacados": r["standouts"],
        "Última": r["last_observed"],
    } for r in rankings]), use_container_width=True, hide_index=True)

    ids = [int(r["player_id"]) for r in rankings]
    labels = {int(r["player_id"]): f"{r['full_name']} · {r['primary_position'] or '-'}" for r in rankings}
    selected = st.selectbox("Abrir ficha rival", ids, format_func=lambda pid: labels[pid])
    if st.button("Cargar historial del jugador", use_container_width=True):
        st.session_state["rival_history_player"] = selected
    history_id = st.session_state.get("rival_history_player")
    if history_id in ids:
        with session_scope() as session:
            player = session.get(Player, history_id)
            history = repo.player_history_by_scope(session, history_id, scope="rival")
        if player:
            _history_block(player, history, "Scouting acumulado")


def render(user: dict) -> None:
    page_header("Jugadores", "Consulta rápida: abre solo No Name o Rivales; la sección no visible no hace consultas.")
    section = st.radio("Tipo de jugador", ["No Name", "Rivales"], horizontal=True, key="players_section")
    if section == "No Name":
        _render_own_team()
    else:
        _render_rivals()
