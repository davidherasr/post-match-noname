from __future__ import annotations

import pandas as pd
import streamlit as st

from core.navigation import request_navigation

from core.constants import POSITIONS
from core.database import session_scope
from core.permissions import can_direct, can_track_players
from core.presentation import NEED_STATES, normalize_need_state
from repositories import planning as planning_repo
from repositories import players as players_repo
from repositories import sporting_reading as sporting_repo
from ui.styles import page_header


def _open_player(pid: int) -> None:
    st.session_state["workspace_player_id"]=int(pid)
    request_navigation("Jugadores")
    st.rerun()




def _open_match(match_id: int) -> None:
    st.session_state["workspace_match_id"] = int(match_id)
    request_navigation("Jornada")
    st.rerun()


def _trend_text(value: float | None) -> str:
    return sporting_repo.trend_label(value)


def _start_tracking_from_dd(player_id: int, user: dict, *, key: str) -> None:
    if not can_track_players(user):
        return
    if st.button("Iniciar seguimiento", use_container_width=True, key=key):
        try:
            with session_scope() as session:
                sporting_repo.start_player_tracking(session, player_id=player_id, actor_id=user["id"])
            st.session_state["workspace_player_id"] = int(player_id)
            request_navigation("Jugadores")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _recent_matches_block(data: dict) -> None:
    own_rows = data.get("own") or []
    neutral_rows = data.get("neutral") or []
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("#### No Name · postpartidos")
        if not own_rows:
            st.info("Todavía no hay partidos de No Name con información para leer.")
        for item in own_rows:
            match = item["match"]
            reading = item["reading"]
            with st.container(border=True):
                a, b = st.columns([4, 1])
                a.markdown(f"**{match.round_name} · {match.home_team.name} - {match.away_team.name}**")
                own_rating = "—" if reading["own_weighted"] is None else f"{reading['own_weighted']:.2f}"
                rival_rating = "—" if reading["rival_weighted"] is None else f"{reading['rival_weighted']:.2f}"
                own_consensus = sporting_repo.consensus_label(reading.get("own_dispersion"), len(reading["reports"]))
                a.caption(f"{len(reading['reports'])} postpartidos · No Name {own_rating} · Rival {rival_rating} · {own_consensus}")
                if b.button("Abrir", key=f"dd_own_match_421_{match.id}", use_container_width=True):
                    _open_match(match.id)
    with c2:
        st.markdown("#### Liga · partidos neutrales")
        if not neutral_rows:
            st.info("Todavía no hay lecturas del staff en partidos neutrales.")
        for item in neutral_rows:
            match = item["match"]
            reading = item["reading"]
            with st.container(border=True):
                a, b = st.columns([4, 1])
                a.markdown(f"**{match.round_name} · {match.home_team.name} - {match.away_team.name}**")
                home = "—" if reading["home_weighted"] is None else f"{reading['home_weighted']:.2f}"
                away = "—" if reading["away_weighted"] is None else f"{reading['away_weighted']:.2f}"
                consensus = sporting_repo.consensus_label(
                    max(x for x in [reading.get("home_dispersion"), reading.get("away_dispersion")] if x is not None)
                    if any(x is not None for x in [reading.get("home_dispersion"), reading.get("away_dispersion")]) else None,
                    len(reading["opinions"]),
                )
                a.caption(f"{len(reading['opinions'])} lecturas · {match.home_team.short_name or match.home_team.name} {home} · {match.away_team.short_name or match.away_team.name} {away} · {len(reading['players'])} señales · {consensus}")
                if b.button("Abrir", key=f"dd_neutral_match_421_{match.id}", use_container_width=True):
                    _open_match(match.id)


