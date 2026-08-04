from __future__ import annotations

from io import BytesIO, StringIO
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import BASE_DIR
from core.utils import normalize_name, parse_date, safe_int
from models.entities import Match, Player, Team
from repositories import scouting as repo

PLAYER_COLUMNS = ["equipo", "temporada", "dorsal", "jugador", "posicion", "fecha_nacimiento", "nacionalidad"]
LINEUP_COLUMNS = ["partido_id", "equipo", "dorsal", "jugador", "posicion", "titular", "minuto_entrada", "minuto_salida", "capitan"]


def available_sheets(uploaded_file) -> list[str]:
    name = getattr(uploaded_file, "name", "").lower()
    if not name.endswith(".xlsx"):
        return []
    uploaded_file.seek(0)
    sheets = pd.ExcelFile(uploaded_file).sheet_names
    uploaded_file.seek(0)
    return sheets


def read_table(uploaded_file, sheet_name: str | int | None = None) -> pd.DataFrame:
    name = getattr(uploaded_file, "name", "").lower()
    uploaded_file.seek(0)
    if name.endswith(".csv"):
        raw = uploaded_file.read()
        text = None
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("No se ha podido detectar la codificación del CSV.")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        separator = ";" if first_line.count(";") > first_line.count(",") else ","
        return pd.read_csv(StringIO(text), sep=separator, decimal=",")
    if name.endswith(".xls"):
        raise ValueError("El formato .xls antiguo no está admitido. Guarda el archivo como .xlsx o CSV.")
    return pd.read_excel(uploaded_file, sheet_name=sheet_name or 0)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.columns = [normalize_name(str(c)).replace(" ", "_") for c in result.columns]
    result = result.dropna(how="all")
    return result


def validate_columns(df: pd.DataFrame, required: list[str]) -> list[str]:
    return [c for c in required if c not in df.columns]


def preview_import(df: pd.DataFrame, import_type: str) -> dict[str, Any]:
    df = normalize_columns(df)
    import_type = "plantillas" if import_type in {"plantillas", "rosters"} else "alineaciones"
    # Accept common short column names from manually prepared CSV files.
    df = df.rename(columns={"entrada": "minuto_entrada", "salida": "minuto_salida", "capitán": "capitan"})
    required = ["equipo", "temporada", "jugador"] if import_type == "plantillas" else ["partido_id", "equipo", "jugador"]
    missing = validate_columns(df, required)
    errors: list[str] = []
    warnings: list[str] = []
    if missing:
        errors.append(f"Faltan columnas: {', '.join(missing)}")
    duplicate_rows = int(df.duplicated(subset=[c for c in ["equipo", "temporada", "partido_id", "jugador"] if c in df.columns]).sum())
    if duplicate_rows:
        warnings.append(f"Se han detectado {duplicate_rows} filas repetidas.")
    if import_type == "alineaciones" and not missing:
        for (match_id, team), group in df.groupby(["partido_id", "equipo"], dropna=False):
            starters = group.get("titular", pd.Series(dtype=str)).astype(str).str.strip().str.lower().isin({"si", "sí", "true", "1", "x"}).sum()
            if starters > 11:
                errors.append(f"Partido {match_id} / {team}: hay {starters} titulares.")
            for idx, row in group.iterrows():
                minute_in = safe_int(row.get("minuto_entrada"), 0) or 0
                minute_out = safe_int(row.get("minuto_salida"), 90) or 90
                if minute_out < minute_in:
                    errors.append(f"Fila {idx + 2}: minuto de salida anterior al de entrada.")
    return {"dataframe": df, "data": df, "errors": errors, "warnings": warnings, "rows": len(df)}


def import_rosters(session: Session, df: pd.DataFrame, actor_id: int | None = None) -> dict:
    preview = preview_import(df, "plantillas")
    if preview["errors"]:
        raise ValueError(" | ".join(preview["errors"]))
    df = preview["dataframe"]
    created_players = 0
    roster_links = 0
    errors: list[str] = []
    for index, row in df.iterrows():
        try:
            with session.begin_nested():
                team_name = str(row.get("equipo", "")).strip()
                season_name = str(row.get("temporada", "")).strip()
                player_name = str(row.get("jugador", "")).strip()
                if not team_name or not season_name or not player_name:
                    raise ValueError("equipo, temporada y jugador son obligatorios")
                team = repo.create_team(session, team_name, actor_id=actor_id)
                season = repo.create_season(session, season_name, actor_id=actor_id)
                before = int(session.scalar(select(Player.id).where(Player.normalized_name == normalize_name(player_name)).limit(1)) or 0)
                player = repo.find_or_create_player(
                    session,
                    player_name,
                    date_of_birth=parse_date(row.get("fecha_nacimiento")),
                    primary_position=str(row.get("posicion", "")).strip() or None,
                    nationality=str(row.get("nacionalidad", "")).strip() or None,
                    actor_id=actor_id,
                )
                if not before:
                    created_players += 1
                repo.assign_player_to_roster(session, team.id, season.id, player.id, safe_int(row.get("dorsal")), actor_id)
                roster_links += 1
        except Exception as exc:
            errors.append(f"Fila {index + 2}: {exc}")
    return {"roster_links": roster_links, "created_players": created_players, "errors": errors, "warnings": preview["warnings"]}


