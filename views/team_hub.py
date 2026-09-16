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
    st.markdown("### Plantilla conocida")
    search=st.text_input("Buscar en la plantilla",key=f"team_roster_search_444_{team.id}",
                         placeholder="Nombre del jugador…")
    selected=[r for r in data["roster"] if search.casefold() in
              (r.player.display_name or r.player.full_name).casefold()]
    st.caption(f"{len(selected)} futbolistas encontrados · abre la ficha para consultar la evidencia.")
    for roster in selected:
        p=roster.player;d=data["decisions"].get(p.id)
        with st.container(border=True):
            st.markdown(f"**{p.display_name or p.full_name}** · {p.primary_position or 'Posición desconocida'}")
            st.caption(d.status if d else "Sin decisión deportiva")
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
