from __future__ import annotations

from datetime import datetime
import json

import pandas as pd
import streamlit as st

from core.clock import local_today
from core.constants import FORMATIONS, POSITIONS
from core.formations import available_lineup_player_ids, slots_for
from core.database import session_scope
from core.permissions import can_admin, can_direct, can_report, can_track_players
from core.presentation import status_badge
from core.schedule import is_schedule_confirmed
from repositories import calendar as calendar_repo
from repositories import matches as matches_repo
from repositories import planning as planning_repo
from repositories import players as players_repo
from repositories import workspaces
from repositories import sporting_reading as sporting_repo
from ui.styles import page_header
from ui.match_study import render_campogram


def _match_title(match) -> str:
    return f"{match.home_team.name} - {match.away_team.name}"


def _open_match(match_id: int) -> None:
    st.session_state["workspace_match_id"] = int(match_id)
    st.session_state.pop("match_hub_mode", None)
    st.rerun()


def _schedule_form(match, user: dict) -> None:
    if not can_admin(user):
        return
    with st.expander("Confirmar / corregir horario", expanded=not is_schedule_confirmed(match)):
        with st.form(f"schedule_39_{match.id}"):
            definitive_date = st.date_input("Fecha real", value=match.kickoff_at.date() if match.kickoff_at else match.match_date)
            # Matchday rule: if the kickoff is unknown the field is genuinely empty.
            kickoff_text = st.text_input("Hora real (HH:MM)", value=match.kickoff_at.strftime("%H:%M") if match.kickoff_at else "", placeholder="Ej. 17:30")
            venue = st.text_input("Campo (opcional)", value=match.venue or "")
            confirm = st.form_submit_button("Confirmar horario", type="primary", use_container_width=True)
        if confirm:
            try:
                if not kickoff_text.strip():
                    raise ValueError("Escribe una hora real. No se guarda ninguna hora por defecto.")
                parsed = datetime.strptime(kickoff_text.strip(), "%H:%M").time()
                kickoff = datetime.combine(definitive_date, parsed)
                with session_scope() as session:
                    calendar_repo.update_schedule(session, match.id, user["id"], kickoff_at=kickoff, venue=venue)
                st.success("Horario confirmado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))



def _player_name(player) -> str:
    return player.display_name or player.full_name


def _roster_table(roster: list) -> pd.DataFrame:
    rows=[]
    for item in roster:
        rows.append({
            "Dorsal": item.shirt_number if item.shirt_number is not None else "—",
            "Jugador": _player_name(item.player),
            "Pos.": item.player.primary_position or "—",
        })
    return pd.DataFrame(rows, columns=["Dorsal","Jugador","Pos."])


def _federation_roster_editor(match, team, user: dict, *, side: str) -> None:
    if not (can_admin(user) or can_report(user)):
        return
    with st.expander("Actualizar plantilla desde Federación", expanded=False):
        st.caption("Pega la lista de Federación. Si sabes convocatoria, separa con `TITULARES` y `SUPLENTES`. Si no, pega solo `dorsal;nombre` y quedará como plantilla sin inventar quién jugó.")
        text=st.text_area(
            "Plantilla / convocatoria Federación",height=230,key=f"fed_roster_40_{match.id}_{team.id}_{side}",
            placeholder="TITULARES\n1;Portero titular;POR\n2;Jugador titular;DFC\n...\n\nSUPLENTES\n12;Portero suplente;POR\n14;Jugador suplente;MC",
            label_visibility="collapsed",
        )
        st.caption("También admite `T;7;Nombre;DC` y `S;12;Nombre;POR`. Nunca se toma 'las primeras 11 líneas' como titulares si no lo indicas.")
        if st.button("Guardar plantilla",type="primary",use_container_width=True,key=f"fed_save_40_{match.id}_{team.id}_{side}"):
            try:
                with session_scope() as session:
                    result=matches_repo.import_federation_roster_text(
                        session,team_id=team.id,season_id=match.season_id,actor_id=user["id"],text=text,match_id=match.id
                    )
                detail=f"Plantilla actualizada: {result['rows']} jugadores · {result['created_players']} nuevos"
                if result.get("starters") or result.get("substitutes"):
                    detail += f" · {result.get('starters',0)} titulares · {result.get('substitutes',0)} suplentes"
                st.success(detail + ".")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _render_roster_only(match, team, user: dict, *, side: str) -> None:
    st.markdown(f"#### {team.name}")
    with session_scope() as session:
        roster=players_repo.get_roster(session,team.id,match.season_id)
        parts=matches_repo.get_participations(session,match.id,team.id)
    starters=[p for p in parts if p.starter]
    substitutes=[p for p in parts if not p.starter]
    if starters or substitutes:
        st.caption("Formación desconocida · convocatoria del partido sí identificada")
        if starters:
            st.markdown(f"**🟢 Titulares ({len(starters)})**")
            st.dataframe(pd.DataFrame([{
                "Dorsal": p.shirt_number if p.shirt_number is not None else "—",
                "Jugador": _player_name(p.player),
                "Pos.": p.position or p.player.primary_position or "—",
            } for p in starters]),use_container_width=True,hide_index=True)
        if substitutes:
            st.markdown(f"**🟡 Suplentes ({len(substitutes)})**")
            st.dataframe(pd.DataFrame([{
                "Dorsal": p.shirt_number if p.shirt_number is not None else "—",
                "Jugador": _player_name(p.player),
                "Pos.": p.position or p.player.primary_position or "—",
            } for p in substitutes]),use_container_width=True,hide_index=True)
        roster_part_ids={p.player_id for p in parts}
        others=[r for r in roster if r.player_id not in roster_part_ids]
        if others:
            with st.expander(f"⚪ Resto de plantilla ({len(others)})",expanded=False):
                st.dataframe(_roster_table(others),use_container_width=True,hide_index=True)
    elif roster:
        st.caption("Formación y convocatoria desconocidas · plantilla de temporada ordenada por dorsal")
        st.dataframe(_roster_table(roster),use_container_width=True,hide_index=True)
    else:
        st.info("Todavía no hay plantilla cargada para este equipo en la temporada.")
    _federation_roster_editor(match,team,user,side=side)


def _formation_lineup_editor(match, team, user: dict, *, side: str, formation: str) -> None:
    with session_scope() as session:
        roster=players_repo.get_roster(session,team.id,match.season_id)
        parts=matches_repo.get_participations(session,match.id,team.id)
    slots=slots_for(formation)
    raw_by_order={p.order_index:p for p in parts if p.starter}
    # Only reuse slot positions when they were previously saved against this
    # exact formation. A pasted TITULARES list does not imply tactical order.
    by_order={
        idx: part for idx, part in raw_by_order.items()
        if 0 <= idx < len(slots) and part.position == slots[idx].code
    }
    pitch_rows=[]
    for idx,slot in enumerate(slots):
        part=by_order.get(idx)
        pitch_rows.append({"name":_player_name(part.player) if part else "—","shirt_number":part.shirt_number if part else None,"position":slot.code})
    st.markdown(f"#### {team.name} · {formation}")
    render_campogram(formation,pitch_rows)
    if not (can_admin(user) or can_report(user)):
        return
    with st.expander("Editar XI observado", expanded=not bool(parts)):
        if not roster:
            st.info("Carga primero la plantilla de Federación para poder colocar jugadores en el campograma.")
            _federation_roster_editor(match,team,user,side=side)
            return
        player_map={r.player_id:r for r in roster}
        match_status={p.player_id:("starter" if p.starter else "substitute") for p in parts}
        roster_ids=sorted(
            player_map,
            key=lambda pid: (
                {"starter":0,"substitute":1}.get(match_status.get(pid),2),
                player_map[pid].shirt_number if player_map[pid].shirt_number is not None else 999,
                _player_name(player_map[pid].player),
            ),
        )
        existing_sub_ids=[p.player_id for p in parts if not p.starter and p.player_id in player_map]

        def lineup_option_label(pid):
            if pid is None:
                return "— Sin identificar —"
            item=player_map[pid]
            badge="🟢 TIT" if match_status.get(pid)=="starter" else "🟡 SUP" if match_status.get(pid)=="substitute" else "⚪ PLANTILLA"
            dorsal=f"#{item.shirt_number} · " if item.shirt_number is not None else ""
            return f"{badge} · {dorsal}{_player_name(item.player)}"
        slot_keys=[f"formation_slot_40_{match.id}_{team.id}_{formation}_{idx}" for idx in range(len(slots))]

        # Inicializa todos los slots antes de crear los widgets. Así, al cambiar una
        # posición Streamlit puede recalcular inmediatamente las opciones del resto.
        for idx,key in enumerate(slot_keys):
            default=by_order.get(idx).player_id if by_order.get(idx) and by_order.get(idx).player_id in player_map else None
            if key not in st.session_state or (st.session_state.get(key) is not None and st.session_state.get(key) not in player_map):
                st.session_state[key]=default

        st.caption("Cada jugador seleccionado desaparece automáticamente del resto de posiciones del XI.")
        for idx,slot in enumerate(slots):
            key=slot_keys[idx]
            current=st.session_state.get(key)
            slot_values=[st.session_state.get(k) for k in slot_keys]
            available_ids=available_lineup_player_ids(roster_ids,slot_values,idx)
            choices=[None]+available_ids
            if current is not None and current not in choices and current in player_map:
                choices.append(current)
            index=choices.index(current) if current in choices else 0
            st.selectbox(
                f"{slot.label} · {slot.code}",choices,index=index,
                format_func=lineup_option_label,
                key=key,
            )

        selected=[st.session_state.get(key) for key in slot_keys]
        starter_ids={pid for pid in selected if pid is not None}
        bench_choices=[pid for pid in roster_ids if pid not in starter_ids]
        bench_default=[pid for pid in existing_sub_ids if pid in bench_choices]
        substitute_ids=st.multiselect(
            "🟡 Suplentes / banquillo",bench_choices,default=bench_default,
            format_func=lineup_option_label,
            key=f"formation_bench_40_{match.id}_{team.id}_{formation}_{side}",
            help="No hace falta conocer la posición táctica de los suplentes. Quedan asociados a este partido y diferenciados del XI.",
        )
        st.caption(f"XI identificado: {len(starter_ids)}/11 · Suplentes: {len(substitute_ids)}")
        save=st.button("Guardar XI y banquillo",type="primary",use_container_width=True,key=f"save_formation_xi_40_{match.id}_{team.id}_{formation}_{side}")
        if save:
            try:
                with session_scope() as session:
                    matches_repo.save_known_formation_lineup(
                        session,match_id=match.id,team_id=team.id,actor_id=user["id"],formation=formation,
                        player_ids=selected,substitute_ids=substitute_ids,
                    )
                st.success("XI y banquillo observados guardados.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _neutral_match_study(match, user: dict) -> None:
    st.markdown("### Estudio del partido")
    st.caption("4.0 separa lo que realmente conoces de cada equipo. Una formación puede estar disponible en un lado y no en el otro.")
    local_state=match.home_formation if match.home_formation_known and match.home_formation else "Plantilla / dorsal"
    away_state=match.away_formation if match.away_formation_known and match.away_formation else "Plantilla / dorsal"
    st.markdown(
        f"**Contexto:** {'🎥 Vídeo disponible' if match.video_available else '🚫 Sin vídeo'} · "
        f"**{match.home_team.short_name or match.home_team.name}:** {local_state} · "
        f"**{match.away_team.short_name or match.away_team.name}:** {away_state}"
    )
    known_formations=[f for f in FORMATIONS if slots_for(f)]
    can_edit=can_admin(user) or can_report(user)

    c1,c2,c3=st.columns(3)
    video=c1.toggle("Vídeo disponible",value=bool(match.video_available),disabled=not can_edit,key=f"video40_{match.id}")
    home_known=c2.toggle(f"Formación {match.home_team.short_name or match.home_team.name}",value=bool(match.home_formation_known),disabled=not can_edit,key=f"home_known40_{match.id}")
    away_known=c3.toggle(f"Formación {match.away_team.short_name or match.away_team.name}",value=bool(match.away_formation_known),disabled=not can_edit,key=f"away_known40_{match.id}")
    f1,f2=st.columns(2)
    home_current=match.home_formation if match.home_formation in known_formations else known_formations[0]
    away_current=match.away_formation if match.away_formation in known_formations else known_formations[0]
    home_formation=f1.selectbox("Sistema local",known_formations,index=known_formations.index(home_current),disabled=not home_known or not can_edit,key=f"home_form40_{match.id}")
    away_formation=f2.selectbox("Sistema visitante",known_formations,index=known_formations.index(away_current),disabled=not away_known or not can_edit,key=f"away_form40_{match.id}")
    reference=st.text_input("Referencia de vídeo (opcional)",value=match.video_reference or "",disabled=not video or not can_edit,placeholder="Enlace, plataforma o referencia interna",key=f"video_ref40_{match.id}")
    notes=st.text_area("Notas generales del visionado",value=match.study_notes or "",height=90,disabled=not can_edit,key=f"study_notes40_{match.id}")
    if can_edit and st.button("Guardar configuración del estudio",type="primary",use_container_width=True,key=f"study_save40_{match.id}"):
        try:
            with session_scope() as session:
                matches_repo.update_match_study_context(
                    session,match.id,user["id"],video_available=video,video_reference=reference,
                    home_formation_known=home_known,away_formation_known=away_known,
                    home_formation=home_formation if home_known else None,away_formation=away_formation if away_known else None,study_notes=notes,
                )
            st.success("Configuración guardada.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.markdown("#### Lectura por equipos")
    left,right=st.columns(2,gap="large")
    with left:
        if match.home_formation_known and match.home_formation:
            _formation_lineup_editor(match,match.home_team,user,side="home",formation=match.home_formation)
        else:
            _render_roster_only(match,match.home_team,user,side="home")
    with right:
        if match.away_formation_known and match.away_formation:
            _formation_lineup_editor(match,match.away_team,user,side="away",formation=match.away_formation)
        else:
            _render_roster_only(match,match.away_team,user,side="away")


def _player_context_for_match(match, players: list):
    player_map = {p.id: p for p in players}
    with session_scope() as session:
        home_roster = list(players_repo.get_roster(session, match.home_team_id, match.season_id))
        away_roster = list(players_repo.get_roster(session, match.away_team_id, match.season_id))
        parts = matches_repo.get_participations(session, match.id)
    player_team: dict[int, int] = {}
    shirts: dict[int, int | None] = {}
    status: dict[int, str] = {}
    for row in home_roster:
        player_team[row.player_id] = match.home_team_id
        shirts[row.player_id] = row.shirt_number
    for row in away_roster:
        player_team[row.player_id] = match.away_team_id
        shirts[row.player_id] = row.shirt_number
    for part in parts:
        player_team[part.player_id] = part.team_id
        shirts[part.player_id] = part.shirt_number if part.shirt_number is not None else shirts.get(part.player_id)
        status[part.player_id] = "starter" if part.starter else "substitute"
    return player_map, player_team, shirts, status


def _match_player_label(pid: int, player_map: dict, shirts: dict, status: dict) -> str:
    player = player_map[pid]
    badge = "🟢 TIT" if status.get(pid) == "starter" else "🟡 SUP" if status.get(pid) == "substitute" else "⚪ PLANTILLA"
    shirt = shirts.get(pid)
    dorsal = f"#{shirt} · " if shirt is not None else ""
    return f"{badge} · {dorsal}{player.display_name or player.full_name}"


def _neutral_staff_opinion(match, user: dict, players: list) -> None:
    if not can_report(user) or not is_schedule_confirmed(match):
        return
    st.markdown("### Tu lectura del partido")
    st.caption("Partido neutral: valora a los dos equipos y señala únicamente a los jugadores que realmente te hayan llamado la atención. No estás iniciando un seguimiento.")
    player_map, player_team, shirts, status = _player_context_for_match(match, players)
    with session_scope() as session:
        existing = sporting_repo.get_match_opinion(session, match.id, user["id"])
        existing_players = sporting_repo.opinion_players(session, existing.id) if existing else []
    existing_by_player = {row.player_id: row for row in existing_players}
    ordered = sorted(
        [pid for pid in player_map if pid in player_team],
        key=lambda pid: (
            0 if player_team.get(pid) == match.home_team_id else 1,
            {"starter": 0, "substitute": 1}.get(status.get(pid), 2),
            shirts.get(pid) if shirts.get(pid) is not None else 999,
            player_map[pid].display_name or player_map[pid].full_name,
        ),
    )
    default_selected = [pid for pid in existing_by_player if pid in ordered]
    selected = st.multiselect(
        "Jugadores destacados (opcional)", ordered, default=default_selected,
        format_func=lambda pid: _match_player_label(pid, player_map, shirts, status),
        key=f"neutral_highlights_42_{match.id}_{user['id']}",
        help="Señalar aquí no abre un seguimiento. Solo crea una señal para la lectura conjunta de Dirección Deportiva.",
    )
    with st.form(f"neutral_opinion_42_{match.id}_{user['id']}"):
        c1, c2 = st.columns(2)
        home_rating = c1.number_input(
            f"Nota {match.home_team.name}", 0.0, 10.0,
            float(existing.home_team_rating or 0.0) if existing else 0.0, .5, help="0 = sin valorar",
        )
        away_rating = c2.number_input(
            f"Nota {match.away_team.name}", 0.0, 10.0,
            float(existing.away_team_rating or 0.0) if existing else 0.0, .5, help="0 = sin valorar",
        )
        summary = st.text_area(
            "Qué te deja el partido", value=existing.summary or "" if existing else "", height=90,
            placeholder="Qué equipo te convenció, qué patrones viste, qué merece recordarse...",
        )
        player_rows = []
        if selected:
            st.markdown("**Jugadores destacados**")
            for pid in selected:
                previous = existing_by_player.get(pid)
                c1, c2 = st.columns([1, 3])
                rating = c1.number_input(
                    f"Nota · {player_map[pid].display_name or player_map[pid].full_name}", 0.0, 10.0,
                    float(previous.rating or 0.0) if previous else 0.0, .5,
                    key=f"neutral_player_rate_42_{match.id}_{user['id']}_{pid}",
                )
                note = c2.text_input(
                    f"Apunte · {player_map[pid].display_name or player_map[pid].full_name}",
                    value=previous.note or "" if previous else "",
                    key=f"neutral_player_note_42_{match.id}_{user['id']}_{pid}",
                )
                player_rows.append({"player_id": pid, "team_id": player_team[pid], "rating": rating, "note": note})
        save = st.form_submit_button("Guardar mi lectura", type="primary", use_container_width=True)
    if save:
        try:
            with session_scope() as session:
                sporting_repo.save_neutral_opinion(
                    session, match_id=match.id, user_id=user["id"],
                    home_team_rating=home_rating, away_team_rating=away_rating,
                    summary=summary, player_rows=player_rows,
                )
            st.success("Lectura guardada.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _start_tracking_button(player_id: int, user: dict, *, key: str) -> None:
    if not can_track_players(user):
        return
    if st.button("Iniciar seguimiento", use_container_width=True, key=key):
        try:
            with session_scope() as session:
                sporting_repo.start_player_tracking(session, player_id=player_id, actor_id=user["id"])
            st.session_state["workspace_player_id"] = int(player_id)
            from core.navigation import request_navigation
            request_navigation("Jugadores")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _director_match_reading(match, user: dict, *, is_own_match: bool) -> None:
    if not can_direct(user):
        return
    st.markdown("### Dirección Deportiva · lectura conjunta")
    if is_own_match:
        with session_scope() as session:
            reading = sporting_repo.own_match_reading(session, match.id)
        reports = reading["reports"]
        if not reports:
            st.info("Todavía no hay postpartidos entregados. Dirección Deportiva leerá el consenso cuando empiecen a llegar.")
            return
        c1, c2, c3 = st.columns(3)
        c1.metric("Postpartidos", len(reports))
        c2.metric("No Name · consenso", "—" if reading["own_weighted"] is None else f"{reading['own_weighted']:.2f}")
        c3.metric("Rival · consenso", "—" if reading["rival_weighted"] is None else f"{reading['rival_weighted']:.2f}")
        st.caption(
            f"No Name: {sporting_repo.consensus_label(reading.get('own_dispersion'), len(reports))} · "
            f"Rival: {sporting_repo.consensus_label(reading.get('rival_dispersion'), len(reports))}. "
            "Los jugadores de No Name se leen como rendimiento de plantilla, nunca como candidatos a seguimiento de mercado."
        )
        with st.expander("Ver opiniones del staff", expanded=False):
            for report in reports:
                weight = reading["weights"].get(report.reporter_id)
                w = float(weight.own_match_weight if weight else 1.0)
                st.markdown(
                    f"**{report.reporter.full_name}** · peso x{w:.2f} · "
                    f"No Name {'—' if report.own_team_rating is None else f'{report.own_team_rating:.1f}'} · "
                    f"Rival {'—' if report.rival_team_rating is None else f'{report.rival_team_rating:.1f}'}"
                )
                if report.key_takeaways:
                    st.caption(report.key_takeaways)
        own_players = [row for row in reading["players"] if row["scope"] == "own"]
        rival_players = [row for row in reading["players"] if row["scope"] == "rival"]
        if own_players:
            st.markdown("#### No Name · rendimiento ponderado")
            st.dataframe(pd.DataFrame([{
                "Jugador": row["player"].display_name or row["player"].full_name,
                "Nota": None if row["weighted_rating"] is None else round(row["weighted_rating"], 2),
                "Opiniones": row["reporter_count"],
                "Consenso": sporting_repo.consensus_label(row["dispersion"], row["reporter_count"]),
            } for row in own_players]), hide_index=True, use_container_width=True)
        if rival_players:
            st.markdown("#### Rival · señales del postpartido")
            st.caption("Que un rival destaque aquí no significa que esté en seguimiento. Es solo una señal nacida de nuestros postpartidos.")
            for row in rival_players[:8]:
                with st.container(border=True):
                    a, b = st.columns([4, 1])
                    a.markdown(f"**{row['player'].display_name or row['player'].full_name}** · {row['team'].name}")
                    a.caption(f"Nota {'—' if row['weighted_rating'] is None else f'{row['weighted_rating']:.2f}'} · {row['reporter_count']} opiniones · {sporting_repo.consensus_label(row.get('dispersion'), row['reporter_count'])}")
                    if can_track_players(user):
                        with b:
                            _start_tracking_button(row["player"].id, user, key=f"track_ownmatch_rival_42_{match.id}_{row['player'].id}")
    else:
        with session_scope() as session:
            reading = sporting_repo.neutral_match_reading(session, match.id)
        opinions = reading["opinions"]
        if not opinions:
            st.info("Todavía no hay lecturas del staff para este partido neutral.")
            return
        c1, c2, c3 = st.columns(3)
        c1.metric("Lecturas", len(opinions))
        c2.metric(match.home_team.short_name or match.home_team.name, "—" if reading["home_weighted"] is None else f"{reading['home_weighted']:.2f}")
        c3.metric(match.away_team.short_name or match.away_team.name, "—" if reading["away_weighted"] is None else f"{reading['away_weighted']:.2f}")
        st.caption(
            f"{match.home_team.short_name or match.home_team.name}: {sporting_repo.consensus_label(reading.get('home_dispersion'), len(opinions))} · "
            f"{match.away_team.short_name or match.away_team.name}: {sporting_repo.consensus_label(reading.get('away_dispersion'), len(opinions))}"
        )
        with st.expander("Ver opiniones del staff", expanded=False):
            for opinion in opinions:
                weight = reading["weights"].get(opinion.user_id)
                w = float(weight.neutral_match_weight if weight else 1.0)
                st.markdown(
                    f"**{opinion.user.full_name}** · peso x{w:.2f} · "
                    f"{match.home_team.short_name or match.home_team.name} {'—' if opinion.home_team_rating is None else f'{opinion.home_team_rating:.1f}'} · "
                    f"{match.away_team.short_name or match.away_team.name} {'—' if opinion.away_team_rating is None else f'{opinion.away_team_rating:.1f}'}"
                )
                if opinion.summary:
                    st.caption(opinion.summary)
        if reading["players"]:
            st.markdown("#### Jugadores señalados por el staff")
            st.caption("Primero aparecen como señales. Solo quien tenga permiso especial puede convertir una señal en seguimiento individual.")
            for row in reading["players"][:10]:
                with st.container(border=True):
                    a, b = st.columns([4, 1])
                    a.markdown(f"**{row['player'].display_name or row['player'].full_name}** · {row['team'].name}")
                    rating = "—" if row["weighted_rating"] is None else f"{row['weighted_rating']:.2f}"
                    a.caption(f"{row['mentions']} persona(s) lo señalaron · nota ponderada {rating} · {sporting_repo.consensus_label(row.get('dispersion'), row['mentions'])}")
                    if row["notes"]:
                        a.write(" · ".join(row["notes"][:3]))
                    if can_track_players(user):
                        with b:
                            _start_tracking_button(row["player"].id, user, key=f"track_neutral_42_{match.id}_{row['player'].id}")


def _individual_tracking_form(match, user: dict, players: list) -> None:
    if not can_track_players(user) or not is_schedule_confirmed(match):
        return
    with session_scope() as session:
        own = players_repo.get_own_team(session)
        own_ids = set()
        if own:
            own_ids = {r.player_id for r in players_repo.get_roster(session, own.id, match.season_id)}
    external = [p for p in players if p.id not in own_ids]
    if not external:
        return
    st.markdown("### Seguimiento individual")
    st.caption("Permiso especial. Aquí sí se abre evidencia longitudinal para un jugador externo. Los jugadores de No Name quedan fuera de este flujo.")
    player_map = {p.id: p for p in external}
    pid = st.selectbox(
        "Jugador externo", list(player_map),
        format_func=lambda x: player_map[x].display_name or player_map[x].full_name,
        key=f"individual_track_player_42_{match.id}",
    )
    player = player_map[pid]
    with session_scope() as session:
        model_roles = planning_repo.list_model_roles(session)
    role_options = [None] + [r.id for r in model_roles if not player.primary_position or r.position == player.primary_position]
    role_id = st.selectbox(
        "Rol No Name", role_options,
        format_func=lambda rid: "Sin rol todavía" if rid is None else next(f"{r.position} · {r.name}" for r in model_roles if r.id == rid),
        key=f"individual_track_role_42_{match.id}_{pid}",
    )
    with session_scope() as session:
        criteria = planning_repo.list_model_criteria(session, role_id) if role_id else []
    with st.form(f"individual_track_form_42_{match.id}_{pid}_{role_id}"):
        c1, c2 = st.columns(2)
        position = c1.selectbox("Posición observada", POSITIONS, index=POSITIONS.index(player.primary_position) if player.primary_position in POSITIONS else 0)
        rating = c2.number_input("Rendimiento del partido", 0.0, 10.0, 0.0, .5)
        scores = {}
        for criterion in criteria:
            scores[criterion.id] = st.number_input(f"{criterion.name} · peso {criterion.weight}", 0.0, 10.0, 0.0, .5, key=f"track_crit_42_{match.id}_{pid}_{criterion.id}")
        summary = st.text_area("Conclusión del visionado", height=90)
        recommendation = st.selectbox("Siguiente acción", ["Sin conclusión", "Volver a ver", "Seguimiento", "Prioritario", "Descartado"])
        strengths = st.text_area("Fortalezas", height=60)
        weaknesses = st.text_area("Dudas / riesgos", height=60)
        save = st.form_submit_button("Guardar en seguimiento", type="primary", use_container_width=True)
    if save:
        try:
            clean_scores = {cid: score for cid, score in scores.items() if score and score > 0}
            with session_scope() as session:
                sporting_repo.start_player_tracking(session, player_id=pid, actor_id=user["id"])
                fit = planning_repo.weighted_model_fit(planning_repo.list_model_criteria(session, role_id), clean_scores) if role_id else None
                obs = planning_repo.create_observation(
                    session, player_id=pid, reviewer_id=user["id"], match_id=match.id,
                    mission_id=None, source_type="specific", observation_level="observation", model_role_id=role_id,
                )
                planning_repo.save_observation(
                    session, obs.id, user["id"], observed_position=position,
                    general_rating=rating if rating > 0 else None, model_fit_score=fit,
                    attributes=clean_scores, summary=summary, recommendation=recommendation,
                    strengths=strengths, weaknesses=weaknesses, model_role_id=role_id,
                    observation_level="observation", submit=True,
                )
            st.success("Observación añadida al seguimiento individual del jugador.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _manage_postmatch_assignments_4231(match, user: dict, assignments: list) -> None:
    """Recover already published postmatches without deleting or republishing them."""
    if not can_admin(user) or match.status != "published":
        return
    from repositories import users as users_repo
    with session_scope() as session:
        reporters = [item for item in users_repo.list_users(session, active_only=True)
                     if item.deleted_at is None and users_repo.user_has_role(session, item.id, "reporter")]
    options = {item.id: item.full_name for item in reporters}
    active = [assignment for assignment in assignments if assignment.status != "waived"]
    selected_default = [assignment.user_id for assignment in active if assignment.user_id in options]
    with st.expander("Informadores asignados · gestionar postpartido", expanded=not bool(active)):
        if not active:
            st.error("Postpartido sin informadores: nadie recibirá una tarea ni verá «Abrir informe». Asígnalos aquí sin volver a publicar el partido.")
        else:
            st.caption(f"{len(active)} asignación(es) registradas. Los informes ya entregados no se eliminan al actualizar el reparto.")
        unavailable = [assignment.user_id for assignment in active if assignment.user_id not in options]
        if unavailable:
            st.warning("Hay asignaciones a cuentas no disponibles (IDs: " + ", ".join(map(str, unavailable)) + "). Revisa estos usuarios antes de modificar el reparto.")
        if not options:
            st.warning("No existen usuarios activos con rol Informador. Administración → Usuarios permite asignar el rol.")
            return
        with st.form(f"manage_published_reporters_4231_{match.id}"):
            selected_ids = st.multiselect("Informadores que deben completar este postpartido", list(options),
                                          default=selected_default,
                                          format_func=lambda uid: f"{options[uid]} · ID {uid}")
            st.caption("Selecciona al menos uno. La operación crea o actualiza asignaciones auditadas; no duplica el partido, informes ni jugadores.")
            save = st.form_submit_button("Guardar asignaciones y activar tareas", type="primary",
                                         use_container_width=True, disabled=not selected_ids)
        if save:
            try:
                with session_scope() as session:
                    assigned = matches_repo.assign_reporters(session, match.id, selected_ids, user["id"],
                                                              due_at=match.report_due_at, required=True)
                    if len(assigned) != len(set(selected_ids)):
                        raise RuntimeError("No se han creado todas las asignaciones; la operación se ha revertido.")
                st.success("Asignaciones guardadas. Los Informadores verán la tarea en Inicio y el botón «Abrir informe» en Jornada.")
                st.rerun()
            except Exception as exc:
                st.error(f"No se pudieron guardar las asignaciones: {exc}")


def _render_match_hub(user: dict, match_id: int) -> None:
    mode=st.session_state.get("match_hub_mode")
    if st.button("← Volver a la jornada",key=f"back_match_38_{match_id}"):
        st.session_state.pop("workspace_match_id",None); st.session_state.pop("match_hub_mode",None); st.rerun()
    if mode=="postmatch":
        if st.button("← Volver a la ficha del partido",key=f"back_post_38_{match_id}"):
            st.session_state.pop("match_hub_mode",None); st.rerun()
        from views import postmatch
        postmatch.render(user)
        return
    if mode=="report":
        if st.button("← Volver a la ficha del partido",key=f"back_report_38_{match_id}"):
            st.session_state.pop("match_hub_mode",None); st.rerun()
        from views import reports
        reports.render_match_report(user,match_id)
        return

    with session_scope() as session:
        data=workspaces.load_match_workspace(session,match_id=match_id,user_id=user["id"])
        players=workspaces.match_candidate_players(session,match_id)
    match=data["match"]
    page_header(_match_title(match),f"{match.round_name} · {match.competition.name}")
    kind="ready" if is_schedule_confirmed(match) else "pending"
    st.markdown(status_badge(kind,"Horario confirmado" if kind=="ready" else "Programación provisional"))
    if match.match_date == local_today():
        st.caption(f"HOY · {calendar_repo.schedule_label(match)}")
    else:
        st.caption(calendar_repo.schedule_label(match))
    if match.home_score is not None and match.away_score is not None:
        st.metric("Resultado",f"{match.home_score} - {match.away_score}")
    tc1,tc2=st.columns(2)
    if tc1.button(f"Ver {match.home_team.short_name or match.home_team.name}",use_container_width=True,key=f"team_home38_{match.id}"):
        st.session_state["workspace_team_id"]=match.home_team_id; st.rerun()
    if tc2.button(f"Ver {match.away_team.short_name or match.away_team.name}",use_container_width=True,key=f"team_away38_{match.id}"):
        st.session_state["workspace_team_id"]=match.away_team_id; st.rerun()

    primary_done=False
    if data["is_own_match"] and is_schedule_confirmed(match) and can_admin(user) and match.status in {"scheduled","draft"}:
        if st.button("Preparar partido",type="primary",use_container_width=True,key=f"prepare38_{match.id}"):
            st.session_state["postmatch_existing_match_id"]=match.id; st.session_state["match_hub_mode"]="postmatch"; st.rerun()
        primary_done=True
    elif data["is_own_match"] and can_report(user) and data.get("my_assignment") and data["my_assignment"].status!="waived":
        if st.button("Abrir informe",type="primary",use_container_width=True,key=f"report38_{match.id}"):
            st.session_state["match_hub_mode"]="report"; st.rerun()
        primary_done=True
    if not primary_done and not is_schedule_confirmed(match) and can_admin(user):
        st.info("Confirma una hora real para habilitar el trabajo operativo.")
    if data["is_own_match"] and match.status == "published":
        if can_admin(user):
            _manage_postmatch_assignments_4231(match, user, data["assignments"])
        elif can_report(user) and not data.get("my_assignment"):
            st.warning("Este postpartido está publicado, pero tu usuario no tiene asignación. Pide a Administración que abra este partido y utilice «Informadores asignados · gestionar postpartido». Tu rol Informador por sí solo no te asigna todos los encuentros.")
        elif can_report(user) and data["my_assignment"].status == "waived":
            st.info("Tu asignación para este partido consta como «No requerido». Administración puede reactivarla desde la ficha del encuentro.")

    _schedule_form(match,user)

    if not data["is_own_match"]:
        _neutral_match_study(match,user)

    if data["is_own_match"]:
        st.info("**Partido No Name · flujo 4.2.2**: el staff completa su postpartido. Dirección Deportiva compara el criterio conjunto. Los jugadores propios se leen como rendimiento de plantilla, nunca como seguimiento de mercado.")
    else:
        st.info("**Partido neutral · flujo 4.2.2**: cada miembro deja una lectura ligera del partido y puede señalar jugadores. Señalar no equivale a seguir; el seguimiento individual es un permiso aparte.")

    if data["is_own_match"]:
        st.markdown("### Estado del postpartido")
        active_assignments = [a for a in data["assignments"] if a.status != "waived"]
        st.markdown(f"**Informes** · {len(data['reports'])} registrados / {len(active_assignments)} informadores asignados")
        from core.constants import REPORT_STATUSES
        for report in data["reports"][:8]:
            st.caption(f"{report.reporter.full_name} · {REPORT_STATUSES.get(report.status, report.status)}")
    else:
        with session_scope() as session:
            neutral_reading = sporting_repo.neutral_match_reading(session, match.id)
        st.markdown("### Estado de la lectura")
        st.markdown(f"**Opiniones del staff** · {len(neutral_reading['opinions'])}")
        if neutral_reading["players"]:
            st.caption(f"{len(neutral_reading['players'])} jugadores han sido señalados al menos una vez.")

    if not data["is_own_match"]:
        _neutral_staff_opinion(match, user, players)
    _director_match_reading(match, user, is_own_match=data["is_own_match"])
    if data["is_own_match"] and can_track_players(user):
        with st.expander("Seguimiento individual de un rival · opcional", expanded=False):
            _individual_tracking_form(match, user, players)
    else:
        _individual_tracking_form(match, user, players)


def render(user: dict) -> None:
    team_opened=st.session_state.get("workspace_team_id")
    if team_opened:
        from views import team_hub
        team_hub.render(user,int(team_opened)); return
    opened=st.session_state.get("workspace_match_id")
    if opened:
        _render_match_hub(user,int(opened)); return
    page_header("Jornada","Partidos, postpartidos y lectura del staff desde un único lugar.")
    with session_scope() as session:
        active=players_repo.get_active_season(session); own=players_repo.get_own_team(session)
        if not active:
            st.warning("No hay temporada activa."); return
        rounds=workspaces.list_rounds(session,active.id)
        default=workspaces.default_round(session,active.id,own.id if own else None)
    if not rounds:
        st.info("Todavía no hay calendario cargado."); return
    current=st.session_state.get("round_39")
    if current not in rounds: current=default if default in rounds else rounds[0]
    idx=rounds.index(current)
    c1,c2,c3=st.columns([1,4,1])
    if c1.button("←",disabled=idx==0,use_container_width=True,key="round_prev_38"):
        st.session_state["round_39"]=rounds[idx-1]; st.rerun()
    selected=c2.selectbox("Jornada",rounds,index=idx,label_visibility="collapsed",key="round_select_38")
    if selected!=current:
        st.session_state["round_39"]=selected; st.rerun()
    if c3.button("→",disabled=idx==len(rounds)-1,use_container_width=True,key="round_next_38"):
        st.session_state["round_39"]=rounds[idx+1]; st.rerun()
    with session_scope() as session:
        data=workspaces.load_round_workspace(session,season_id=active.id,round_name=current,user_id=user["id"])
    st.markdown(f"### {current}")
    for match in data["matches"]:
        own_match=bool(data["own_team"] and data["own_team"].id in {match.home_team_id,match.away_team_id})
        with st.container(border=True):
            a,b=st.columns([5,1])
            prefix="⚽ " if own_match else ""
            a.markdown(f"**{prefix}{_match_title(match)}**")
            bits=[]
            if match.match_date == local_today():
                bits.append("HOY")
            bits.append(calendar_repo.schedule_label(match))
            ac=data["assignment_counts"].get(match.id,{})
            if not own_match:
                bits.append("🎥 vídeo" if match.video_available else "sin vídeo")
                known_count=int(bool(match.home_formation_known))+int(bool(match.away_formation_known))
                bits.append(f"formaciones {known_count}/2")
            if ac.get("total"): bits.append(f"📋 {ac.get('total')} informadores")
            a.caption(" · ".join(bits))
            if b.button("Abrir",type="primary" if own_match else "secondary",use_container_width=True,key=f"open_round39_{match.id}"):
                _open_match(match.id)
    if can_admin(user):
        with st.expander("Importar calendario / mantenimiento excepcional"):
            st.caption("Estas herramientas quedan fuera del flujo diario.")
            from views import calendar as legacy_calendar
            # Import/schedule tools remain available, but not as primary navigation.
            if st.button("Abrir herramientas de calendario",use_container_width=True,key="legacy_calendar_39"):
                st.session_state["calendar_tools_39"]=not st.session_state.get("calendar_tools_39",False)
            if st.session_state.get("calendar_tools_39"):
                legacy_calendar.render(user)
