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
    page_header(team.name,"Ficha de rival")
    if data.get("next_vs_own"):
        m=data["next_vs_own"]
        st.markdown(f"**Próximo partido vs No Name:** {m.round_name} · {m.home_team.name} - {m.away_team.name}")
        st.caption(m.kickoff_at.strftime("%d/%m/%Y · %H:%M") if m.kickoff_at else f"{m.match_date.strftime('%d/%m/%Y')} · horario pendiente")
    c1,c2,c3=st.columns(3)
    c1.metric("Jugadores conocidos",len(data["roster"]))
    c2.metric("Seguimiento",sum(1 for d in data["decisions"].values() if d.status=="Seguimiento"))
    c3.metric("Prioritarios",sum(1 for d in data["decisions"].values() if d.status=="Prioritario"))
    if data["last_lineup"]:
        st.markdown("### Último XI conocido")
        starters=[p for p in data["last_lineup"] if p.starter]
        st.caption(" · ".join((p.player.display_name or p.player.full_name) for p in starters))
    st.markdown("### Jugadores")
    for roster in data["roster"]:
        p=roster.player;d=data["decisions"].get(p.id)
        with st.container(border=True):
            a,b=st.columns([5,1]);a.markdown(f"**{p.display_name or p.full_name}** · {p.primary_position or '-'}")
            a.caption(d.status if d else "Observado")
            if b.button("Abrir",key=f"teamplayer38_{team.id}_{p.id}",use_container_width=True):
                st.session_state["workspace_player_id"]=p.id;request_navigation("Jugadores");st.rerun()
    if data.get("readings"):
        st.markdown("### Lectura acumulada del equipo")
        st.caption("Histórico 4.2.1 construido con opiniones del staff en neutrales y valoraciones del rival en postpartidos de No Name.")
        for row in reversed(data["readings"][-8:]):
            match = row["match"]
            score = "—" if row["score"] is None else f"{row['score']:.2f}"
            st.markdown(f"**{match.round_name} · {match.home_team.name} - {match.away_team.name}** · {score}")
            st.caption(f"{row['mentions']} opinión(es)")
