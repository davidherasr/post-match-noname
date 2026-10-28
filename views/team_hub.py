from __future__ import annotations

import streamlit as st

from core.navigation import request_navigation

from core.database import session_scope
from repositories import players as players_repo
from repositories import workspaces
from ui.styles import page_header


def render(user:dict,team_id:int)->None:
    if st.button("← Volver al partido",key=f"back_team38_{team_id}"):
        st.session_state.pop("workspace_team_id",None);st.rerun()
    with session_scope() as session:
        active=players_repo.get_active_season(session)
        data=workspaces.load_team_workspace(session,team_id=team_id,season_id=active.id if active else None)
    team=data["team"]
    own_team = bool(team.is_own_team)
    page_header(team.name, "Plantilla y rendimiento del equipo propio" if own_team else "Plantilla e información del equipo")
    if data.get("next_vs_own"):
        m=data["next_vs_own"]
        st.markdown(f"**Próximo partido vs No Name:** {m.round_name} · {m.home_team.name} - {m.away_team.name}")
        st.caption(m.kickoff_at.strftime("%d/%m/%Y · %H:%M") if m.kickoff_at else f"{m.match_date.strftime('%d/%m/%Y')} · horario pendiente")
    st.caption(f"{len(data['roster'])} jugadores conocidos · "
               f"{sum(1 for d in data['decisions'].values() if d.status=='Seguimiento')} en seguimiento · "
               f"{sum(1 for d in data['decisions'].values() if d.status=='Prioritario')} prioritarios")
    if data["last_lineup"]:
        with st.expander("Último XI documentado"):
            starters=[p for p in data["last_lineup"] if p.starter]
            if starters:
                for part in starters:
                    st.write(f"{('#' + str(part.shirt_number)) if part.shirt_number is not None else '—'} · "
                             f"{part.player.display_name or part.player.full_name}")
            else:
                st.caption("No se han registrado titulares para ese encuentro.")
    knowledge = None
    if active:
        try:
            from repositories.dd_attention import team_knowledge
            with session_scope() as session:
                knowledge = team_knowledge(session, active.id, team.id)
        except (ImportError, AttributeError) as exc:
            # A partial Cloud deployment must not block the squad and fixture
            # views. The release-smoke check catches this before deployment.
            st.warning("La lectura agregada de DD no está disponible en este despliegue. Verifica que todos los archivos de la release se hayan actualizado juntos.")
    if knowledge:
        st.markdown("### Conocimiento sobre el equipo")
        st.caption(f"{len(knowledge['matches'])} encuentros oficiales en calendario · última referencia: {knowledge['last_observed'] or '—'}")
        if knowledge["formations"]:
            st.markdown("**Estructuras realmente observadas**")
            for shape, count, last in knowledge["formations"][:6]:
                st.caption(f"{shape} · {count} partido(s) · última vez {last:%d/%m/%Y}")
        else:
            st.caption("No hay formaciones confirmadas en el histórico; no se infiere un sistema fijo.")
        verified = next((m for m in knowledge["matches"] if (
            (m.home_team_id == team.id and m.home_formation_known and m.home_formation) or
            (m.away_team_id == team.id and m.away_formation_known and m.away_formation))), None)
        if verified:
            from core.formations import slots_for
            from ui.match_study import render_campogram
            from repositories import unidentified_players as unknown_repo
            from models.entities import Participation
            from sqlalchemy import select
            form = verified.home_formation if verified.home_team_id == team.id else verified.away_formation
            with session_scope() as session:
                parts = list(session.scalars(select(Participation).where(
                    Participation.match_id == verified.id, Participation.team_id == team.id)).all())
                unknowns = unknown_repo.unresolved(session, match_id=verified.id, team_id=team.id)
                slots = slots_for(form)
                pitch_rows = []
                used = set()
                for slot in slots:
                    part = next((p for p in parts if p.id not in used and p.position == slot.code), None)
                    if part:
                        used.add(part.id)
                        pitch_rows.append({"name": part.player.display_name or part.player.full_name,
                                           "shirt_number": part.shirt_number})
                    else:
                        candidate = next((e for e in unknowns if e.position == slot.code), None)
                        pitch_rows.append({"name": "Identidad pendiente" if candidate else None,
                                           "shirt_number": candidate.shirt_number if candidate else None})
            with st.expander(f"Campograma observado · {verified.match_date:%d/%m/%Y} · {form}"):
                render_campogram(form, pitch_rows, title="Posiciones documentadas; hueco vacío = desconocido")
                st.caption("El dibujo recoge la última estructura verificada y no presupone titulares desconocidos.")
        if knowledge["signals"]:
            st.markdown("**Jugadores señalados y posiciones pendientes de identificar**")
            for signal in knowledge["signals"][:12]:
                label = signal["name"]
                st.write(f"{label} · {signal['matches']} partido(s), {signal['authors']} autor(es) · {signal['coverage']}")
                st.caption("; ".join(signal["reasons"]))
    st.markdown("### Plantilla conocida")
    search=st.text_input("Buscar en la plantilla",key=f"team_roster_search_444_{team.id}",
                         placeholder="Nombre del jugador…")
    selected=[r for r in data["roster"] if search.casefold() in
              (r.player.display_name or r.player.full_name).casefold()]
    st.caption(f"{len(selected)} futbolistas encontrados · abre la ficha para consultar la evidencia.")
    for roster in selected:
        p=roster.player;d=data["decisions"].get(p.id)
        with st.container(border=True):
            st.markdown(f"**{p.display_name or p.full_name}** · {roster.usual_position or p.primary_position or 'Posición desconocida'}")
            st.caption(d.status if d else "Sin decisión deportiva")
            from core.permissions import can_admin, can_direct, can_report
            if can_admin(user) or can_direct(user) or can_report(user):
                with st.expander("Posición habitual en esta plantilla"):
                    from core.constants import POSITIONS
                    from repositories import unidentified_players
                    current_pos = roster.usual_position
                    options = [None] + [pos for pos in POSITIONS if pos != None]
                    if current_pos not in options:
                        options.append(current_pos)
                    pos = st.selectbox("Posición (equipo/temporada)", options,
                        index=options.index(current_pos) if current_pos in options else 0,
                        format_func=lambda v: v or "Desconocida",
                        key=f"team_position_45_{team.id}_{p.id}")
                    if st.button("Guardar posición habitual", key=f"team_savepos_45_{team.id}_{p.id}"):
                        try:
                            with session_scope() as session:
                                unidentified_players.set_usual_position(session,
                                    actor_id=user["id"], team_id=team.id, season_id=active.id,
                                    player_id=p.id, position=pos)
                            st.success("Posición contextual guardada; no cambia la del partido ni la global.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
            if st.button("Abrir ficha del jugador",key=f"teamplayer38_{team.id}_{p.id}",use_container_width=True):
                st.session_state["workspace_player_id"]=p.id;request_navigation("Jugadores");st.rerun()
    if data.get("readings"):
        st.markdown("### Lectura acumulada del equipo")
        st.caption('Histórico de valoraciones del staff en partidos propios y neutrales.')
        for row in reversed(data["readings"][-8:]):
            match = row["match"]
            score = "—" if row["score"] is None else f"{row['score']:.2f}"
            st.markdown(f"**{match.round_name} · {match.home_team.name} - {match.away_team.name}** · {score}")
            st.caption(f"{row['mentions']} opinión(es)")
