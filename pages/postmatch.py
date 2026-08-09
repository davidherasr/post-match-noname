from __future__ import annotations

from datetime import date, datetime, time, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st

from core.constants import FORMATIONS, POSITIONS, ROLES
from core.database import session_scope
from models.entities import Competition, Team
from repositories import scouting as repo
from services.import_service import available_sheets, normalize_columns, read_table
from ui.styles import page_header


WIZARD_KEY = "postmatch_3_match_id"
RIVAL_DRAFT_KEY = "postmatch_3_rival_rows"


def _default_season_name(today: date | None = None) -> str:
    today = today or date.today()
    start = today.year if today.month >= 7 else today.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def _bool_value(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return str(value).strip().casefold() in {"si", "sí", "true", "1", "x", "titular", "t"}


def _int_value(value, default: int | None = None) -> int | None:
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _setup_own_team(user: dict) -> None:
    st.info("Esta instalación está pensada para No Name. Solo necesitas configurar el club una vez.")
    with st.form("noname_setup_form"):
        name = st.text_input("Nombre del equipo", value="No Name")
        short = st.text_input("Nombre corto", value="NO NAME")
        country = st.text_input("País (opcional)", value="España")
        save = st.form_submit_button("Configurar No Name", type="primary", use_container_width=True)
    if save:
        if not name.strip():
            st.error("Escribe el nombre del equipo.")
            return
        with session_scope() as session:
            team = repo.create_team(
                session,
                name.strip(),
                short_name=short.strip() or None,
                country=country.strip() or None,
                is_own_team=True,
                actor_id=user["id"],
            )
            repo.set_setting(session, "club_name", team.name, user["id"])
            repo.set_setting(session, "edition", "noname", user["id"])
        st.success("Club configurado. Ya puedes preparar el primer postpartido.")
        st.rerun()


def _setup_season(user: dict) -> None:
    st.warning("Todavía no hay una temporada activa. Créala aquí sin salir del postpartido.")
    with st.form("quick_season_form"):
        name = st.text_input("Temporada", value=_default_season_name())
        c1, c2 = st.columns(2)
        start = c1.date_input("Inicio", value=date(date.today().year if date.today().month >= 7 else date.today().year - 1, 7, 1))
        end = c2.date_input("Fin", value=date((date.today().year if date.today().month >= 7 else date.today().year - 1) + 1, 6, 30))
        save = st.form_submit_button("Crear temporada", type="primary", use_container_width=True)
    if save:
        with session_scope() as session:
            season = repo.create_season(session, name.strip(), start, end, user["id"])
            repo.set_active_season(session, season.id, user["id"])
        st.success("Temporada creada y seleccionada.")
        st.rerun()


def _draft_matches_for_user(user: dict, own_team_id: int) -> list:
    with session_scope() as session:
        return [
            m for m in repo.list_matches(session, status="draft", limit=30)
            if own_team_id in {m.home_team_id, m.away_team_id} and m.created_by == user["id"]
        ]


def _render_match_creation(user: dict, own_team) -> None:
    with session_scope() as session:
        seasons = repo.list_seasons(session, active_only=True)
        active_season = repo.get_active_season(session)
        competitions = repo.list_competitions(session, active_only=True)
        teams = [t for t in repo.list_teams(session, active_only=True) if t.id != own_team.id]
        last_competition_raw = repo.get_setting(session, "last_competition_id")
        season_match_count = len([m for m in repo.list_matches(session, limit=500) if active_season and m.season_id == active_season.id and own_team.id in {m.home_team_id, m.away_team_id}])

    if not seasons:
        _setup_season(user)
        return

    st.markdown("### 1 · Partido")
    st.caption("Crea el contexto mínimo. Si la competición o el rival no existen, se crean aquí mismo.")

    season_ids = [s.id for s in seasons]
    default_season = active_season.id if active_season and active_season.id in season_ids else season_ids[0]
    competition_options = [c.id for c in competitions] + [None]
    team_options = [None] + [t.id for t in teams]
    try:
        last_competition_id = int(last_competition_raw) if last_competition_raw else None
    except (TypeError, ValueError):
        last_competition_id = None
    competition_default_index = competition_options.index(last_competition_id) if last_competition_id in competition_options else 0

    season_id = st.selectbox(
        "Temporada",
        season_ids,
        index=season_ids.index(default_season),
        format_func=lambda sid: next(s.name for s in seasons if s.id == sid),
        key="postmatch_season",
    )
    c1, c2 = st.columns(2)
    competition_id = c1.selectbox(
        "Competición",
        competition_options,
        index=competition_default_index,
        format_func=lambda cid: "＋ Crear competición" if cid is None else next(c.name for c in competitions if c.id == cid),
        key="postmatch_competition",
    )
    new_competition = c1.text_input("Nombre de la nueva competición", placeholder="Liga, Copa...", disabled=competition_id is not None)
    rival_id = c2.selectbox(
        "Rival",
        team_options,
        format_func=lambda tid: "＋ Crear rival" if tid is None else next(t.name for t in teams if t.id == tid),
        key="postmatch_rival",
    )
    new_rival = c2.text_input("Nombre del nuevo rival", placeholder="Nombre del equipo", disabled=rival_id is not None)

    c3, c4, c5 = st.columns([1.1, 1, 1])
    round_name = c3.text_input("Jornada / partido", value=f"Jornada {season_match_count + 1}")
    match_date = c4.date_input("Fecha", value=date.today())
    own_location = c5.radio("No Name juega", ["Local", "Visitante"], horizontal=True)

    s1, s2 = st.columns(2)
    own_score = s1.number_input(f"Goles {own_team.name}", min_value=0, max_value=30, value=0, step=1)
    rival_label = next((t.name for t in teams if t.id == rival_id), None) or new_rival.strip() or "Rival"
    rival_score = s2.number_input(f"Goles {rival_label}", min_value=0, max_value=30, value=0, step=1)

    with st.expander("Opciones del partido", expanded=False):
        venue = st.text_input("Campo / ubicación (opcional)")
        f1, f2 = st.columns(2)
        own_formation = f1.selectbox("Sistema No Name (opcional)", ["No indicado"] + FORMATIONS, index=0)
        rival_formation = f2.selectbox("Sistema rival (opcional)", ["No indicado"] + FORMATIONS, index=0)
        set_due = st.checkbox("Añadir fecha límite para los informes", value=False)
        if set_due:
            d1, d2 = st.columns(2)
            due_date = d1.date_input("Fecha límite", value=match_date + timedelta(days=1))
            due_time = d2.time_input("Hora límite", value=time(20, 0))
        else:
            due_date, due_time = None, None

    if st.button("Guardar partido y continuar", type="primary", use_container_width=True):
        if competition_id is None and not new_competition.strip():
            st.error("Selecciona una competición o crea una nueva.")
            return
        if rival_id is None and not new_rival.strip():
            st.error("Selecciona un rival o crea uno nuevo.")
            return
        if not round_name.strip():
            st.error("Indica la jornada o nombre del partido.")
            return
        try:
            with session_scope() as session:
                repo.set_active_season(session, season_id, user["id"])
                competition = session.get(Competition, competition_id) if competition_id is not None else None
                if competition is None:
                    competition = repo.create_competition(session, new_competition.strip(), actor_id=user["id"])
                repo.set_setting(session, "last_competition_id", str(competition.id), user["id"])
                rival = session.get(Team, rival_id) if rival_id is not None else None
                if rival is None:
                    rival = repo.create_team(session, new_rival.strip(), actor_id=user["id"])
                if own_location == "Local":
                    home_id, away_id = own_team.id, rival.id
                    home_score, away_score = int(own_score), int(rival_score)
                    home_formation = None if own_formation == "No indicado" else own_formation
                    away_formation = None if rival_formation == "No indicado" else rival_formation
                else:
                    home_id, away_id = rival.id, own_team.id
                    home_score, away_score = int(rival_score), int(own_score)
                    home_formation = None if rival_formation == "No indicado" else rival_formation
                    away_formation = None if own_formation == "No indicado" else own_formation
                match = repo.create_match(
                    session,
                    season_id=season_id,
                    competition_id=competition.id,
                    round_name=round_name.strip(),
                    match_date=match_date,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    created_by=user["id"],
                    home_score=home_score,
                    away_score=away_score,
                    venue=venue.strip() or None,
                    home_formation=home_formation,
                    away_formation=away_formation,
                    status="draft",
                    report_due_at=datetime.combine(due_date, due_time) if due_date and due_time else None,
                )
                st.session_state[WIZARD_KEY] = match.id
                st.session_state.pop(RIVAL_DRAFT_KEY, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _parse_roster_lines(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";")]
        name = parts[0]
        position = parts[1].upper() if len(parts) > 1 and parts[1] else "Otro"
        shirt = _int_value(parts[2], None) if len(parts) > 2 else None
        rows.append({"name": name, "position": position if position in POSITIONS else "Otro", "shirt_number": shirt})
    return rows


def _add_roster_players(user: dict, team_id: int, season_id: int) -> None:
    with st.expander("Añadir jugadores a la plantilla de No Name", expanded=False):
        with st.form("quick_add_own_player"):
            a, b, c = st.columns([2, 1, 1])
            name = a.text_input("Nombre")
            position = b.selectbox("Posición", POSITIONS)
            shirt = c.number_input("Dorsal", min_value=0, max_value=99, value=None, step=1)
            add = st.form_submit_button("Añadir jugador")
        if add:
            if not name.strip():
                st.error("Escribe el nombre del jugador.")
            else:
                with session_scope() as session:
                    player = repo.find_or_create_player(session, name.strip(), primary_position=position, actor_id=user["id"])
                    repo.assign_player_to_roster(session, team_id, season_id, player.id, shirt, user["id"])
                st.success(f"{name.strip()} añadido a la plantilla.")
                st.rerun()

        st.caption("Alta rápida en bloque: una línea por jugador con `Nombre;POS;Dorsal`. Posición y dorsal son opcionales.")
        bulk = st.text_area("Pegar jugadores", placeholder="Mario Losada;DC;9\nPablo García;DFC;4", height=120)
        if st.button("Añadir lista a la plantilla", use_container_width=True):
            parsed = _parse_roster_lines(bulk)
            if not parsed:
                st.warning("No hay jugadores que añadir.")
            else:
                try:
                    with session_scope() as session:
                        for row in parsed:
                            player = repo.find_or_create_player(
                                session,
                                row["name"],
                                primary_position=row["position"],
                                actor_id=user["id"],
                            )
                            repo.assign_player_to_roster(
                                session,
                                team_id,
                                season_id,
                                player.id,
                                row["shirt_number"],
                                user["id"],
                            )
                    st.success(f"{len(parsed)} jugadores procesados.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def _own_lineup_frame(roster, existing) -> pd.DataFrame:
    existing_map = {p.player_id: p for p in existing}
    rows = []
    for item in roster:
        part = existing_map.get(item.player_id)
        rows.append({
            "Incluir": bool(part),
            "player_id": item.player_id,
            "Jugador": item.player.display_name or item.player.full_name,
            "Dorsal": part.shirt_number if part else item.shirt_number,
            "Titular": bool(part.starter) if part else False,
            "Posición": part.position if part else (item.player.primary_position or "Otro"),
            "Entrada": part.minute_in if part else 0,
            "Salida": part.minute_out if part else 90,
            "Capitán": bool(part.captain) if part else False,
        })
    return pd.DataFrame(rows)


def _render_own_lineup(match, own_team, user: dict) -> bool:
    st.markdown(f"### 2 · Alineación {own_team.name}")
    st.caption("Tu plantilla se reutiliza durante toda la temporada. Solo marcas quién jugó y los minutos.")
    with session_scope() as session:
        roster = repo.get_roster(session, own_team.id, match.season_id)
        existing = repo.get_participations(session, match.id, own_team.id)
        previous = repo.previous_match_with_team(
            session,
            own_team.id,
            before_date=match.match_date,
            exclude_match_id=match.id,
        )

    _add_roster_players(user, own_team.id, match.season_id)
    if not roster:
        st.warning("Añade la plantilla de No Name aquí arriba. No necesitas ir a Base de datos.")
        return False

    if previous:
        left, right = st.columns([3, 1])
        left.caption(f"Última alineación disponible: {previous.match_date.strftime('%d/%m/%Y')} · {previous.home_team.name} - {previous.away_team.name}")
        if right.button("Copiar última alineación", use_container_width=True, key=f"copy_own_{match.id}"):
            try:
                with session_scope() as session:
                    repo.copy_lineup_from_match(
                        session,
                        source_match_id=previous.id,
                        target_match_id=match.id,
                        team_id=own_team.id,
                        actor_id=user["id"],
                    )
                st.success("Alineación anterior copiada. Ajusta únicamente los cambios de este partido.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    frame = _own_lineup_frame(roster, existing)
    edited = st.data_editor(
        frame,
        use_container_width=True,
        hide_index=True,
        key=f"noname_lineup_{match.id}",
        column_config={
            "Incluir": st.column_config.CheckboxColumn("Jugó"),
            "player_id": None,
            "Jugador": st.column_config.TextColumn(),
            "Dorsal": st.column_config.NumberColumn(min_value=0, max_value=99, step=1),
            "Titular": st.column_config.CheckboxColumn(),
            "Posición": st.column_config.SelectboxColumn(options=POSITIONS),
            "Entrada": st.column_config.NumberColumn(min_value=0, max_value=130, step=1),
            "Salida": st.column_config.NumberColumn(min_value=0, max_value=130, step=1),
            "Capitán": st.column_config.CheckboxColumn(),
        },
        disabled=["Jugador"],
        num_rows="fixed",
    )
    selected = edited[edited["Incluir"] == True]  # noqa: E712
    starters = int(selected["Titular"].sum()) if len(selected) else 0
    st.caption(f"Jugadores incluidos: {len(selected)} · Titulares: {starters}")
    if st.button("Guardar alineación No Name", type="primary", use_container_width=True, key=f"save_own_{match.id}"):
        rows, errors = [], []
        for _, row in selected.iterrows():
            minute_in = _int_value(row["Entrada"], 0) or 0
            minute_out = _int_value(row["Salida"], 90) or 90
            starter = bool(row["Titular"])
            if starter:
                minute_in = 0
            if minute_out < minute_in:
                errors.append(f"{row['Jugador']}: salida anterior a entrada.")
            rows.append({
                "selected": True,
                "player_id": int(row["player_id"]),
                "shirt_number": _int_value(row["Dorsal"], None),
                "starter": starter,
                "position": row["Posición"] or "Otro",
                "minute_in": minute_in,
                "minute_out": minute_out,
                "captain": bool(row["Capitán"]),
            })
        if starters > 11:
            errors.append("No puede haber más de 11 titulares.")
        if len([r for r in rows if r["captain"]]) > 1:
            errors.append("Solo puede haber un capitán.")
        if errors:
            for error in errors:
                st.error(error)
        elif not rows:
            st.error("Selecciona al menos un jugador.")
        else:
            try:
                with session_scope() as session:
                    repo.replace_participations(session, match.id, own_team.id, rows, user["id"])
                st.success("Alineación de No Name guardada.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    return bool(existing)


def _blank_rival_rows() -> list[dict]:
    suggested = ["POR", "LD", "DFC", "DFC", "LI", "MCD", "MC", "MP", "ED", "EI", "DC"]
    return [
        {"Jugador": "", "Dorsal": None, "Posición": pos, "Titular": True, "Entrada": 0, "Salida": 90, "Capitán": False}
        for pos in suggested
    ]


def _participations_to_named_rows(parts) -> list[dict]:
    return [{
        "Jugador": p.player.display_name or p.player.full_name,
        "Dorsal": p.shirt_number,
        "Posición": p.position or p.player.primary_position or "Otro",
        "Titular": p.starter,
        "Entrada": p.minute_in,
        "Salida": p.minute_out,
        "Capitán": p.captain,
    } for p in parts]


def _load_uploaded_rival(uploaded) -> list[dict]:
    sheets = available_sheets(uploaded)
    sheet = sheets[0] if sheets else None
    df = normalize_columns(read_table(uploaded, sheet_name=sheet))
    aliases = {
        "nombre": "jugador",
        "player": "jugador",
        "position": "posicion",
        "shirt_number": "dorsal",
        "entrada": "minuto_entrada",
        "salida": "minuto_salida",
        "captain": "capitan",
    }
    df = df.rename(columns=aliases)
    if "jugador" not in df.columns:
        raise ValueError("El archivo necesita una columna 'jugador' o 'nombre'.")
    rows = []
    for _, row in df.iterrows():
        name = str(row.get("jugador") or "").strip()
        if not name or name.casefold() == "nan":
            continue
        rows.append({
            "Jugador": name,
            "Dorsal": _int_value(row.get("dorsal"), None),
            "Posición": str(row.get("posicion") or "Otro").strip().upper(),
            "Titular": _bool_value(row.get("titular"), True),
            "Entrada": _int_value(row.get("minuto_entrada"), 0) or 0,
            "Salida": _int_value(row.get("minuto_salida"), 90) or 90,
            "Capitán": _bool_value(row.get("capitan"), False),
        })
    return rows


def _parse_rival_text(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) == 1:
            name, dorsal, pos, starter, minute_in, minute_out = parts[0], None, "Otro", True, 0, 90
        else:
            dorsal = _int_value(parts[0], None)
            name = parts[1] if len(parts) > 1 else ""
            pos = parts[2].upper() if len(parts) > 2 and parts[2] else "Otro"
            starter = _bool_value(parts[3], True) if len(parts) > 3 else True
            minute_in = _int_value(parts[4], 0) if len(parts) > 4 else 0
            minute_out = _int_value(parts[5], 90) if len(parts) > 5 else 90
        rows.append({
            "Jugador": name,
            "Dorsal": dorsal,
            "Posición": pos if pos in POSITIONS else "Otro",
            "Titular": starter,
            "Entrada": minute_in or 0,
            "Salida": minute_out or 90,
            "Capitán": False,
        })
    return rows


def _render_rival_lineup(match, own_team, user: dict) -> bool:
    rival = match.away_team if match.home_team_id == own_team.id else match.home_team
    st.markdown(f"### 3 · Alineación rival · {rival.name}")
    st.caption("No hace falta crear antes su plantilla. Escribe los jugadores aquí y la base se actualiza automáticamente.")

    with session_scope() as session:
        existing = repo.get_participations(session, match.id, rival.id)
        previous = repo.previous_match_with_team(
            session,
            rival.id,
            before_date=match.match_date,
            exclude_match_id=match.id,
            opponent_id=own_team.id,
        ) or repo.previous_match_with_team(
            session,
            rival.id,
            before_date=match.match_date,
            exclude_match_id=match.id,
        )

    if existing:
        base_rows = _participations_to_named_rows(existing)
        st.session_state[RIVAL_DRAFT_KEY] = base_rows
    elif RIVAL_DRAFT_KEY not in st.session_state:
        st.session_state[RIVAL_DRAFT_KEY] = _blank_rival_rows()

    if previous:
        left, right = st.columns([3, 1])
        left.caption(f"Última alineación conocida: {previous.match_date.strftime('%d/%m/%Y')} · {previous.home_team.name} - {previous.away_team.name}")
        if right.button("Usar última alineación", use_container_width=True, key=f"copy_rival_{match.id}"):
            try:
                with session_scope() as session:
                    repo.copy_lineup_from_match(
                        session,
                        source_match_id=previous.id,
                        target_match_id=match.id,
                        team_id=rival.id,
                        actor_id=user["id"],
                    )
                st.session_state.pop(RIVAL_DRAFT_KEY, None)
                st.success("Alineación rival recuperada. Corrige únicamente los cambios.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with st.expander("Pegar o importar alineación", expanded=False):
        st.caption("Formato rápido recomendado: `Dorsal;Nombre;POS;Titular;Entrada;Salida`. También puedes escribir solo el nombre.")
        pasted = st.text_area("Pegar lista", placeholder="1;Bote;POR;Sí;0;90\n4;Checkmate;DFC;Sí;0;90", height=120)
        if st.button("Cargar texto en la tabla", use_container_width=True):
            rows = _parse_rival_text(pasted)
            if rows:
                st.session_state[RIVAL_DRAFT_KEY] = rows
                st.rerun()
            else:
                st.warning("No se han detectado jugadores.")
        uploaded = st.file_uploader("Importar CSV/XLSX", type=["csv", "xlsx"], key=f"rival_upload_{match.id}")
        if uploaded and st.button("Cargar archivo en la tabla", key=f"load_rival_upload_{match.id}"):
            try:
                rows = _load_uploaded_rival(uploaded)
                if not rows:
                    raise ValueError("El archivo no contiene jugadores.")
                st.session_state[RIVAL_DRAFT_KEY] = rows
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    df = pd.DataFrame(st.session_state[RIVAL_DRAFT_KEY])
    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key=f"rival_lineup_editor_{match.id}",
        column_config={
            "Jugador": st.column_config.TextColumn(required=False),
            "Dorsal": st.column_config.NumberColumn(min_value=0, max_value=99, step=1),
            "Posición": st.column_config.SelectboxColumn(options=POSITIONS),
            "Titular": st.column_config.CheckboxColumn(),
            "Entrada": st.column_config.NumberColumn(min_value=0, max_value=130, step=1),
            "Salida": st.column_config.NumberColumn(min_value=0, max_value=130, step=1),
            "Capitán": st.column_config.CheckboxColumn(),
        },
    )
    valid_names = [str(x).strip() for x in edited.get("Jugador", []) if str(x).strip() and str(x).strip().casefold() != "nan"]
    starters = int(edited[edited["Jugador"].astype(str).str.strip().ne("")]["Titular"].fillna(False).sum()) if "Titular" in edited.columns else 0
    st.caption(f"Jugadores escritos: {len(valid_names)} · Titulares: {starters}")

    if st.button("Guardar alineación rival", type="primary", use_container_width=True, key=f"save_rival_{match.id}"):
        rows = []
        for _, row in edited.iterrows():
            name = str(row.get("Jugador") or "").strip()
            if not name or name.casefold() == "nan":
                continue
            starter = bool(row.get("Titular", False))
            rows.append({
                "name": name,
                "shirt_number": _int_value(row.get("Dorsal"), None),
                "position": str(row.get("Posición") or "Otro"),
                "starter": starter,
                "minute_in": 0 if starter else (_int_value(row.get("Entrada"), 0) or 0),
                "minute_out": _int_value(row.get("Salida"), 90) or 90,
                "captain": bool(row.get("Capitán", False)),
            })
        try:
            with session_scope() as session:
                repo.save_named_lineup(
                    session,
                    match_id=match.id,
                    team_id=rival.id,
                    season_id=match.season_id,
                    rows=rows,
                    actor_id=user["id"],
                    sync_roster=True,
                )
            st.session_state.pop(RIVAL_DRAFT_KEY, None)
            st.success("Alineación rival guardada y plantilla rival actualizada automáticamente.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    return bool(existing)


def _render_publish(match, own_team, user: dict) -> None:
    rival = match.away_team if match.home_team_id == own_team.id else match.home_team
    with session_scope() as session:
        own_parts = repo.get_participations(session, match.id, own_team.id)
        rival_parts = repo.get_participations(session, match.id, rival.id)
        users = [u for u in repo.list_users(session, active_only=True) if u.role in {"reporter", "admin", "director"}]
        current = repo.list_assignments(session, match_id=match.id)

    st.markdown("### 4 · Publicar postpartido")
    a, b, c, d = st.columns(4)
    a.metric(own_team.name, len(own_parts))
    b.metric(rival.name, len(rival_parts))
    c.metric("Titulares propios", len([p for p in own_parts if p.starter]))
    d.metric("Titulares rivales", len([p for p in rival_parts if p.starter]))

    if not own_parts or not rival_parts:
        st.warning("Guarda las dos alineaciones antes de publicar.")
        return

    reporter_ids = [u.id for u in users]
    current_ids = [a.user_id for a in current if a.status != "waived"]
    default_reporters = current_ids or [u.id for u in users if u.role == "reporter"]
    selected = st.multiselect(
        "Quién puede/debe informar este partido",
        reporter_ids,
        default=[uid for uid in default_reporters if uid in reporter_ids],
        format_func=lambda uid: next(f"{u.full_name} · {ROLES.get(u.role, u.role)}" for u in users if u.id == uid),
    )
    st.caption("Si no seleccionas a nadie, el partido se publica igualmente y administración/dirección podrán abrirlo.")

    due_enabled = st.checkbox("Usar fecha límite", value=bool(match.report_due_at))
    if due_enabled:
        x, y = st.columns(2)
        due_date = x.date_input("Fecha límite", value=match.report_due_at.date() if match.report_due_at else match.match_date + timedelta(days=1))
        due_time = y.time_input("Hora límite", value=match.report_due_at.time() if match.report_due_at else time(20, 0))
        due_at = datetime.combine(due_date, due_time)
    else:
        due_at = None

    st.success("Todo lo necesario está preparado. Publicar hará que el partido aparezca en el panel de los informadores.")
    if st.button("PUBLICAR POSTPARTIDO", type="primary", use_container_width=True):
        try:
            with session_scope() as session:
                repo.update_match(session, match.id, user["id"], status="published", report_due_at=due_at)
                if selected:
                    repo.assign_reporters(session, match.id, selected, user["id"], due_at=due_at, required=True)
                repo.audit(session, user["id"], "publish_postmatch", "match", match.id, detail=f"reporters={len(selected)}")
            st.session_state.pop(WIZARD_KEY, None)
            st.session_state.pop(RIVAL_DRAFT_KEY, None)
            st.session_state["postmatch_3_published"] = match.id
            st.success("Postpartido publicado. Ya está disponible para valorar.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _render_active_draft(match_id: int, own_team, user: dict) -> None:
    with session_scope() as session:
        match = repo.get_match(session, match_id)
    if not match or match.status != "draft":
        st.session_state.pop(WIZARD_KEY, None)
        st.rerun()
        return

    rival = match.away_team if match.home_team_id == own_team.id else match.home_team
    with st.container(border=True):
        st.markdown(f"**{match.home_team.name} {match.home_score if match.home_score is not None else '-'} - {match.away_score if match.away_score is not None else '-'} {match.away_team.name}**")
        st.caption(f"{match.competition.name} · {match.round_name} · {match.match_date.strftime('%d/%m/%Y')} · borrador")
        c1, c2 = st.columns([1, 3])
        if c1.button("Descartar este borrador", use_container_width=True):
            with session_scope() as session:
                repo.archive_match(session, match.id, user["id"])
            st.session_state.pop(WIZARD_KEY, None)
            st.session_state.pop(RIVAL_DRAFT_KEY, None)
            st.rerun()
        c2.info(f"Rival: {rival.name}. Todo se configura en esta misma página.")

    st.divider()
    _render_own_lineup(match, own_team, user)
    st.divider()
    _render_rival_lineup(match, own_team, user)
    st.divider()
    with session_scope() as session:
        refreshed = repo.get_match(session, match.id)
    _render_publish(refreshed, own_team, user)


def render(user: dict) -> None:
    if user["role"] != "admin":
        st.error("Solo administración puede preparar un nuevo postpartido.")
        return

    page_header(
        "Nuevo postpartido",
        "Un único flujo: partido → No Name → rival → publicar. La base de datos trabaja por detrás.",
    )

    if st.session_state.pop("postmatch_3_published", None):
        st.success("Postpartido publicado correctamente. Puedes crear el siguiente cuando lo necesites.")

    with session_scope() as session:
        own_team = repo.get_own_team(session)
    if not own_team:
        _setup_own_team(user)
        return

    if WIZARD_KEY not in st.session_state:
        drafts = _draft_matches_for_user(user, own_team.id)
        if drafts:
            with st.expander("Continuar un borrador anterior", expanded=False):
                options = [m.id for m in drafts]
                selected = st.selectbox(
                    "Borrador",
                    options,
                    format_func=lambda mid: next(
                        f"{m.match_date.strftime('%d/%m/%Y')} · {m.home_team.name} - {m.away_team.name} · {m.round_name}"
                        for m in drafts if m.id == mid
                    ),
                )
                if st.button("Continuar este postpartido", use_container_width=True):
                    st.session_state[WIZARD_KEY] = selected
                    st.rerun()
        _render_match_creation(user, own_team)
        return

    _render_active_draft(int(st.session_state[WIZARD_KEY]), own_team, user)
