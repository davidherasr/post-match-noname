"""4.5 editorial DD reading: what, why, how much evidence, what next."""
from __future__ import annotations
import streamlit as st
from core.database import session_scope
from core.navigation import request_navigation
from repositories import dd_attention, observation_requests, planning, players
from repositories import unidentified_players as unknown_repo


def _player(pid: int) -> None:
    st.session_state["workspace_player_id"] = pid
    request_navigation("Jugadores")
    st.rerun()


def _match(mid: int) -> None:
    st.session_state["workspace_match_id"] = mid
    request_navigation("Jornada")
    st.rerun()


def render(user: dict, season_id: int, *, own: bool = False, limit: int = 35) -> None:
    with session_scope() as session:
        rows = [r for r in dd_attention.attention_feed(session, season_id) if r["own_team"] == own]
        responses = dd_attention.recent_request_responses(session, season_id) if not own else []
    st.markdown("### Evolución de la plantilla propia" if own else "### Lo que merece tu atención")
    st.caption("Reglas transparentes y tamaño de muestra. Una nota alta es una señal; solo DD decide su interés.")
    if responses:
        with st.expander(f"Respuestas recientes a peticiones DD ({len(responses)})", expanded=False):
            for answer in responses:
                with st.container(border=True):
                    st.markdown(f"**{answer['author']}** respondió sobre **{answer['name']}**")
                    st.caption(f"Respuesta: {answer['result']} · petición #{answer['request_id']}"
                               + (f" · origen: {answer['evidence_origin']}" if answer['evidence_origin'] else ""))
                    st.write(answer["question"])
                    if answer["note"]:
                        st.write(answer["note"])
                    if st.button("Abrir jugador y evidencia", key=f"dd_response45_{answer['response_id']}"):
                        _player(answer["player_id"])
    if not rows:
        st.info("Todavía no hay evidencias destacadas con las reglas actuales.")
        return
    for item in rows[:limit]:
        pid = item.get("player_id")
        own_id = f"p{pid}_t{item['team_id']}" if pid else f"u{item['unknown_id']}"
        with st.container(border=True):
            st.markdown(f"**{item['name']}**" + (" · identidad pendiente" if not pid else ""))
            m = "—" if item["average"] is None else str(round(item["average"], 2)).replace(".", ",")
            st.caption(f"{item['matches']} partido(s) · {item['authors']} autor(es) · {item['events']} señal(es) · "
                       f"{len(item['ratings'])} notas · media {m} · top 3: {item['highlights']} · "
                       f"top 1: {item['top_ones']} · conocimiento {item['coverage']}")
            st.write("**Motivo:** " + "; ".join(item["reasons"]))
            if pid and item.get("status"):
                st.caption(f"Decisión DD existente: {item['status']}")
            with st.expander("Ver autores, partidos y valoraciones originales", expanded=False):
                for ev in item["evidence"]:
                    grade = "sin nota" if ev["rating"] is None else f"{ev['rating']:g}/10"
                    st.markdown(f"**{ev['author']}** · partido {ev['match_id']} · {grade}"
                                + (f" · top {ev['rank']}" if ev.get("rank") else ""))
                    if ev.get("note"):
                        st.caption(ev["note"])
                    c1, c2 = st.columns(2)
                    if c1.button("Abrir partido", key=f"dd_match_45_{own_id}_{ev['kind']}_{ev['evidence_id']}"):
                        _match(ev["match_id"])
                    if (pid and not own and ev["kind"] in {"own_report", "neutral", "resolved_unknown"} and
                            c2.button("Preguntar a este autor", key=f"dd_question_45_{own_id}_{ev['kind']}_{ev['evidence_id']}") ):
                        try:
                            with session_scope() as session:
                                observation_requests.ask_about_evidence(session, actor_id=user["id"],
                                    evidence_kind=ev["kind"], evidence_id=ev["evidence_id"])
                            st.success("Petición creada y vinculada a la evidencia.")
                        except Exception as exc:
                            st.error(str(exc))
            if pid:
                cols = st.columns(2)
                if cols[0].button("Abrir ficha 360", key=f"dd_player_45_{own_id}"):
                    _player(pid)
                if not own:
                    if item.get("status") not in {"Interesante", "Seguimiento", "Prioritario"}:
                        if cols[1].button("Añadir a interés DD", key=f"dd_interest_45_{own_id}"):
                            try:
                                with session_scope() as session:
                                    planning.upsert_season_decision(session, user["id"],
                                        season_id=season_id, player_id=pid, status="Interesante", priority=3)
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                    elif item.get("status") != "Prioritario":
                        if cols[1].button("Decidir: prioritario", key=f"dd_prior_45_{own_id}"):
                            try:
                                with session_scope() as session:
                                    current = next((x for x in planning.list_season_decisions(session, season_id) if x.player_id == pid), None)
                                    planning.upsert_season_decision(session, user["id"], season_id=season_id,
                                        player_id=pid, status="Prioritario", priority=2,
                                        model_role_id=current.model_role_id if current else None,
                                        director_note=current.director_note if current else None,
                                        fit_score=current.fit_score if current else None,
                                        current_level=current.current_level if current else None,
                                        potential_score=current.potential_score if current else None)
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
            else:
                with st.expander("Identificar futbolista · Administración / DD"):
                    st.caption("Solo puedes vincular la señal a un jugador existente de esta plantilla; no se inventan fichas.")
                    with session_scope() as session:
                        members = players.get_roster(session, item["team_id"], season_id)
                        options = [(r.player_id, r.player.display_name or r.player.full_name) for r in members]
                    if not options:
                        st.info("Primero incorpora el jugador real a la plantilla de ese equipo/temporada.")
                    else:
                        pid_options = [id for id, _ in options]
                        selected = st.selectbox("Jugador verificado", pid_options,
                            key=f"dd_unknown_player_45_{own_id}",
                            format_func=lambda id: next(name for rid, name in options if rid == id))
                        if st.button("Vincular identidad sin duplicar la nota", key=f"dd_resolve_45_{own_id}"):
                            try:
                                with session_scope() as session:
                                    unknown_repo.resolve(session, actor_id=user["id"],
                                                         signal_id=item["unknown_id"], player_id=selected)
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
