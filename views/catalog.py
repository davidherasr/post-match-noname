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


def _section_search(user: dict) -> None:
    st.subheader("Búsqueda global")
    st.caption("Busca jugadores o equipos desde un único sitio. Solo se consulta cuando pulsas Buscar.")
    with st.form("catalog_global_search"):
        query = st.text_input("Buscar", placeholder="Nombre de jugador o equipo")
        submit = st.form_submit_button("Buscar", type="primary", use_container_width=True)
    if not submit or len(query.strip()) < 2:
        st.info("Escribe al menos dos caracteres.")
        return
    with session_scope() as session:
        result = repo.global_catalog_search(session, query.strip())
    if result["players"]:
        st.markdown("#### Jugadores")
        st.dataframe(pd.DataFrame([{
            "ID": p.id, "Jugador": p.full_name, "Nombre visible": p.display_name or "",
            "POS": p.primary_position or "-", "Nacimiento": p.date_of_birth, "Activo": p.active,
        } for p in result["players"]]), hide_index=True, use_container_width=True)
    if result["teams"]:
        st.markdown("#### Equipos")
        st.dataframe(pd.DataFrame([{
            "ID": t.id, "Equipo": t.name, "Nombre corto": t.short_name or "", "Activo": t.active,
        } for t in result["teams"]]), hide_index=True, use_container_width=True)
    if not result["players"] and not result["teams"]:
        st.warning("No se han encontrado coincidencias.")


def _section_seasons(user: dict) -> None:
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


def _section_competitions(user: dict) -> None:
    with session_scope() as session:
        comps = repo.list_competitions(session)
    if comps:
        st.dataframe(pd.DataFrame([{"ID": c.id, "Competición": c.name, "Activa": c.active} for c in comps]), use_container_width=True, hide_index=True)
    with st.form("create_comp"):
        name = st.text_input("Nombre de competición", placeholder="Liga / Copa")
        with st.expander("Datos avanzados", expanded=False):
            country = st.text_input("País (opcional)", help="En No Name normalmente no necesitas rellenarlo.")
        submit = st.form_submit_button("Crear competición", type="primary", use_container_width=True)
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
            new_name = st.text_input("Nombre", value=comp.name)
            active = st.checkbox("Activa", value=comp.active)
            with st.expander("Datos avanzados", expanded=False):
                new_country = st.text_input("País (opcional)", value=comp.country or "")
            save = st.form_submit_button("Guardar cambios", use_container_width=True)
        if save:
            try:
                with session_scope() as session:
                    repo.update_competition(session, selected, user["id"], name=new_name.strip(), country=new_country.strip() or None, active=active)
                st.success("Competición actualizada.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _section_teams(user: dict) -> None:
    with session_scope() as session:
        teams = repo.list_teams(session)
    if teams:
        st.dataframe(pd.DataFrame([{
            "ID": t.id, "Equipo": t.name, "Nombre corto": t.short_name,
            "Nuestro equipo": t.is_own_team, "Activo": t.active, "Escudo": "Sí" if t.logo_b64 else "No"
        } for t in teams]), use_container_width=True, hide_index=True)
    with st.form("create_team"):
        c1, c2 = st.columns([2, 1])
        name = c1.text_input("Nombre completo")
        short = c2.text_input("Nombre corto")
        own = st.checkbox("Marcar como nuestro equipo")
        with st.expander("Datos avanzados", expanded=False):
            country = st.text_input("País (opcional)", help="Se conserva para compatibilidad, pero no es necesario en vuestro flujo de liga.")
        submit = st.form_submit_button("Crear equipo", type="primary", use_container_width=True)
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
            e1, e2 = st.columns([2, 1])
            new_name = e1.text_input("Nombre", value=team.name)
            new_short = e2.text_input("Nombre corto", value=team.short_name or "")
            active = st.checkbox("Activo", value=team.active)
            own = st.checkbox("Nuestro equipo", value=team.is_own_team)
            with st.expander("Datos avanzados", expanded=False):
                new_country = st.text_input("País (opcional)", value=team.country or "")
                logo = st.file_uploader("Escudo (PNG/JPG)", type=["png", "jpg", "jpeg"], key=f"team_logo_{selected}")
                remove_logo = st.checkbox("Eliminar escudo actual", disabled=not bool(team.logo_b64))
            save = st.form_submit_button("Guardar equipo", use_container_width=True)
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
                st.success("Equipo actualizado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _section_players(user: dict) -> None:
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
            "Activo": p.active, "Fusionado": p.merged_into_id,
        } for p in players]), use_container_width=True, hide_index=True)
    with st.form("create_player"):
        p1, p2 = st.columns([2, 1])
        full_name = p1.text_input("Nombre completo")
        display_name = p2.text_input("Nombre visible / camiseta")
        position = st.selectbox("Posición", POSITIONS)
        nationality = ""
        preferred_foot = ""
        has_dob = False
        dob = date(2000, 1, 1)
        with st.expander("Datos avanzados", expanded=False):
            a1, a2 = st.columns(2)
            preferred_foot = a1.selectbox("Pie", ["", "Derecho", "Izquierdo", "Ambidiestro"])
            nationality = a2.text_input("Nacionalidad (opcional)")
            has_dob = st.checkbox("Añadir fecha de nacimiento")
            dob = st.date_input("Fecha de nacimiento", value=date(2000, 1, 1), disabled=not has_dob)
        submit = st.form_submit_button("Crear jugador", type="primary", use_container_width=True)
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
            e1, e2 = st.columns([2, 1])
            new_full = e1.text_input("Nombre completo", value=player.full_name)
            new_display = e2.text_input("Nombre visible", value=player.display_name or "")
            new_position = st.selectbox("Posición", POSITIONS, index=POSITIONS.index(player.primary_position) if player.primary_position in POSITIONS else len(POSITIONS)-1)
            active = st.checkbox("Activo", value=player.active)
            with st.expander("Datos avanzados", expanded=False):
                a1, a2 = st.columns(2)
                new_foot = a1.selectbox("Pie", ["", "Derecho", "Izquierdo", "Ambidiestro"], index=["", "Derecho", "Izquierdo", "Ambidiestro"].index(player.preferred_foot) if player.preferred_foot in {"Derecho", "Izquierdo", "Ambidiestro"} else 0)
                new_nationality = a2.text_input("Nacionalidad", value=player.nationality or "")
                has_new_dob = st.checkbox("Mantener/añadir fecha de nacimiento", value=player.date_of_birth is not None)
                new_dob = st.date_input("Nacimiento", value=player.date_of_birth or date(2000, 1, 1), disabled=not has_new_dob)
                photo = st.file_uploader("Fotografía opcional", type=["png", "jpg", "jpeg"], key=f"player_photo_{selected}")
                remove_photo = st.checkbox("Eliminar fotografía", disabled=not bool(player.photo_b64))
                alias = st.text_input("Nuevo alias (opcional)")
            save = st.form_submit_button("Guardar jugador", use_container_width=True)
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