def _players_intelligence(user: dict, players: list[dict], *, compact: bool = False) -> None:
    if not players:
        st.info("Todavía no hay jugadores externos señalados por el staff.")
        return
    rows = players[:6] if compact else players[:30]
    for row in rows:
        player = row["player"]
        tracked = row.get("tracking") is not None
        with st.container(border=True):
            a, b, c = st.columns([5, 1, 1])
            a.markdown(f"**{player.display_name or player.full_name}** · {row['team'].name}")
            rating = "—" if row["weighted_rating"] is None else f"{row['weighted_rating']:.2f}"
            a.caption(
                f"{row['match_count']} partido(s) · {row['mentions']} señales · {row['staff_count']} persona(s) · "
                f"nota {rating} · {_trend_text(row['trend'])} · {row['consensus']}"
            )
            if row.get("staff"):
                a.caption("Señalado por: " + ", ".join(row["staff"][:5]))
            if row.get("notes") and not compact:
                a.write(" · ".join(row["notes"][:3]))
            if b.button("Abrir ficha", use_container_width=True, key=f"dd_intel_open_421_{player.id}_{'c' if compact else 'f'}"):
                _open_player(player.id)
            if tracked:
                c.caption("En seguimiento")
            elif can_track_players(user):
                with c:
                    _start_tracking_from_dd(player.id, user, key=f"dd_intel_track_421_{player.id}_{'c' if compact else 'f'}")


def _teams_intelligence(teams: list[dict], *, compact: bool = False) -> None:
    if not teams:
        st.info("Todavía no hay suficiente lectura acumulada de equipos rivales.")
        return
    rows = teams[:6] if compact else teams[:30]
    frame = pd.DataFrame([{
        "Equipo": row["team"].name,
        "Partidos": row["match_count"],
        "Opiniones": row["opinions"],
        "Personas": row["staff_count"],
        "Nota ponderada": None if row["weighted_rating"] is None else round(row["weighted_rating"], 2),
        "Evolución": _trend_text(row["trend"]),
        "Consenso": row["consensus"],
    } for row in rows])
    st.dataframe(frame, hide_index=True, use_container_width=True)


def _disagreements_block(disagreements: list[dict], *, compact: bool = False) -> None:
    rows = disagreements[:5] if compact else disagreements[:20]
    if not rows:
        st.info("Todavía no hay opiniones comparables suficientes para detectar discrepancias.")
        return
    for row in rows:
        match = row["match"]
        with st.container(border=True):
            a, b = st.columns([5, 1])
            a.markdown(f"**{row['consensus']} · {row['kind']}: {row['entity_name']}**")
            a.caption(
                f"{match.round_name} · {match.home_team.name} - {match.away_team.name} · "
                f"{row['count']} opiniones · rango {row['low'][0]} {row['low'][1]:.1f} ↔ {row['high'][0]} {row['high'][1]:.1f}"
            )
            if b.button("Abrir", use_container_width=True, key=f"dd_disagreement_421_{row['kind']}_{row['entity_id']}_{match.id}_{'c' if compact else 'f'}"):
                _open_match(match.id)


