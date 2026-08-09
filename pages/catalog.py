from __future__ import annotations

import base64
from datetime import date

import pandas as pd
import streamlit as st

from core.constants import POSITIONS
from core.database import session_scope
from models.entities import Player
from repositories import scouting as repo
from ui.styles import page_header


def _safe_date(value, fallback: date) -> date:
    return value if isinstance(value, date) else fallback


def render(user: dict) -> None:
    page_header("Base de datos · mantenimiento", "Zona administrativa para revisar, corregir, archivar o fusionar datos. El trabajo normal se hace desde Nuevo postpartido.")
    tab_seasons, tab_comp, tab_teams, tab_players, tab_rosters, tab_duplicates = st.tabs([
        "Temporadas", "Competiciones", "Equipos", "Jugadores", "Plantillas", "Duplicados"
    ])

    with tab_seasons:
        with session_scope() as session:
            seasons = repo.list_seasons(session)
        if seasons:
            st.dataframe(pd.DataFrame([{"ID": s.id, "Temporada": s.name, "Inicio": s.start_date, "Fin": s.end_date, "Activa": s.active} for s in seasons]), use_container_width=True, hide_index=True)
        with st.form("create_season"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Nombre", placeholder="2026/27")
            start = c2.date_input("Inicio", value=date(date.today().year, 7, 1))
            end = c3.date_input("Fin", value=date(date.today().year + 1, 6, 30))
            submit = st.form_submit_button("Crear temporada", type="primary")
        if submit and name.strip():
            try:
                with session_scope() as session:
                    repo.create_season(session, name.strip(), start, end, user["id"])
                st.success("Temporada creada.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if seasons:
            selected = st.selectbox("Editar temporada", [s.id for s in seasons], format_func=lambda sid: next(s.name for s in seasons if s.id == sid))
            season = next(s for s in seasons if s.id == selected)
            with st.form(f"edit_season_{selected}"):
                e1, e2, e3 = st.columns(3)
                new_name = e1.text_input("Nombre", value=season.name)
                new_start = e2.date_input("Inicio", value=_safe_date(season.start_date, date.today()))
                new_end = e3.date_input("Fin", value=_safe_date(season.end_date, date.today()))
                active = st.checkbox("Activa", value=season.active)
                save = st.form_submit_button("Guardar cambios")
            if save:
                try:
                    with session_scope() as session:
                        repo.update_season(session, selected, user["id"], name=new_name.strip(), start_date=new_start, end_date=new_end, active=active)
                    st.success("Temporada actualizada.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tab_comp:
        with session_scope() as session:
            comps = repo.list_competitions(session)
        if comps:
            st.dataframe(pd.DataFrame([{"ID": c.id, "Competición": c.name, "País": c.country, "Activa": c.active} for c in comps]), use_container_width=True, hide_index=True)
        with st.form("create_comp"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre de competición")
            country = c2.text_input("País")
            submit = st.form_submit_button("Crear competición", type="primary")
        if submit and name.strip():
            try:
                with session_scope() as session:
                    repo.create_competition(session, name.strip(), country.strip() or None, user["id"])
                st.success("Competición creada.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if comps:
            selected = st.selectbox("Editar competición", [c.id for c in comps], format_func=lambda cid: next(c.name for c in comps if c.id == cid))
            comp = next(c for c in comps if c.id == selected)
            with st.form(f"edit_comp_{selected}"):
                e1, e2 = st.columns(2)
                new_name = e1.text_input("Nombre", value=comp.name)
                new_country = e2.text_input("País", value=comp.country or "")
                active = st.checkbox("Activa", value=comp.active)
                save = st.form_submit_button("Guardar cambios")
            if save:
                try:
                    with session_scope() as session:
                        repo.update_competition(session, selected, user["id"], name=new_name.strip(), country=new_country.strip() or None, active=active)
                    st.success("Competición actualizada.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tab_teams:
        with session_scope() as session:
            teams = repo.list_teams(session)
        if teams:
            st.dataframe(pd.DataFrame([{
                "ID": t.id, "Equipo": t.name, "Nombre corto": t.short_name, "País": t.country,
                "Nuestro equipo": t.is_own_team, "Activo": t.active, "Escudo": "Sí" if t.logo_b64 else "No"
            } for t in teams]), use_container_width=True, hide_index=True)
        with st.form("create_team"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Nombre completo")
            short = c2.text_input("Nombre corto")
            country = c3.text_input("País")
            own = st.checkbox("Marcar como nuestro equipo")
            submit = st.form_submit_button("Crear equipo", type="primary")
        if submit and name.strip():
            try:
                with session_scope() as session:
                    repo.create_team(session, name.strip(), short.strip() or None, country.strip() or None, own, user["id"])
                st.success("Equipo creado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if teams:
            selected = st.selectbox("Editar equipo", [t.id for t in teams], format_func=lambda tid: next(t.name for t in teams if t.id == tid))
            team = next(t for t in teams if t.id == selected)
            if team.logo_b64:
                try:
                    st.image(base64.b64decode(team.logo_b64), width=90)
                except Exception:
                    st.caption("El escudo actual no se puede previsualizar.")
            with st.form(f"edit_team_{selected}"):
                e1, e2, e3 = st.columns(3)
                new_name = e1.text_input("Nombre", value=team.name)
                new_short = e2.text_input("Nombre corto", value=team.short_name or "")
                new_country = e3.text_input("País", value=team.country or "")
                active = st.checkbox("Activo", value=team.active)
                own = st.checkbox("Nuestro equipo", value=team.is_own_team)
                logo = st.file_uploader("Escudo (PNG/JPG)", type=["png", "jpg", "jpeg"], key=f"team_logo_{selected}")
                remove_logo = st.checkbox("Eliminar escudo actual", disabled=not bool(team.logo_b64))
                save = st.form_submit_button("Guardar equipo")
            if save:
                values = {"name": new_name.strip(), "short_name": new_short.strip() or None, "country": new_country.strip() or None, "active": active}
                if logo:
                    values.update(logo_b64=base64.b64encode(logo.getvalue()).decode("ascii"), logo_mime=logo.type)
                elif remove_logo:
                    values.update(logo_b64=None, logo_mime=None)
                try:
                    with session_scope() as session:
                        repo.update_team(session, selected, user["id"], **values)
                        if own:
                            repo.set_own_team(session, selected, user["id"])
                            repo.set_setting(session, "own_team_id", str(selected), user["id"])
                    st.success("Equipo actualizado.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tab_players:
        c1, c2, c3 = st.columns([2, 1, 1])
        search = c1.text_input("Buscar jugador")
        pos_filter = c2.selectbox("Posición", ["Todas"] + POSITIONS)
        page = c3.number_input("Página", min_value=1, value=1, step=1)
        page_size = 100
        with session_scope() as session:
            players = repo.list_players(session, search=search or None, position=None if pos_filter == "Todas" else pos_filter, active_only=False, limit=page_size, offset=(int(page)-1)*page_size)
        if players:
            st.dataframe(pd.DataFrame([{
                "ID": p.id, "Jugador": p.full_name, "Nombre visible": p.display_name, "Posición": p.primary_position,
                "Nacimiento": p.date_of_birth, "Nacionalidad": p.nationality, "Pie": p.preferred_foot,
                "Activo": p.active, "Fusionado": p.merged_into_id,
            } for p in players]), use_container_width=True, hide_index=True)
        with st.form("create_player"):
            p1, p2 = st.columns(2)
            full_name = p1.text_input("Nombre completo")
            display_name = p2.text_input("Nombre visible / camiseta")
            p3, p4, p5 = st.columns(3)
            position = p3.selectbox("Posición", POSITIONS)
            nationality = p4.text_input("Nacionalidad")
            preferred_foot = p5.selectbox("Pie", ["", "Derecho", "Izquierdo", "Ambidiestro"])
            has_dob = st.checkbox("Añadir fecha de nacimiento")
            dob = st.date_input("Fecha de nacimiento", value=date(2000, 1, 1), disabled=not has_dob)
            submit = st.form_submit_button("Crear jugador", type="primary")
        if submit and full_name.strip():
            try:
                with session_scope() as session:
                    player = repo.find_or_create_player(session, full_name.strip(), dob if has_dob else None, position, nationality.strip() or None, display_name.strip() or None, actor_id=user["id"])
                    if preferred_foot:
                        repo.update_player(session, player.id, user["id"], preferred_foot=preferred_foot)
                st.success("Jugador creado o localizado en la base de datos.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if players:
            selected = st.selectbox("Editar jugador", [p.id for p in players], format_func=lambda pid: next(p.full_name for p in players if p.id == pid))
            player = next(p for p in players if p.id == selected)
            if player.photo_b64:
                try:
                    st.image(base64.b64decode(player.photo_b64), width=100)
                except Exception:
                    pass
            with st.form(f"edit_player_{selected}"):
                e1, e2 = st.columns(2)
                new_full = e1.text_input("Nombre completo", value=player.full_name)
                new_display = e2.text_input("Nombre visible", value=player.display_name or "")
                e3, e4, e5 = st.columns(3)
                new_position = e3.selectbox("Posición", POSITIONS, index=POSITIONS.index(player.primary_position) if player.primary_position in POSITIONS else len(POSITIONS)-1)
                new_nationality = e4.text_input("Nacionalidad", value=player.nationality or "")
                new_foot = e5.selectbox("Pie", ["", "Derecho", "Izquierdo", "Ambidiestro"], index=["", "Derecho", "Izquierdo", "Ambidiestro"].index(player.preferred_foot) if player.preferred_foot in {"Derecho", "Izquierdo", "Ambidiestro"} else 0)
                has_new_dob = st.checkbox("Mantener/añadir fecha de nacimiento", value=player.date_of_birth is not None)
                new_dob = st.date_input("Nacimiento", value=player.date_of_birth or date(2000, 1, 1), disabled=not has_new_dob)
                active = st.checkbox("Activo", value=player.active)
                photo = st.file_uploader("Fotografía opcional", type=["png", "jpg", "jpeg"], key=f"player_photo_{selected}")
                remove_photo = st.checkbox("Eliminar fotografía", disabled=not bool(player.photo_b64))
                alias = st.text_input("Nuevo alias (opcional)")
                save = st.form_submit_button("Guardar jugador")
            if save:
                values = {
                    "full_name": new_full.strip(), "display_name": new_display.strip() or None,
                    "primary_position": new_position, "nationality": new_nationality.strip() or None,
                    "preferred_foot": new_foot or None, "date_of_birth": new_dob if has_new_dob else None,
                    "active": active,
                }
                if photo:
                    values.update(photo_b64=base64.b64encode(photo.getvalue()).decode("ascii"), photo_mime=photo.type)
                elif remove_photo:
                    values.update(photo_b64=None, photo_mime=None)
                try:
                    with session_scope() as session:
                        repo.update_player(session, selected, user["id"], **values)
                        if alias.strip():
                            repo.add_player_alias(session, selected, alias.strip(), user["id"])
                    st.success("Jugador actualizado.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tab_rosters:
        with session_scope() as session:
            teams = repo.list_teams(session, active_only=True)
            seasons = repo.list_seasons(session, active_only=True)
            players = repo.list_players(session, limit=1000)
        if not teams or not seasons or not players:
            st.info("Necesitas equipos, temporadas y jugadores.")
        else:
            c1, c2 = st.columns(2)
            team_id = c1.selectbox("Equipo", [t.id for t in teams], format_func=lambda tid: next(t.name for t in teams if t.id == tid))
            season_id = c2.selectbox("Temporada", [s.id for s in seasons], format_func=lambda sid: next(s.name for s in seasons if s.id == sid))
            with session_scope() as session:
                roster = repo.get_roster(session, team_id, season_id, active_only=False)
            if roster:
                st.dataframe(pd.DataFrame([{
                    "ID": r.id, "Dorsal": r.shirt_number, "Jugador": r.player.full_name, "Posición": r.player.primary_position,
                    "Activo": r.active, "Alta": r.joined_at, "Baja": r.left_at,
                } for r in roster]), use_container_width=True, hide_index=True)
            with st.form("assign_roster"):
                player_id = st.selectbox("Jugador", [p.id for p in players], format_func=lambda pid: next(f"{p.full_name} · {p.primary_position or '-'}" for p in players if p.id == pid))
                shirt = st.number_input("Dorsal", min_value=0, max_value=99, value=0)
                joined_at = st.date_input("Fecha de alta", value=date.today())
                submit = st.form_submit_button("Añadir o actualizar en plantilla", type="primary")
            if submit:
                try:
                    with session_scope() as session:
                        item = repo.assign_player_to_roster(session, team_id, season_id, player_id, shirt or None, user["id"])
                        repo.update_roster_entry(session, item.id, user["id"], active=True, joined_at=joined_at, left_at=None)
                    st.success("Plantilla actualizada.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if roster:
                selected_roster = st.selectbox("Editar alta/baja", [r.id for r in roster], format_func=lambda rid: next(r.player.full_name for r in roster if r.id == rid))
                item = next(r for r in roster if r.id == selected_roster)
                with st.form(f"edit_roster_{selected_roster}"):
                    r1, r2 = st.columns(2)
                    new_shirt = r1.number_input("Dorsal", min_value=0, max_value=99, value=int(item.shirt_number or 0))
                    active = r2.checkbox("Activo en plantilla", value=item.active)
                    joined = st.date_input("Fecha de alta", value=item.joined_at or date.today())
                    has_left = st.checkbox("Registrar fecha de baja", value=item.left_at is not None)
                    left = st.date_input("Fecha de baja", value=item.left_at or date.today(), disabled=not has_left)
                    save = st.form_submit_button("Guardar estado")
                if save:
                    try:
                        with session_scope() as session:
                            repo.update_roster_entry(session, selected_roster, user["id"], shirt_number=new_shirt or None, active=active, joined_at=joined, left_at=left if has_left else None)
                        st.success("Situación de plantilla actualizada.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    with tab_duplicates:
        with session_scope() as session:
            groups = repo.duplicate_player_groups(session)
        if not groups:
            st.success("No se han detectado grupos evidentes de posibles duplicados.")
        else:
            st.warning("La fusión mueve participaciones, evaluaciones, plantillas, alias y seguimientos al registro maestro. Revisa antes de confirmar.")
            flat = []
            for group in groups:
                for candidate in group["players"]:
                    flat.append({"Nombre normalizado": group["normalized_name"], "ID": candidate.id, "Jugador": candidate.full_name, "Nacimiento": candidate.date_of_birth, "Posición": candidate.primary_position})
            st.dataframe(pd.DataFrame(flat), use_container_width=True, hide_index=True)
            ids = sorted({row["ID"] for row in flat})
            with session_scope() as session:
                candidates = [session.get(Player, pid) for pid in ids]
                candidates = [p for p in candidates if p]
            if len(candidates) >= 2:
                c1, c2 = st.columns(2)
                source_id = c1.selectbox("Duplicado que se absorberá", [p.id for p in candidates], format_func=lambda pid: next(f"{p.full_name} · ID {p.id}" for p in candidates if p.id == pid))
                target_options = [p.id for p in candidates if p.id != source_id]
                target_id = c2.selectbox("Registro maestro que se conservará", target_options, format_func=lambda pid: next(f"{p.full_name} · ID {p.id}" for p in candidates if p.id == pid))
                confirmation = st.text_input("Escribe FUSIONAR para confirmar")
                if st.button("Fusionar jugadores", type="primary", disabled=confirmation != "FUSIONAR"):
                    try:
                        with session_scope() as session:
                            repo.merge_players(session, source_id, target_id, user["id"])
                        st.success("Jugadores fusionados y trazabilidad registrada.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
