from __future__ import annotations

from datetime import datetime
import json

import pandas as pd
import streamlit as st

from core.clock import local_today
from core.constants import FORMATIONS, POSITIONS
from core.formations import available_lineup_player_ids, slots_for
from core.database import session_scope
from core.permissions import can_admin, can_direct, can_report, can_scout
from core.presentation import SCOUT_LEVELS, status_badge
from core.schedule import is_schedule_confirmed
from repositories import calendar as calendar_repo
from repositories import matches as matches_repo
from repositories import planning as planning_repo
from repositories import players as players_repo
from repositories import scouting as base_repo
from repositories import workspaces
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
    if not can_scout(user):
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
    if not can_scout(user):
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
    can_edit=can_scout(user)

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


def _mission_planning(match, user: dict, players: list) -> None:
    if not can_direct(user):
        return
    with st.expander("Planificar observación", expanded=False):
        with session_scope() as session:
            scouts = planning_repo.list_scout_users(session)
        if not scouts:
            st.info("No hay usuarios con capacidad Scout.")
            return
        player_map = {p.id: p for p in players}
        with st.form(f"mission_38_{match.id}"):
            target_ids = st.multiselect("Objetivos", list(player_map), format_func=lambda pid: player_map[pid].display_name or player_map[pid].full_name)
            assignee = st.selectbox("Responsable", [u.id for u in scouts], format_func=lambda uid: next(u.full_name for u in scouts if u.id == uid))
            priority = st.select_slider("Prioridad", [3, 2, 1], value=2, format_func=lambda x: {1:"Alta",2:"Media",3:"Baja"}[x])
            purpose = st.text_input("Objetivo", placeholder="Qué queremos resolver en este visionado")
            create = st.form_submit_button("Asignar próxima acción", type="primary", use_container_width=True)
        if create:
            try:
                title = "Observar " + (player_map[target_ids[0]].full_name if len(target_ids) == 1 else f"{len(target_ids)} jugadores" if target_ids else _match_title(match))
                with session_scope() as session:
                    planning_repo.create_mission(
                        session, match_id=match.id, mission_type="player" if len(target_ids) <= 1 else "multi_player",
                        title=title, assigned_to=assignee, requested_by=user["id"], player_ids=target_ids,
                        purpose=purpose, priority=priority, due_at=match.kickoff_at if is_schedule_confirmed(match) else None,
                    )
                st.success("Próxima acción asignada.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _scouting_form(match, user: dict, players: list) -> None:
    if not can_scout(user):
        return
    st.markdown("### Scouting")
    if not is_schedule_confirmed(match):
        st.caption("Puedes planificar el visionado, pero la observación se habilita cuando exista fecha y hora reales.")
        return
    if not players:
        st.info("No hay jugadores asociados a las plantillas de este partido.")
        return
    player_map = {p.id: p for p in players}
    with session_scope() as session:
        all_parts=matches_repo.get_participations(session,match.id)
        all_roster=list(players_repo.get_roster(session,match.home_team_id,match.season_id))+list(players_repo.get_roster(session,match.away_team_id,match.season_id))
    participant_status={p.player_id:("starter" if p.starter else "substitute") for p in all_parts}
    participant_shirt={p.player_id:p.shirt_number for p in all_parts}
    roster_shirt={r.player_id:r.shirt_number for r in all_roster}

    def scout_player_label(pid: int) -> str:
        player=player_map[pid]
        status=participant_status.get(pid)
        badge="🟢 TIT" if status=="starter" else "🟡 SUP" if status=="substitute" else "⚪ PLANTILLA"
        shirt=participant_shirt.get(pid)
        if shirt is None:
            shirt=roster_shirt.get(pid)
        dorsal=f"#{shirt} · " if shirt is not None else ""
        return f"{badge} · {dorsal}{player.display_name or player.full_name}"

    # Neutral matches can easily contain 35-50 known players. Filter by team
    # before asking the Scout to select a player; this keeps the daily workflow fast.
    with session_scope() as session:
        own=players_repo.get_own_team(session)
        neutral=not own or own.id not in {match.home_team_id,match.away_team_id}
        if neutral:
            home_ids={r.player_id for r in players_repo.get_roster(session,match.home_team_id,match.season_id)}
            away_ids={r.player_id for r in players_repo.get_roster(session,match.away_team_id,match.season_id)}
            for part in matches_repo.get_participations(session,match.id,match.home_team_id): home_ids.add(part.player_id)
            for part in matches_repo.get_participations(session,match.id,match.away_team_id): away_ids.add(part.player_id)
        else:
            home_ids=away_ids=set()
    if neutral:
        team_scope=st.segmented_control(
            "Equipo",["Ambos",match.home_team.name,match.away_team.name],default="Ambos",
            key=f"scout_team_scope40_{match.id}",
        ) or "Ambos"
        if team_scope==match.home_team.name:
            player_map={pid:p for pid,p in player_map.items() if pid in home_ids}
        elif team_scope==match.away_team.name:
            player_map={pid:p for pid,p in player_map.items() if pid in away_ids}
        if not player_map:
            st.info("No hay jugadores cargados para ese equipo. Añade primero la plantilla de Federación en Estudio del partido.")
            return
    st.markdown("#### ¿Qué tipo de seguimiento quieres hacer?")
    scout_modes=["⚡ Barrido rápido","👁 Observación individual","📁 Dossier completo"]
    mode=st.segmented_control("Tipo de seguimiento",scout_modes,default=scout_modes[0],key=f"scout_level_38_{match.id}",label_visibility="collapsed") or scout_modes[0]
    level={scout_modes[0]:"scan",scout_modes[1]:"observation",scout_modes[2]:"dossier"}[mode]
    if level=="scan":
        st.caption("⚡ **Barrido rápido:** compara varios jugadores del partido con nota + apunte corto. Úsalo para detectar quién merece volver a verse.")
    elif level=="observation":
        st.caption("👁 **Observación individual:** un jugador, posición, rendimiento y encaje con el Modelo No Name.")
    else:
        st.caption("📁 **Dossier completo:** evaluación profunda para jugadores que ya están en seguimiento: nivel, proyección, fortalezas y riesgos.")
    if level == "scan":
        ordered_ids=sorted(player_map, key=lambda pid: ({"starter":0,"substitute":1}.get(participant_status.get(pid),2), (participant_shirt.get(pid) if participant_shirt.get(pid) is not None else 999), (player_map[pid].display_name or player_map[pid].full_name)))
        selected = st.multiselect("Jugadores", ordered_ids, format_func=scout_player_label, key=f"scan_ids_38_{match.id}")
        if not selected:
            st.caption("Selecciona uno o varios jugadores para un barrido rápido.")
            return
        with st.form(f"scan_form_38_{match.id}"):
            rows=[]
            for pid in selected:
                p=player_map[pid]
                a,b=st.columns([1,3])
                rating=a.number_input(f"{p.display_name or p.full_name} · nota",0.0,10.0,0.0,.5,key=f"scan38_rate_{match.id}_{pid}")
                note=b.text_input(f"{p.display_name or p.full_name} · apunte",key=f"scan38_note_{match.id}_{pid}")
                rows.append({"player_id":pid,"general_rating":rating,"observed_position":p.primary_position,"summary":note})
            save=st.form_submit_button("Guardar barrido",type="primary",use_container_width=True)
        if save:
            with session_scope() as session:
                count=planning_repo.save_quick_match_observations(session,match_id=match.id,reviewer_id=user["id"],rows=rows)
            st.success(f"{count} observaciones guardadas.") if count else st.warning("Asigna una nota superior a 0 para guardar.")
            if count: st.rerun()
        return

    ordered_ids=sorted(player_map, key=lambda pid: ({"starter":0,"substitute":1}.get(participant_status.get(pid),2), (participant_shirt.get(pid) if participant_shirt.get(pid) is not None else 999), (player_map[pid].display_name or player_map[pid].full_name)))
    pid=st.selectbox("Jugador",ordered_ids,format_func=scout_player_label,key=f"scout_player_38_{match.id}_{level}")
    player=player_map[pid]
    with session_scope() as session:
        roles=planning_repo.list_model_roles(session)
    role_options=[None]+[r.id for r in roles if not player.primary_position or r.position==player.primary_position] or [None]
    role_id=st.selectbox("Rol No Name",role_options,format_func=lambda rid:"Sin rol todavía" if rid is None else next(f"{r.position} · {r.name}" for r in roles if r.id==rid),key=f"scout_role_38_{match.id}_{pid}_{level}")
    with session_scope() as session:
        criteria=planning_repo.list_model_criteria(session,role_id) if role_id else []
    with st.form(f"obs_form_38_{match.id}_{pid}_{level}_{role_id}"):
        c1,c2=st.columns(2)
        position=c1.selectbox("Posición observada",POSITIONS,index=POSITIONS.index(player.primary_position) if player.primary_position in POSITIONS else 0)
        rating=c2.number_input("Rendimiento del partido",0.0,10.0,0.0,.5)
        scores={}
        if role_id:
            st.markdown("**Criterios del Modelo No Name**")
            for criterion in criteria:
                scores[criterion.id]=st.number_input(f"{criterion.name} · peso {criterion.weight}",0.0,10.0,0.0,.5,key=f"crit38_{match.id}_{pid}_{criterion.id}_{level}")
        summary=st.text_area("Conclusión",height=80)
        recommendation=st.selectbox("Recomendación",["Sin conclusión","Volver a ver","Seguimiento","Prioritario","Descartado"])
        current=potential=None; strengths=weaknesses=None
        if level=="dossier":
            c3,c4=st.columns(2)
            current=c3.number_input("Nivel actual",0.0,10.0,0.0,.5)
            potential=c4.number_input("Proyección",0.0,10.0,0.0,.5)
            strengths=st.text_area("Fortalezas",height=70)
            weaknesses=st.text_area("Riesgos / dudas",height=70)
        submit=st.form_submit_button("Guardar observación",type="primary",use_container_width=True)
    if submit:
        try:
            clean_scores={cid:score for cid,score in scores.items() if score and score>0}
            with session_scope() as session:
                fit=planning_repo.weighted_model_fit(planning_repo.list_model_criteria(session,role_id),clean_scores) if role_id else None
                obs=planning_repo.create_observation(session,player_id=pid,reviewer_id=user["id"],match_id=match.id,source_type="specific",observation_level=level,model_role_id=role_id)
                planning_repo.save_observation(
                    session,obs.id,user["id"],observed_position=position,general_rating=rating if rating>0 else None,
                    model_fit_score=fit,attributes=clean_scores,summary=summary,recommendation=recommendation,
                    current_level=current if current and current>0 else None,potential_score=potential if potential and potential>0 else None,
                    strengths=strengths,weaknesses=weaknesses,model_role_id=role_id,observation_level=level,submit=True,
                )
            st.success("Observación guardada.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _rival_analysis(match, user: dict, data: dict) -> None:
    if not can_scout(user):
        return
    relevant=[m for m in data["my_missions"] if m.mission_type in {"team","rival_analysis"} and m.status in {"pending","in_progress"}]
    if not relevant or not is_schedule_confirmed(match):
        return
    mission=relevant[0]
    st.markdown("### Análisis rival")
    with st.form(f"rival_analysis_38_{mission.id}"):
        structure=st.text_area("Estructura",height=70)
        behavior=st.text_area("Qué hacen",height=90,placeholder="Con balón / sin balón")
        danger=st.text_area("Qué nos puede hacer daño",height=80,placeholder="Jugadores o patrones")
        keys=st.text_area("Claves para No Name",height=80)
        with st.expander("Añadir detalle"):
            transitions=st.text_area("Transiciones",height=60)
            set_pieces=st.text_area("ABP",height=60)
        save=st.form_submit_button("Entregar análisis",type="primary",use_container_width=True)
    if save:
        text="\n\n".join(x for x in [f"ESTRUCTURA\n{structure.strip()}" if structure.strip() else "",f"QUÉ HACEN\n{behavior.strip()}" if behavior.strip() else "",f"QUÉ NOS PUEDE HACER DAÑO\n{danger.strip()}" if danger.strip() else "",f"CLAVES PARA NO NAME\n{keys.strip()}" if keys.strip() else "",f"TRANSICIONES\n{transitions.strip()}" if transitions.strip() else "",f"ABP\n{set_pieces.strip()}" if set_pieces.strip() else ""] if x)
        with session_scope() as session:
            planning_repo.update_mission_status(session,mission.id,user["id"],status="completed",result_summary=text)
        st.success("Análisis entregado.")
        st.rerun()


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

    _schedule_form(match,user)

    if not data["is_own_match"]:
        _neutral_match_study(match,user)

    st.markdown("### Estado del partido")
    c1,c2=st.columns(2)
    with c1:
        st.markdown(f"**Scouting** · {len(data['missions'])} tareas")
        for mission in data["missions"][:6]:
            targets=data["targets_by_mission"].get(mission.id,[])
            names=", ".join(t.player.display_name or t.player.full_name for t in targets) or (mission.target_team.name if mission.target_team else mission.title)
            st.caption(f"{mission.assignee.full_name}: {names} · {mission.status}")
    with c2:
        st.markdown(f"**Informes** · {len(data['reports'])}/{len(data['assignments']) or len(data['reports'])}")
        for report in data["reports"][:6]:
            st.caption(f"{report.reporter.full_name} · {report.status}")

    _mission_planning(match,user,players)
    _rival_analysis(match,user,data)
    _scouting_form(match,user,players)


def render(user: dict) -> None:
    team_opened=st.session_state.get("workspace_team_id")
    if team_opened:
        from views import team_hub
        team_hub.render(user,int(team_opened)); return
    opened=st.session_state.get("workspace_match_id")
    if opened:
        _render_match_hub(user,int(opened)); return
    page_header("Jornada","Partidos, horarios, scouting e informes desde un único lugar.")
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
            mc=data["mission_counts"].get(match.id,0)
            ac=data["assignment_counts"].get(match.id,{})
            if mc: bits.append(f"👁 {mc} objetivo{'s' if mc!=1 else ''}")
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
