from __future__ import annotations

import base64
import json

import pandas as pd
import streamlit as st

from core.constants import POSITIONS, RECOMMENDATIONS
from core.database import session_scope
from core.utils import safe_html
from models.entities import Player
from repositories import scouting as repo
from ui.styles import page_header


def _fmt(value, digits: int = 2) -> str:
    return "Sin muestra" if value is None else f"{float(value):.{digits}f}"


def render(user: dict) -> None:
    page_header("Jugadores observados", "Histórico fiable: solo informes aprobados/finales y exclusivamente evaluaciones de rivales.")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    search = c1.text_input("Buscar por nombre")
    position = c2.selectbox("Posición", ["Todas"] + POSITIONS)
    min_reports = c3.number_input("Mínimo informes", min_value=1, value=1, step=1)
    page = c4.number_input("Página", min_value=1, value=1, step=1)
    page_size = 100
    with session_scope() as session:
        rankings = repo.player_rankings(session, min_observations=int(min_reports), position=position, limit=page_size, offset=(int(page)-1)*page_size)
        if search:
            rankings = [r for r in rankings if search.casefold() in r["full_name"].casefold()]
    if not rankings:
        st.info("No hay jugadores observados que coincidan con los filtros.")
        return
    shown = pd.DataFrame([{
        "Jugador": r["full_name"], "Posición observada": r["primary_position"], "Informes": r["observations"],
        "Informadores": r["reporter_count"], "General": round(r["avg_general"], 2),
        "Dispersión": round(r["rating_dispersion"], 2), "Decisión habitual": r["recommendation"],
        "Destacados": r["standouts"], "Última observación": r["last_observed"],
    } for r in rankings])
    st.dataframe(shown, use_container_width=True, hide_index=True)

    ids = [int(r["player_id"]) for r in rankings]
    labels = {int(r["player_id"]): f"{r['full_name']} · {r['primary_position'] or '-'}" for r in rankings}
    selected_id = st.selectbox("Abrir ficha", ids, format_func=lambda pid: labels[pid])
    with session_scope() as session:
        player = session.get(Player, selected_id)
        history = repo.player_history(session, selected_id)
    if not player:
        return
    avg_row = next(r for r in rankings if int(r["player_id"]) == selected_id)
    photo = ""
    if player.photo_b64:
        photo = f'<img src="data:{safe_html(player.photo_mime or "image/jpeg")};base64,{player.photo_b64}" style="width:88px;height:88px;object-fit:cover;border-radius:12px;margin-right:18px">'
    st.markdown(
        f'''<div class="pm-card" style="display:flex;align-items:center">{photo}<div>
        <div class="pm-kicker">Ficha histórica validada</div>
        <div class="pm-player-name">{safe_html(player.full_name)}</div>
        <div class="pm-player-meta">{safe_html(player.primary_position or '-')} · {safe_html(player.nationality or 'Nacionalidad no registrada')} · {len(history)} observaciones aprobadas</div>
        </div></div>''', unsafe_allow_html=True,
    )
    cols = st.columns(5)
    cols[0].metric("Nota media", _fmt(avg_row["avg_general"]))
    cols[1].metric("Informes", int(avg_row["observations"]))
    cols[2].metric("Informadores", int(avg_row["reporter_count"]))
    cols[3].metric("Dispersión", _fmt(avg_row["rating_dispersion"]))
    cols[4].metric("Última", str(avg_row["last_observed"] or "-"))
    st.caption("Una dispersión alta indica desacuerdo entre observaciones; las dimensiones sin evaluar aparecen como ‘Sin muestra’, nunca como cero.")

    st.subheader("Historial de observaciones")
    for item in history:
        ev, match, participation = item["evaluation"], item["match"], item["participation"]
        position_observed = participation.position if participation and participation.position else player.primary_position
        minutes = (participation.minute_out - participation.minute_in) if participation else None
        title = f"{match.match_date.strftime('%d/%m/%Y')} · {match.home_team.name} - {match.away_team.name} · {item['reporter'].full_name}"
        with st.expander(title, expanded=False):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("General", _fmt(ev.general_rating, 1))
            c2.metric("Técnica", _fmt(ev.technical_rating, 1))
            c3.metric("Táctica", _fmt(ev.tactical_rating, 1))
            c4.metric("Física", _fmt(ev.physical_rating, 1))
            c5.metric("Minutos", str(minutes) if minutes is not None else "Sin muestra")
            st.write(f"**Equipo observado:** {item['team'].name} · **Posición observada:** {position_observed or '-'}")
            st.write(f"**Competición:** {item['competition'].name} · **Estado del informe:** {item['report'].status}")
            st.write(f"**Decisión:** {ev.recommendation or '-'} · **Confianza:** {ev.confidence or 'Sin muestra'}")
            if ev.short_note:
                st.write(ev.short_note)
            if ev.strengths:
                try:
                    strengths = json.loads(ev.strengths)
                except (json.JSONDecodeError, TypeError):
                    strengths = []
                if strengths:
                    st.caption("Fortalezas: " + " · ".join(strengths))
            if ev.detailed_note:
                st.markdown("**Nota ampliada**")
                st.write(ev.detailed_note)