def _section_rosters(user: dict) -> None:
    with session_scope() as session:
        teams = repo.list_teams(session, active_only=True)
        seasons = repo.list_seasons(session, active_only=True)
        players = repo.list_players(session, limit=1000)
    if not teams or not seasons or not players:
        st.info("Necesitas equipos, temporadas y jugadores.")
        return
    c1, c2 = st.columns(2)
    team_id = c1.selectbox("Equipo", [t.id for t in teams], format_func=lambda tid: next(t.name for t in teams if t.id == tid))
    season_id = c2.selectbox("Temporada", [s.id for s in seasons], format_func=lambda sid: next(s.name for s in seasons if s.id == sid))
    with session_scope() as session:
        roster = repo.get_roster(session, team_id, season_id, active_only=False)

    st.caption("Edita varios dorsales/altas/bajas y guarda toda la plantilla en un único lote.")
    if roster:
        base = pd.DataFrame([{
            "id": r.id, "Jugador": r.player.full_name, "POS": r.player.primary_position or "-",
            "Dorsal": r.shirt_number, "Activo": r.active, "Alta": r.joined_at, "Baja": r.left_at,
        } for r in roster])
        with st.form(f"bulk_roster_{team_id}_{season_id}"):
            edited = st.data_editor(
                base, hide_index=True, use_container_width=True, disabled=["id", "Jugador", "POS"],
                column_config={"id": None, "Dorsal": st.column_config.NumberColumn(min_value=0,max_value=99,step=1), "Activo": st.column_config.CheckboxColumn()},
            )
            save_bulk = st.form_submit_button("Guardar cambios de plantilla", type="primary", use_container_width=True)
        if save_bulk:
            rows = [{
                "id": int(r["id"]),
                "shirt_number": None if pd.isna(r["Dorsal"]) else int(r["Dorsal"]),
                "active": bool(r["Activo"]),
                "joined_at": None if pd.isna(r["Alta"]) else r["Alta"],
                "left_at": None if pd.isna(r["Baja"]) else r["Baja"],
            } for _, r in edited.iterrows()]
            with session_scope() as session:
                count = repo.bulk_update_roster_entries_fast(session, rows, user["id"])
            st.success(f"{count} registros actualizados en un lote.")
            st.rerun()

    with st.expander("Añadir jugador a esta plantilla", expanded=not bool(roster)):
        with st.form(f"assign_roster_{team_id}_{season_id}"):
            player_id = st.selectbox("Jugador", [p.id for p in players], format_func=lambda pid: next(f"{p.full_name} · {p.primary_position or '-'}" for p in players if p.id == pid))
            shirt = st.number_input("Dorsal", min_value=0, max_value=99, value=0)
            joined_at = st.date_input("Fecha de alta", value=date.today())
            submit = st.form_submit_button("Añadir", type="primary", use_container_width=True)
        if submit:
            with session_scope() as session:
                item = repo.assign_player_to_roster(session, team_id, season_id, player_id, shirt or None, user["id"])
                repo.update_roster_entry(session, item.id, user["id"], active=True, joined_at=joined_at, left_at=None)
            st.success("Jugador añadido.")
            st.rerun()


def _section_duplicates(user: dict) -> None:
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


def render(user: dict) -> None:
    page_header("Base de datos · mantenimiento", 'Revisa y corrige datos sin cargar todas las tablas a la vez.')
    section = st.selectbox(
        "Sección",
        ['Buscar', 'Temporadas', 'Competiciones', 'Equipos', 'Jugadores', 'Plantillas', 'Duplicados'],
        key="catalog_section",
        help="Solo se consulta la sección que abras; el resto no ejecuta consultas en segundo plano.",
    )
    if section == 'Buscar':
        _section_search(user)
    elif section == 'Temporadas':
        _section_seasons(user)
    elif section == 'Competiciones':
        _section_competitions(user)
    elif section == 'Equipos':
        _section_teams(user)
    elif section == 'Jugadores':
        _section_players(user)
    elif section == 'Plantillas':
        _section_rosters(user)
    elif section == 'Duplicados':
        _section_duplicates(user)