def import_lineup(session: Session, df: pd.DataFrame, actor_id: int) -> dict:
    preview = preview_import(df, "alineaciones")
    if preview["errors"]:
        raise ValueError(" | ".join(preview["errors"]))
    df = preview["dataframe"]
    errors: list[str] = []
    imported = 0
    for (match_id, team_name), group in df.groupby(["partido_id", "equipo"]):
        try:
            with session.begin_nested():
                match = session.get(Match, int(match_id))
                if not match:
                    raise ValueError(f"partido_id {match_id} no existe")
                team = session.scalar(select(Team).where(Team.name == str(team_name).strip()))
                if not team:
                    raise ValueError(f"equipo '{team_name}' no existe")
                if team.id not in {match.home_team_id, match.away_team_id}:
                    raise ValueError("el equipo no participa en el partido")
                rows = []
                for _, row in group.iterrows():
                    player_name = str(row.get("jugador", "")).strip()
                    candidates = repo.find_player_candidates(session, player_name)
                    if len(candidates) > 1:
                        raise ValueError(f"'{player_name}' coincide con varios jugadores. Resuelve el duplicado antes de importar.")
                    player = repo.find_or_create_player(session, player_name, primary_position=str(row.get("posicion", "")).strip() or None, actor_id=actor_id)
                    repo.assign_player_to_roster(session, team.id, match.season_id, player.id, safe_int(row.get("dorsal")), actor_id)
                    starter_raw = str(row.get("titular", "si")).strip().lower()
                    captain_raw = str(row.get("capitan", "no")).strip().lower()
                    rows.append({
                        "selected": True,
                        "player_id": player.id,
                        "shirt_number": safe_int(row.get("dorsal")),
                        "starter": starter_raw in {"si", "sí", "true", "1", "x"},
                        "position": str(row.get("posicion", "")).strip() or None,
                        "minute_in": safe_int(row.get("minuto_entrada"), 0) or 0,
                        "minute_out": safe_int(row.get("minuto_salida"), 90) or 90,
                        "captain": captain_raw in {"si", "sí", "true", "1", "x"},
                    })
                repo.replace_participations(session, match.id, team.id, rows, actor_id)
                imported += len(rows)
        except Exception as exc:
            errors.append(f"Partido {match_id} / {team_name}: {exc}")
    return {"imported": imported, "errors": errors, "warnings": preview["warnings"]}


def template_workbook() -> bytes:
    polished_template = BASE_DIR / "templates" / "plantilla_importacion_postmatch_scout_2_0.xlsx"
    if polished_template.exists():
        return polished_template.read_bytes()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([{
            "equipo": "FC Barcelona", "temporada": "2026/27", "dorsal": 23,
            "jugador": "Jules Koundé", "posicion": "LD", "fecha_nacimiento": "1998-11-12", "nacionalidad": "Francia",
        }], columns=PLAYER_COLUMNS).to_excel(writer, sheet_name="plantillas", index=False)
        pd.DataFrame([{
            "partido_id": 1, "equipo": "FC Barcelona", "dorsal": 23, "jugador": "Jules Koundé",
            "posicion": "LD", "titular": "Sí", "minuto_entrada": 0, "minuto_salida": 90, "capitan": "No",
        }], columns=LINEUP_COLUMNS).to_excel(writer, sheet_name="alineaciones", index=False)
        pd.DataFrame([
            {"campo": "titular / capitan", "valores_admitidos": "Sí, No, true, false, 1, 0, x"},
            {"campo": "posicion", "valores_admitidos": "POR, LD, DFC, LI, CAD, CAI, MCD, MC, MP, ED, EI, SD, DC, Otro"},
            {"campo": "formato", "valores_admitidos": "Usa la hoja correspondiente o exporta como CSV UTF-8 con coma o punto y coma"},
        ]).to_excel(writer, sheet_name="instrucciones", index=False)
    return output.getvalue()
