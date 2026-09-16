"""Human-centered DD request → voluntary reporter response → existing evidence."""
from __future__ import annotations

import streamlit as st
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from core.database import session_scope
from core.navigation import request_navigation
from core.permissions import can_direct, can_report
from core.interest import explicitly_selected, qualifies_for_discovery
from models.entities import Match, Participation, Player, TeamRoster
from repositories import observation_requests as requests_repo
from repositories import players as players_repo
from repositories.data_governance import official_match_clause


def _name(player) -> str:
    return player.display_name or player.full_name


def _player_link(pid: int, key: str, label: str = "Abrir jugador"):
    if st.button(label, key=key, use_container_width=True):
        st.session_state["workspace_player_id"] = int(pid)
        request_navigation("Jugadores")
        st.rerun()


def composer(user: dict, season_id: int, *, selected_player_id: int | None = None,
             key_prefix: str = "dd") -> None:
    if not can_direct(user):
        return
    with st.container(border=True):
        st.markdown("#### Pedir una opinión")
        st.caption("Envía una pregunta concreta. El Informador puede responder cuando haya visto al jugador.")
        search = st.text_input("Buscar jugador externo", key=f"{key_prefix}_request_search_443",
            placeholder="Nombre o apellido") if selected_player_id is None else ""
        with session_scope() as session:
            own = players_repo.get_own_team(session)
            owned = {r.player_id for r in players_repo.get_roster(session, own.id, int(season_id))} if own else set()
            players = players_repo.list_players(session, search=search or None, limit=70) if selected_player_id is None else [session.get(Player, int(selected_player_id))]
            players = [p for p in players if p and p.id not in owned and p.active and p.merged_into_id is None]
            staff = requests_repo.available_reporters(session)
            matches = list(session.scalars(select(Match).where(Match.season_id == int(season_id),
                official_match_clause()).options(joinedload(Match.home_team), joinedload(Match.away_team))
                .order_by(Match.match_date.desc(), Match.id.desc()).limit(45)).unique().all())
        if not players:
            st.info("No se han encontrado jugadores externos. Ajusta la búsqueda o comprueba su equipo en Jugadores.")
            return
        player_ids = [p.id for p in players]
        names = {p.id: _name(p) for p in players}
        user_ids = [u.id for u in staff]
        users = {u.id: u.full_name for u in staff}
        match_ids = [None] + [m.id for m in matches]
        match_names = {None: "Cuando vuelva a coincidir", **{m.id:
            f"{m.match_date.strftime('%d/%m/%Y')} · {m.home_team.name} – {m.away_team.name}" for m in matches}}
        with st.form(f"{key_prefix}_compose_443_{selected_player_id or 'all'}"):
            player_id = st.selectbox("Futbolista", player_ids, format_func=lambda pid: names[pid])
            recipients = st.multiselect("Informadores destinatarios", user_ids,
                format_func=lambda uid: users[uid], help="Solo usuarios activos con rol Informador.")
            question = st.text_area("Qué quieres que observen", height=80,
                placeholder="Por ejemplo, defensa del uno contra uno y comportamiento sin balón.")
            a, b = st.columns(2)
            priority = a.selectbox("Prioridad", ["Normal", "Alta"])
            target_match = b.selectbox("Partido (opcional)", match_ids,
                format_func=lambda mid: match_names[mid])
            submit = st.form_submit_button("Enviar petición", type="primary", use_container_width=True)
        if submit:
            try:
                with session_scope() as session:
                    created = requests_repo.create_request(session, actor_id=user["id"],
                        season_id=int(season_id), player_id=int(player_id), recipient_ids=recipients,
                        question=question, priority=priority, target_match_id=target_match)
                st.success("Petición guardada. Cada destinatario verá la pregunta en su bandeja.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def director_board(user: dict, season_id: int, *, compact: bool = False) -> None:
    if not can_direct(user):
        return
    with session_scope() as session:
        requests = requests_repo.list_requests(session, season_id=season_id)
        entries = []
        for req in requests:
            recip = requests_repo.recipients(session, req.id)
            answers = requests_repo.responses(session, req.id)
            entries.append((req, recip, answers))
    open_rows = [row for row in entries if row[0].status == "open"]
    answered = sum(len(row[2]) for row in entries)
    st.markdown("### Peticiones y respuestas" if not compact else "#### Peticiones al staff")
    a,b,c = st.columns(3)
    a.metric("Abiertas", len(open_rows))
    b.metric("Respuestas registradas", answered)
    c.metric("Sin respuesta", sum(bool(row[1]) and all(r.status == "pending" for r in row[1]) for row in open_rows))
    if not entries:
        st.info("Todavía no hay peticiones. Puedes pedir una opinión desde la ficha de un jugador externo.")
        return
    if compact:
        st.caption("Últimas peticiones; consulta el resto desde «Peticiones de opinión».")
    else:
        kind = st.selectbox("Ver peticiones", ["Abiertas", "Con respuesta", "Cerradas", "Todas"],
                            key="dd_request_view_444")
        entries = [row for row in entries if
            (kind == "Todas" or kind == "Abiertas" and row[0].status == "open" or
             kind == "Con respuesta" and bool(row[2]) or kind == "Cerradas" and row[0].status == "closed")]
        if not entries:
            st.caption("No hay peticiones con ese filtro.")
    for req, recip, answers in (entries[:3] if compact else entries):
        with st.container(border=True):
            st.markdown(f"**{_name(req.player)}** · {'Abierta' if req.status == 'open' else 'Cerrada'}")
            st.caption(f"{req.priority} · Solicitada por {req.creator.full_name} · "
                f"{req.created_at.strftime('%d/%m/%Y')}")
            if compact:
                st.caption(f"{len(answers)} respuesta(s) · {sum(r.status == 'pending' for r in recip)} pendiente(s)")
            else:
                st.write(req.question)
                st.caption("Informadores: " + (" · ".join(f"{r.user.full_name}: "
                    f"{'Pendiente' if r.status == 'pending' else 'Respondida' if r.status == 'answered' else 'Declinada'}" for r in recip) or "Sin destinatarios"))
            for answer in answers[:2 if compact else None]:
                origin = f" · {answer.match.home_team.name} – {answer.match.away_team.name}" if answer.match else ""
                grade = f" · nota {answer.evaluation.general_rating:g}" if answer.evaluation and answer.evaluation.general_rating else (
                    f" · señal {answer.neutral_signal.rating:g}" if answer.neutral_signal and answer.neutral_signal.rating else "")
                st.write(f"**{answer.user.full_name}**: {requests_repo.RESULTS.get(answer.result,answer.result)}{origin}{grade}")
                if answer.note and not compact:
                    st.caption(answer.note)
            _player_link(req.player_id, f"dd_req_player_443_{req.id}_{compact}")
            if not compact and req.status == "open":
                with st.expander("Gestionar petición"):
                    reason = st.text_input("Motivo de cierre (opcional)", key=f"dd_close_reason_443_{req.id}")
                    if st.button("Cerrar petición", key=f"dd_close_443_{req.id}", use_container_width=True):
                        try:
                            with session_scope() as session:
                                requests_repo.close_request(session, actor_id=user["id"], request_id=req.id, reason=reason)
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
    if compact and len(entries) > 3:
        st.caption(f"{len(entries)-3} peticiones adicionales en el área «Peticiones de opinión».")


def _matches_for_request(session, req):
    """Only real matches where player identity matches participating club or documented appearance."""
    roster_clubs = select(TeamRoster.team_id).where(TeamRoster.player_id == req.player_id,
        TeamRoster.season_id == req.season_id)
    documented_matches = select(Participation.match_id).where(Participation.player_id == req.player_id)
    stmt = select(Match).options(joinedload(Match.home_team), joinedload(Match.away_team)).where(
        Match.season_id == req.season_id, official_match_clause(),
        or_(Match.id.in_(documented_matches), Match.home_team_id.in_(roster_clubs),
            Match.away_team_id.in_(roster_clubs)))
    if req.target_match_id:
        stmt = stmt.where(Match.id == req.target_match_id)
    rows = list(session.scalars(stmt.order_by(Match.match_date.desc(), Match.id.desc())).unique().all())
    result = []
    for m in rows:
        relevance = requests_repo.match_relevance(session, req, m.id)
        if relevance:
            result.append((m, relevance))
    return result


def _answer_form(user: dict, req, *, match_id: int | None = None, key_prefix: str) -> None:
    with session_scope() as session:
        relevant = _matches_for_request(session, req) if match_id is None else []
        current_type = requests_repo.match_relevance(session, req, match_id) if match_id else None
    choices = ([None] if match_id is None else []) + [m.id for m, _ in relevant]
    mapping = {m.id: (m, reason) for m, reason in relevant}
    if match_id is not None:
        choices = [match_id]
    with st.form(f"answer_request_443_{key_prefix}_{req.id}"):
        if match_id is None:
            target = st.selectbox("Partido observado (si procede)", choices,
                format_func=lambda mid: "Sin partido" if mid is None else (
                    f"{mapping[mid][0].home_team.name} – {mapping[mid][0].away_team.name} · "
                    f"{'participación registrada' if mapping[mid][1] == 'participation' else 'participación sin confirmar'}"))
            relevance = mapping.get(target, (None, None))[1]
        else:
            target = match_id
            relevance = current_type
        answer = st.selectbox("Tu respuesta", list(requests_repo.RESULTS),
            format_func=lambda key: requests_repo.RESULTS[key])
        note = st.text_area("Impresión o motivo (opcional, salvo si lo viste y no lo has puntuado)",
            height=68, placeholder="Por ejemplo, defensivamente correcto en 1 contra 1.")
        confirm = False
        if answer == "seen" and relevance == "possible":
            confirm = st.checkbox("Confirmo personalmente que vi jugar a este futbolista.",
                help="Figurar en una plantilla no demuestra que participara. No modifica el XI.")
        submitted = st.form_submit_button("Guardar respuesta", use_container_width=True, type="primary")
    if submitted:
        try:
            with session_scope() as session:
                requests_repo.respond(session, actor_id=user["id"], request_id=req.id,
                    result=answer, match_id=target, note=note, confirmed_played=confirm)
            st.success("Respuesta registrada y disponible para Dirección Deportiva.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def reporter_inbox(user: dict, season_id: int, *, compact: bool = False) -> None:
    if not can_report(user):
        return
    with session_scope() as session:
        pending = requests_repo.list_requests(session, season_id=season_id,
            reporter_id=user["id"], active_only=True)
    if not pending:
        return
    st.markdown("### Peticiones de opinión" if not compact else "#### Dirección Deportiva te pregunta")
    st.caption("Son voluntarias. Puedes responder cuando coincidas con el jugador o indicar que no lo has visto.")
    show_all = bool(st.session_state.get("home_all_requests_444")) if compact else True
    for req in (pending[:2] if compact and not show_all else pending):
        with st.container(border=True):
            st.markdown(f"**{_name(req.player)}**")
            st.caption(f"{req.creator.full_name} · {req.priority} · {req.created_at.strftime('%d/%m/%Y')}")
            st.write(req.question)
            if st.button("No pude verlo", key=f"request_quick_unseen_444_{req.id}",
                         use_container_width=True, help="Informa de que no puedes aportar una valoración; no crea ninguna nota."):
                try:
                    with session_scope() as session:
                        requests_repo.respond(session, actor_id=user["id"], request_id=req.id,
                                             result="not_seen", match_id=None, note="")
                    st.toast("Respuesta enviada a Dirección Deportiva.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            with st.expander("Responder a esta petición", expanded=False):
                _answer_form(user, req, key_prefix=f"inbox_{compact}")
    if compact and len(pending) > 2:
        if st.button("Mostrar menos peticiones" if show_all else f"Ver las {len(pending)} peticiones",
                     use_container_width=True, key="requests_show_all_444"):
            st.session_state["home_all_requests_444"] = not show_all
            st.rerun()


def match_prompts(user: dict, match_id: int) -> None:
    if not can_report(user):
        return
    with session_scope() as session:
        matches = requests_repo.requests_for_match(session, match_id=match_id, reporter_id=user["id"])
    if not matches:
        return
    st.markdown("### Jugadores sobre los que DD solicita tu opinión")
    for req, relevance in matches:
        with st.container(border=True):
            st.markdown(f"**{_name(req.player)}** · {'Participación registrada' if relevance == 'participation' else 'Posible coincidencia'}")
            st.caption(f"Petición de {req.creator.full_name}")
            st.write(req.question)
            if relevance == "possible":
                st.caption("Solo consta en la plantilla: no podemos afirmar que haya jugado.")
            with st.expander("Responder (opcional)"):
                _answer_form(user, req, match_id=match_id, key_prefix=f"match_{match_id}")


def interest_list(user: dict, season_id: int) -> None:
    """Shortlist chosen by DD, separate from evidence-driven discovery."""
    if not can_direct(user):
        return
    from repositories import sporting_reading, tracking, planning
    with session_scope() as session:
        intel = sporting_reading.league_intelligence(session, int(season_id))
        signals = {row["player"].id: row for row in (intel.get("players") or [])}
        follow = tracking.tracking_activity(session, int(season_id), limit=120)
        decisions = {d.player_id: d for d in planning.list_season_decisions(session, int(season_id))}
        reqs = requests_repo.list_requests(session, season_id=int(season_id), active_only=True)
        own = players_repo.get_own_team(session)
        owned = {r.player_id for r in players_repo.get_roster(session, own.id, int(season_id))} if own else set()
        players_ids = ({*signals, *(ev["player"].id for ev in follow),
                        *(req.player_id for req in reqs), *decisions} - owned)
        players = {p.id: p for p in session.scalars(select(Player).where(Player.id.in_(players_ids),
            Player.active.is_(True), Player.merged_into_id.is_(None))).all()} if players_ids else {}
    by_player = {}
    for row in follow:
        by_player.setdefault(row["player"].id, row)
    req_by_player = {}
    for req in reqs:
        req_by_player[req.player_id] = req_by_player.get(req.player_id, 0) + 1
    st.markdown("### Jugadores de interés")
    st.caption("Selección deportiva: decisiones expresas de DD, peticiones abiertas o seguimiento formal. Una señal aislada no incorpora automáticamente a un jugador.")
    search = st.text_input("Buscar en el listado", key="dd_interest_search_443")
    scope = st.selectbox("Mostrar", ["Selección DD", "Descubrir candidatos por nota"],
        key="dd_interest_scope_444")
    if scope == "Descubrir candidatos por nota":
        minimum_matches = st.selectbox("Muestra mínima", [2, 1, 3, 4],
            format_func=lambda value: f"{value} partido{'s' if value != 1 else ''}",
            help="La media mínima es 8/10. Una sola actuación tiene menor respaldo y se indica expresamente.",
            key="dd_interest_sample_444")
        selected = [p for p in players.values() if search.casefold() in _name(p).casefold()
            and qualifies_for_discovery(signals.get(p.id), minimum_matches=minimum_matches)
            and not (p.id in decisions and decisions[p.id].status == "Descartado")
            and not explicitly_selected(decision_status=decisions[p.id].status if p.id in decisions else None,
                has_open_request=p.id in req_by_player, has_formal_tracking=p.id in by_player)]
        st.caption("Candidatos por filtro de nota ≥8/10; no son incorporaciones automáticas a la selección ni decisiones de fichaje.")
    else:
        status = st.selectbox("Situación", ["Todos", "Con petición", "Con seguimiento", "Con decisión"],
            key="dd_interest_status_443")
        selected = [p for p in players.values() if search.casefold() in _name(p).casefold() and
            explicitly_selected(decision_status=decisions[p.id].status if p.id in decisions else None,
                has_open_request=p.id in req_by_player, has_formal_tracking=p.id in by_player)
            and (status == "Todos" or
                 status == "Con petición" and p.id in req_by_player or
                 status == "Con seguimiento" and p.id in by_player or
                 status == "Con decisión" and p.id in decisions and
                     decisions[p.id].status in {"Interesante", "Seguimiento", "Prioritario"})]
    st.caption(f"{len(selected)} jugadores encontrados.")
    for p in sorted(selected, key=lambda item: (
            -(signals[item.id]["weighted_rating"] or 0) if item.id in signals else 0,
            _name(item).casefold()))[:60]:
        with st.container(border=True):
            a, b = st.columns([3,1])
            a.markdown(f"**{_name(p)}** · {p.primary_position or 'Posición desconocida'}")
            signal = signals.get(p.id)
            if signal:
                a.caption(f"Media {signal['weighted_rating']:.1f}/10" if signal['weighted_rating'] is not None else "Sin nota suficiente")
                a.caption(f"{signal['match_count']} partido(s) · {signal['mentions']} señal(es) · "
                    f"{signal['staff_count']} informadores" +
                    (" · muestra de un único partido" if signal['match_count'] == 1 else ""))
            else:
                a.caption("Sin señales neutrales disponibles")
            if p.id in by_player:
                a.caption("Seguimiento individual registrado")
            if p.id in req_by_player:
                a.caption(f"{req_by_player[p.id]} petición(es) abierta(s)")
            if p.id in decisions:
                a.caption(f"DD: {decisions[p.id].status}")
            with b:
                _player_link(p.id, f"dd_interest_open_443_{p.id}")
                if scope == "Descubrir candidatos por nota":
                    if st.button("Añadir a selección", key=f"dd_interest_select_444_{p.id}",
                                 use_container_width=True):
                        try:
                            with session_scope() as session:
                                planning.upsert_season_decision(session, user["id"],
                                    season_id=int(season_id), player_id=p.id,
                                    status="Interesante", priority=3,
                                    director_note="Seleccionado expresamente tras revisar la evidencia.")
                            st.success("Jugador añadido a la selección de Dirección Deportiva.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
    if len(selected) > 60:
        st.caption("Se muestran 60 jugadores. Utiliza la búsqueda para localizar el resto.")