def _sporting_overview(user: dict, season) -> None:
    st.markdown("### Lectura deportiva")
    st.caption(
        "Dirección Deportiva no reparte tareas de observación: cruza el criterio del staff, detecta patrones entre jornadas "
        "y separa siempre el rendimiento de No Name de las señales sobre el entorno competitivo."
    )
    with session_scope() as session:
        recent = sporting_repo.recent_sporting_matches(session, season.id, limit=8)
        intel = sporting_repo.league_intelligence(session, season.id)

    players = intel.get("players") or []
    teams = intel.get("teams") or []
    disagreements = intel.get("disagreements") or []
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jugadores señalados", len(players))
    c2.metric("Se repiten en 2+ partidos", intel.get("repeated_players", 0))
    c3.metric("Equipos con lectura", len(teams))
    c4.metric("Discrepancias altas", intel.get("high_disagreements", 0))

    area = st.segmented_control(
        "Lectura", ["Panorama", "Jugadores señalados", "Equipos", "Discrepancias", "Partidos recientes"],
        default="Panorama", key="dd_reading_area_421",
    ) or "Panorama"

    if area == "Jugadores señalados":
        st.markdown("#### Señales acumuladas de jugadores externos")
        st.caption("Una señal no es un seguimiento. Se priorizan los jugadores que se repiten en varios partidos y varias opiniones.")
        _players_intelligence(user, players, compact=False)
        return
    if area == "Equipos":
        st.markdown("#### Lectura acumulada de equipos")
        st.caption("Combina partidos neutrales y la valoración de rivales en nuestros postpartidos. No incluye a No Name.")
        _teams_intelligence(teams, compact=False)
        return
    if area == "Discrepancias":
        st.markdown("#### Dónde no estamos viendo lo mismo")
        st.caption("Las discrepancias no son un error: señalan partidos, equipos o jugadores que merece la pena volver a discutir o revisar.")
        _disagreements_block(disagreements, compact=False)
        return
    if area == "Partidos recientes":
        _recent_matches_block(recent)
        return

    st.markdown("#### Señales que empiezan a repetirse")
    _players_intelligence(user, [row for row in players if row["match_count"] >= 2] or players, compact=True)
    st.markdown("#### Equipos con más evidencia acumulada")
    _teams_intelligence(teams, compact=True)
    st.markdown("#### Principales discrepancias")
    _disagreements_block(disagreements, compact=True)
    # The reading itself provides actions and provenance; no internal workflow notes.

