from __future__ import annotations

from datetime import date, datetime, time

import pandas as pd
import streamlit as st

from core.constants import ASSIGNMENT_STATUSES, FORMATIONS, MATCH_STATUSES, POSITIONS, ROLES
from core.database import session_scope
from repositories import scouting as repo
from services.import_service import (
    available_sheets,
    import_lineup,
    import_rosters,
    preview_import,
    read_table,
    template_workbook,
)
from ui.helpers import match_label
from ui.styles import page_header


def _formation_input(label: str, key: str, current: str | None = None) -> str:
    base = current if current in FORMATIONS else ("Personalizada" if current else "4-2-3-1")
    selected = st.selectbox(label, FORMATIONS, index=FORMATIONS.index(base), key=f"formation_select_{key}")
    if selected == "Personalizada":
        return st.text_input("Escribe la formación", value=current or "", key=f"formation_custom_{key}").strip()
    return selected


def _lineup_editor(match_id: int, team_id: int, season_id: int, actor_id: int, key: str) -> None:
    with session_scope() as session:
        roster = repo.get_roster(session, team_id, season_id)
        existing = repo.get_participations(session, match_id, team_id)
    if not roster:
        st.warning("Este equipo no tiene plantilla activa para la temporada del partido.")
        return
    existing_map = {p.player_id: p for p in existing}
    rows = []
    for item in roster:
        part = existing_map.get(item.player_id)
        rows.append({
            "selected": bool(part),
            "player_id": item.player_id,
            "Jugador": item.player.display_name or item.player.full_name,
            "Dorsal": part.shirt_number if part else item.shirt_number,
            "Titular": bool(part.starter) if part else False,
            "Posición": part.position if part else (item.player.primary_position or "Otro"),
            "Entrada": part.minute_in if part else 0,
            "Salida": part.minute_out if part else 90,
            "Capitán": bool(part.captain) if part else False,
        })
    edited = st.data_editor(
        pd.DataFrame(rows), use_container_width=True, hide_index=True, key=f"lineup_editor_{key}",
        column_config={
            "selected": st.column_config.CheckboxColumn("Incluir"),
            "player_id": None,
            "Jugador": st.column_config.TextColumn(),
            "Dorsal": st.column_config.NumberColumn(min_value=0, max_value=99, step=1),
            "Titular": st.column_config.CheckboxColumn(),
            "Posición": st.column_config.SelectboxColumn(options=POSITIONS),
            "Entrada": st.column_config.NumberColumn(min_value=0, max_value=130, step=1),
            "Salida": st.column_config.NumberColumn(min_value=0, max_value=130, step=1),
            "Capitán": st.column_config.CheckboxColumn(),
        },
        disabled=["Jugador"], num_rows="fixed",
    )
    selected = edited[edited["selected"] == True]  # noqa: E712
    starters = int(selected["Titular"].sum()) if len(selected) else 0
    st.caption(f"Seleccionados: {len(selected)} · Titulares: {starters} · Los suplentes no tienen límite fijo.")
    if st.button("Guardar alineación", type="primary", key=f"save_lineup_{key}", use_container_width=True):
        data, errors = [], []
        for _, row in edited.iterrows():
            if not bool(row["selected"]):
                continue
            minute_in = int(row["Entrada"] or 0)
            minute_out = int(row["Salida"] or 90)
            if minute_out < minute_in:
                errors.append(f"{row['Jugador']}: la salida no puede ser anterior a la entrada.")
            if bool(row["Titular"]) and minute_in != 0:
                errors.append(f"{row['Jugador']}: un titular debe entrar en el minuto 0.")
            data.append({
                "selected": True,
                "player_id": int(row["player_id"]),
                "shirt_number": int(row["Dorsal"]) if pd.notna(row["Dorsal"]) else None,
                "starter": bool(row["Titular"]),
                "position": row["Posición"],
                "minute_in": minute_in,
                "minute_out": minute_out,
                "captain": bool(row["Capitán"]),
            })
        if starters > 11:
            errors.append("No puede haber más de 11 titulares.")
        if len([x for x in data if x["captain"]]) > 1:
            errors.append("Solo puede existir un capitán por equipo.")
        if errors:
            for error in errors:
                st.error(error)
            return
        try:
            with session_scope() as session:
                repo.replace_participations(session, match_id, team_id, data, actor_id)
            st.success("Alineación guardada y evaluaciones en borrador reconciliadas.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _match_editor(matches, user: dict) -> None:
    if not matches:
        st.info("No hay partidos.")
        return
    st.dataframe(pd.DataFrame([{
        "ID": m.id,
        "Fecha": m.match_date,
        "Temporada": m.season.name,
        "Competición": m.competition.name,
        "Jornada": m.round_name,
        "Partido": f"{m.home_team.name} - {m.away_team.name}",
        "Resultado": f"{m.home_score}-{m.away_score}" if m.home_score is not None and m.away_score is not None else "",
        "Estado": MATCH_STATUSES.get(m.status, m.status),
        "Entrega": m.report_due_at,
        "Revisión": m.revision,
    } for m in matches]), use_container_width=True, hide_index=True)
    labels = {m.id: match_label(m) for m in matches}
    selected = st.selectbox("Editar partido", [m.id for m in matches], format_func=lambda mid: labels[mid])
    match = next(m for m in matches if m.id == selected)
    with session_scope() as session:
        seasons = repo.list_seasons(session, active_only=True)
        competitions = repo.list_competitions(session, active_only=True)
        teams = repo.list_teams(session, active_only=True)
    due_date = match.report_due_at.date() if match.report_due_at else match.match_date
    due_time = match.report_due_at.time() if match.report_due_at else time(23, 59)
    with st.form(f"edit_match_{match.id}"):
        c1, c2 = st.columns(2)
        season_id = c1.selectbox("Temporada", [s.id for s in seasons], index=next((i for i, s in enumerate(seasons) if s.id == match.season_id), 0), format_func=lambda sid: next(s.name for s in seasons if s.id == sid))
        competition_id = c2.selectbox("Competición", [c.id for c in competitions], index=next((i for i, c in enumerate(competitions) if c.id == match.competition_id), 0), format_func=lambda cid: next(c.name for c in competitions if c.id == cid))
        c3, c4 = st.columns(2)
        round_name = c3.text_input("Jornada / eliminatoria", value=match.round_name)
        match_date = c4.date_input("Fecha", value=match.match_date)
        c5, c6 = st.columns(2)
        home_team_id = c5.selectbox("Local", [t.id for t in teams], index=next((i for i, t in enumerate(teams) if t.id == match.home_team_id), 0), format_func=lambda tid: next(t.name for t in teams if t.id == tid))
        away_team_id = c6.selectbox("Visitante", [t.id for t in teams], index=next((i for i, t in enumerate(teams) if t.id == match.away_team_id), 0), format_func=lambda tid: next(t.name for t in teams if t.id == tid))
        c7, c8, c9 = st.columns(3)
        home_score = c7.number_input("Goles local", min_value=0, max_value=30, value=int(match.home_score or 0))
        away_score = c8.number_input("Goles visitante", min_value=0, max_value=30, value=int(match.away_score or 0))
        status_keys = list(MATCH_STATUSES.keys())[:3]
        status = c9.selectbox("Estado", status_keys, index=status_keys.index(match.status) if match.status in status_keys else 0, format_func=lambda key: MATCH_STATUSES[key])
        venue = st.text_input("Estadio / ubicación", value=match.venue or "")
        f1, f2 = st.columns(2)
        with f1:
            home_formation = _formation_input("Formación local", f"edit_home_{match.id}", match.home_formation)
        with f2:
            away_formation = _formation_input("Formación visitante", f"edit_away_{match.id}", match.away_formation)
        d1, d2 = st.columns(2)
        report_due_date = d1.date_input("Fecha límite del informe", value=due_date)
        report_due_time = d2.time_input("Hora límite", value=due_time)
        save = st.form_submit_button("Guardar todos los cambios", type="primary")
    if save:
        if home_team_id == away_team_id:
            st.error("Local y visitante no pueden ser el mismo equipo.")
        else:
            try:
                with session_scope() as session:
                    repo.update_match(
                        session, match.id, user["id"], expected_revision=match.revision,
                        season_id=season_id, competition_id=competition_id, round_name=round_name.strip(),
                        match_date=match_date, home_team_id=home_team_id, away_team_id=away_team_id,
                        home_score=home_score, away_score=away_score, status=status, venue=venue.strip() or None,
                        home_formation=home_formation, away_formation=away_formation,
                        report_due_at=datetime.combine(report_due_date, report_due_time),
                    )
                st.success("Partido actualizado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with st.expander("Archivar partido"):
        st.warning("El partido dejará de aparecer en los listados normales. Los informes y versiones no se eliminan.")
        if st.button("Archivar", key=f"archive_match_{match.id}"):
            try:
                with session_scope() as session:
                    repo.archive_match(session, match.id, user["id"])
                st.success("Partido archivado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def render(user: dict) -> None:
    page_header("Partidos · mantenimiento", "El alta normal se hace desde Nuevo postpartido. Aquí solo corriges, revisas o importas datos.")
    tab_list, tab_lineups, tab_assign, tab_import = st.tabs(["Partidos", "Alineaciones", "Asignaciones", "Importar"])

    with tab_list:
        with session_scope() as session:
            matches = repo.list_matches(session)
        _match_editor(matches, user)

    with tab_lineups:
        st.caption("Edición avanzada. En el uso normal las alineaciones se preparan dentro de Nuevo postpartido.")
        with session_scope() as session:
            matches = repo.list_matches(session)
        if not matches:
            st.info("No hay partidos.")
        else:
            labels = {m.id: match_label(m) for m in matches}
            selected_id = st.selectbox("Partido a corregir", [m.id for m in matches], format_func=lambda mid: labels[mid], key="lineup_match")
            match = next(m for m in matches if m.id == selected_id)
            local_tab, away_tab = st.tabs([match.home_team.name, match.away_team.name])
            with local_tab:
                _lineup_editor(match.id, match.home_team_id, match.season_id, user["id"], f"{match.id}_home")
            with away_tab:
                _lineup_editor(match.id, match.away_team_id, match.season_id, user["id"], f"{match.id}_away")

    with tab_assign:
        with session_scope() as session:
            matches = repo.list_matches(session)
            reporters = [u for u in repo.list_users(session, active_only=True) if u.role in {"reporter", "admin", "director"}]
        if not matches or not reporters:
            st.info("Necesitas al menos un partido y un usuario activo.")
        else:
            labels = {m.id: match_label(m) for m in matches}
            selected_id = st.selectbox("Partido", [m.id for m in matches], format_func=lambda mid: labels[mid], key="assignment_match")
            match = next(m for m in matches if m.id == selected_id)
            with session_scope() as session:
                current = repo.list_assignments(session, match_id=selected_id)
                progress = repo.assignment_progress(session, selected_id)
            c1, c2, c3 = st.columns(3)
            c1.metric("Asignados", progress.get("total", 0))
            c2.metric("Entregados", progress.get("submitted", 0))
            c3.metric("Aprobados", progress.get("approved", 0))
            current_ids = [a.user_id for a in current if a.status != "waived"]
            with st.form(f"assign_reporters_{selected_id}"):
                selected_users = st.multiselect(
                    "Informadores asignados",
                    [u.id for u in reporters],
                    default=current_ids,
                    format_func=lambda uid: next(f"{u.full_name} · {ROLES.get(u.role, u.role)}" for u in reporters if u.id == uid),
                )
                required = st.checkbox("Informes obligatorios", value=True)
                due_enabled = st.checkbox("Usar fecha límite", value=bool(match.report_due_at))
                if due_enabled:
                    d1, d2 = st.columns(2)
                    due_d = d1.date_input("Fecha límite", value=(match.report_due_at.date() if match.report_due_at else match.match_date))
                    due_t = d2.time_input("Hora límite", value=(match.report_due_at.time() if match.report_due_at else time(23, 59)))
                    due_at = datetime.combine(due_d, due_t)
                else:
                    due_at = None
                save_assignments = st.form_submit_button("Guardar asignaciones", type="primary")
            if save_assignments:
                try:
                    with session_scope() as session:
                        repo.assign_reporters(session, selected_id, selected_users, user["id"], due_at, required)
                    st.success("Asignaciones actualizadas.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tab_import:
        st.caption("La importación es secundaria: el flujo Nuevo postpartido permite crear rivales y jugadores sin archivos.")
        st.download_button("Descargar plantilla Excel", template_workbook(), "plantilla_noname_postmatch.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        import_type_label = st.radio("Tipo de importación", ["Plantillas de equipos", "Alineaciones de un partido"], horizontal=True)
        import_type = "rosters" if import_type_label.startswith("Plantillas") else "lineups"
        uploaded = st.file_uploader("CSV o Excel (.xlsx)", type=["csv", "xlsx"])
        if uploaded:
            try:
                sheets = available_sheets(uploaded)
                sheet = None
                if sheets:
                    preferred = "plantillas" if import_type == "rosters" else "alineaciones"
                    default_idx = next((i for i, name in enumerate(sheets) if preferred in name.lower()), 0)
                    sheet = st.selectbox("Hoja del Excel", sheets, index=default_idx)
                df = read_table(uploaded, sheet_name=sheet)
                preview = preview_import(df, import_type)
                st.dataframe(preview["data"].head(100), use_container_width=True, hide_index=True)
                if preview["errors"]:
                    st.error("La importación contiene errores y no puede confirmarse.")
                    for error in preview["errors"][:30]:
                        st.write(f"- {error}")
                if preview["warnings"]:
                    st.warning("Advertencias de calidad de datos")
                    for warning in preview["warnings"][:30]:
                        st.write(f"- {warning}")
                confirm = st.button("Confirmar importación", type="primary", disabled=bool(preview["errors"]))
                if confirm:
                    with session_scope() as session:
                        result = import_rosters(session, df, user["id"]) if import_type == "rosters" else import_lineup(session, df, user["id"])
                    if result.get("errors"):
                        st.warning(f"Importación finalizada con incidencias: {len(result['errors'])}.")
                        for error in result["errors"][:30]:
                            st.write(f"- {error}")
                    else:
                        st.success(f"Importación completada. Filas: {result.get('roster_links', result.get('imported', result.get('rows', 0)))} · Jugadores creados: {result.get('created_players', 0)}")
                    st.rerun()
            except Exception as exc:
                st.error(str(exc))