def _staff_criterion(user: dict) -> None:
    with st.expander("Criterio del staff · pesos de opinión", expanded=False):
        st.caption("Dirección Deportiva decide cuánto pesa cada opinión según el contexto. No afecta a permisos ni a quién puede entrar en la app.")
        with session_scope() as session:
            staff = sporting_repo.list_sporting_staff(session)
            weights = sporting_repo.weight_map(session)
        if not staff:
            st.info("No hay usuarios Informador / Dirección Deportiva activos.")
            return
        options = list(sporting_repo.WEIGHT_LEVELS)
        for member in staff:
            current = weights.get(member.id)
            own_value = float(current.own_match_weight if current else 1.0)
            neutral_value = float(current.neutral_match_weight if current else 1.0)
            with st.container(border=True):
                st.markdown(f"**{member.full_name}**")
                c1, c2, c3 = st.columns([2,2,1])
                own = c1.selectbox(
                    "Partidos No Name", options,
                    index=min(range(len(options)), key=lambda i: abs(options[i]-own_value)),
                    format_func=lambda v: f"{sporting_repo.WEIGHT_LEVELS[v]} · x{v:.2f}",
                    key=f"staff_own_weight_42_{member.id}",
                )
                neutral = c2.selectbox(
                    "Partidos neutrales", options,
                    index=min(range(len(options)), key=lambda i: abs(options[i]-neutral_value)),
                    format_func=lambda v: f"{sporting_repo.WEIGHT_LEVELS[v]} · x{v:.2f}",
                    key=f"staff_neutral_weight_42_{member.id}",
                )
                if c3.button("Guardar", use_container_width=True, key=f"save_staff_weight_42_{member.id}"):
                    try:
                        with session_scope() as session:
                            sporting_repo.upsert_staff_weight(
                                session, actor_id=user["id"], user_id=member.id,
                                own_match_weight=own, neutral_match_weight=neutral,
                            )
                        st.success("Peso actualizado.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

def _configure_model(user: dict) -> None:
    with st.expander("Configurar Modelo No Name",expanded=False):
        with st.form("new_role_38"):
            c1,c2=st.columns(2)
            name=c1.text_input("Nombre del rol",placeholder="Base / Profundidad / Dominador...")
            pos=c2.selectbox("Posición",POSITIONS)
            description=st.text_area("Descripción",height=70)
            create=st.form_submit_button("Crear rol",type="primary",use_container_width=True)
        if create and name.strip():
            try:
                with session_scope() as session:
                    planning_repo.create_model_role(session,user["id"],name=name,position=pos,description=description)
                st.success("Rol creado."); st.rerun()
            except Exception as exc: st.error(str(exc))
        with session_scope() as session:
            roles=planning_repo.list_model_roles(session)
        if roles:
            role_id=st.selectbox("Añadir criterio a",[r.id for r in roles],format_func=lambda rid:next(f"{r.position} · {r.name}" for r in roles if r.id==rid),key="criterion_role38")
            with st.form(f"criterion_new38_{role_id}"):
                c1,c2,c3=st.columns([3,2,1])
                cname=c1.text_input("Criterio",placeholder="Ataque de profundidad")
                category=c2.selectbox("Bloque",["Técnico","Táctico","Físico","Mental","Mixto"])
                weight=c3.number_input("Peso",1,5,3)
                detail=st.text_input("Qué observar",placeholder="Descripción operativa")
                add=st.form_submit_button("Añadir criterio",use_container_width=True)
            if add and cname.strip():
                with session_scope() as session:
                    planning_repo.add_model_criterion(session,user["id"],role_id,name=cname,category=category,weight=weight,description=detail)
                st.success("Criterio añadido."); st.rerun()


def _map_own_players(user: dict, season, role) -> None:
    with session_scope() as session:
        own=players_repo.get_own_team(session)
        roster=players_repo.get_roster(session,own.id,season.id) if own else []
        decisions=planning_repo.list_season_decisions(session,season.id)
    mapped={d.player_id for d in decisions if d.model_role_id==role.id}
    options=[r.player_id for r in roster if r.player_id not in mapped]
    if not options: return
    player_map={r.player_id:r.player for r in roster}
    with st.expander("Mapear nuestra plantilla al rol",expanded=False):
        selected=st.multiselect("Jugadores",options,format_func=lambda pid:player_map[pid].display_name or player_map[pid].full_name,key=f"map_own38_{role.id}")
        if st.button("Asignar al rol",use_container_width=True,key=f"map_own_save38_{role.id}") and selected:
            with session_scope() as session:
                for pid in selected:
                    planning_repo.upsert_season_decision(session,user["id"],season_id=season.id,player_id=pid,status="Observado",priority=3,model_role_id=role.id)
            st.success("Plantilla mapeada."); st.rerun()


def _role_detail(user: dict, season, role_id: int) -> None:
    if st.button("← Volver al tablero",key="back_role38"):
        st.session_state.pop("workspace_role_id",None); st.rerun()
    with session_scope() as session:
        roles=planning_repo.list_model_roles(session)
        role=next((r for r in roles if r.id==role_id),None)
        if not role:
            st.warning("Rol no encontrado."); return
        criteria=planning_repo.list_model_criteria(session,role.id)
        shadow=next((b for b in planning_repo.shadow_squad(session,season.id) if b["role"].id==role.id),None)
        candidates=shadow["candidates"] if shadow else []
        own_players=shadow["own_players"] if shadow else []
        evidence=planning_repo.scouting_evidence_many(session,[d.player_id for d in candidates],season_id=season.id)
        opportunities=planning_repo.scouting_opportunities(session,season_id=season.id,days_ahead=120,limit=50)
    page_header(f"{role.position} · {role.name}",role.description or "Rol del Modelo No Name")
    if criteria:
        st.markdown("### Criterios")
        for c in criteria:
            st.markdown(f"- **{c.name}** · {c.category} · peso {c.weight}" + (f" — {c.description}" if c.description else ""))
    else: st.caption("Este rol todavía no tiene criterios configurados.")
    st.markdown("### Nuestra plantilla")
    if own_players:
        for d in own_players:
            with st.container(border=True):
                a,b=st.columns([5,1]); a.markdown(f"**{d.player.display_name or d.player.full_name}** · encaje {'—' if d.fit_score is None else f'{d.fit_score:.1f}'}")
                if b.button("Abrir",key=f"role_own38_{d.player_id}",use_container_width=True): _open_player(d.player_id)
    else: st.caption("Sin referencias internas mapeadas.")
    _map_own_players(user,season,role)
    st.markdown("### Candidatos")
    if candidates:
        for d in candidates:
            ev=evidence.get(d.player_id,{})
            with st.container(border=True):
                a,b=st.columns([5,1]); a.markdown(f"**{d.player.display_name or d.player.full_name}** · {d.status}")
                a.caption(f"Encaje {'—' if d.fit_score is None else f'{d.fit_score:.1f}'} · 👁 {ev.get('specific_observations',0)} observaciones de seguimiento")
                if b.button("Abrir",key=f"role_candidate38_{d.player_id}",use_container_width=True): _open_player(d.player_id)
    else: st.caption("Sin candidatos asignados a este rol.")
    relevant=[o for o in opportunities if o.get("role") and o["role"].id==role.id]
    if relevant:
        st.markdown("### Próximas oportunidades")
        for item in relevant[:8]:
            match=item["match"]; player=item["decision"].player
            st.caption(f"{player.display_name or player.full_name} · {match.round_name} · {match.home_team.name} - {match.away_team.name} · {match.match_date.strftime('%d/%m/%Y')}")


def render(user: dict) -> None:
    if not can_direct(user):
        st.error("No tienes permiso de Dirección Deportiva."); return
    with session_scope() as session:
        season=players_repo.get_active_season(session)
    if not season:
        st.warning("No hay temporada activa."); return
    opened=st.session_state.get("workspace_role_id")
    if opened:
        _role_detail(user,season,int(opened)); return
    page_header("Dirección Deportiva","Criterio conjunto, rendimiento de No Name, lectura de la liga y decisiones de plantilla.")
    section = st.segmented_control(
        "Área", ["Lectura deportiva", "Plantilla y modelo", "Criterio del staff"],
        default="Lectura deportiva", key="dd_area_42",
    ) or "Lectura deportiva"
    if section == "Lectura deportiva":
        _sporting_overview(user, season)
        return
    if section == "Criterio del staff":
        _staff_criterion(user)
        return

    _configure_model(user)
    with session_scope() as session:
        blocks=planning_repo.shadow_squad(session,season.id)
        all_candidate_ids=[d.player_id for block in blocks for d in block["candidates"]]
        evidence=planning_repo.scouting_evidence_many(session,all_candidate_ids,season_id=season.id)
    if not blocks:
        st.info("Configura el primer rol del Modelo No Name para empezar."); return
    for block in blocks:
        role=block["role"]; need=block.get("need"); need_value=normalize_need_state(need.need_level if need else "Media")
        with st.container(border=True):
            h1,h2,h3=st.columns([4,1,1])
            h1.markdown(f"### {role.position} · {role.name}")
            h2.metric("Necesidad",need_value)
            if h3.button("Abrir rol",use_container_width=True,key=f"open_role38_{role.id}"):
                st.session_state["workspace_role_id"]=role.id; st.rerun()
            own_names=[d.player.display_name or d.player.full_name for d in block["own_players"][:4]]
            st.markdown("**No Name:** "+(", ".join(own_names) if own_names else "sin referencia mapeada"))
            if block["candidates"]:
                candidate_text=[]
                for d in block["candidates"][:5]:
                    ev=evidence.get(d.player_id,{})
                    candidate_text.append(f"{d.player.display_name or d.player.full_name} ({'—' if d.fit_score is None else f'{d.fit_score:.1f}'} · 👁 {ev.get('specific_observations',0)})")
                st.caption("Candidatos: "+" · ".join(candidate_text))
            else: st.caption("Candidatos: —")
            with st.expander("Actualizar necesidad"):
                with st.form(f"need38_{role.id}"):
                    level=st.selectbox("Estado",NEED_STATES,index=NEED_STATES.index(need_value),key=f"needlevel38_{role.id}")
                    note=st.text_input("Nota",value=need.note if need else "",key=f"neednote38_{role.id}")
                    save=st.form_submit_button("Guardar",use_container_width=True)
                if save:
                    with session_scope() as session:
                        planning_repo.upsert_squad_need(session,user["id"],season_id=season.id,model_role_id=role.id,need_level=level,note=note)
                    st.success("Necesidad actualizada."); st.rerun()
