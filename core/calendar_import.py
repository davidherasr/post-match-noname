from __future__ import annotations

import re
from datetime import date, datetime, time

CALENDAR_PARSER_VERSION = "3.7.0"

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _parse_date(value: str, default_year: int | None = None) -> date:
    value = value.strip()
    if re.search(r"\d\s*[/.-]\s*\d{1,2}/\d{1,2}/\d{2,4}", value) and value.count("/") >= 3:
        raise ValueError(
            f"Fecha no reconocida: {value}. En 3.7 no uses rangos: indica solo la fecha de jornada publicada (por ejemplo 13/09/2026)."
        )
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-záéíóúñ]+)(?:\s+(\d{4}))?", value.lower())
    if m and m.group(2) in SPANISH_MONTHS:
        year = int(m.group(3) or default_year or date.today().year)
        return date(year, SPANISH_MONTHS[m.group(2)], int(m.group(1)))
    raise ValueError(f"Fecha no reconocida: {value}")


def _parse_time(value: str) -> time | None:
    value = value.strip()
    if not value or value.lower() in {"pendiente", "sin hora", "-"}:
        return None
    for fmt in ("%H:%M", "%H.%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            pass
    raise ValueError(f"Hora no reconocida: {value}")


def parse_calendar_text(text: str, *, default_year: int | None = None) -> tuple[list[dict], list[str]]:
    """Parse a semicolon-separated fixture list.

    Normal 3.7 format (recommended):
      1;13/09/2026;La Cistérniga;C.D. Noname

    The date is the federation/reference date for the round and is explicitly
    *provisional*. It does not become the definitive match date until an admin
    confirms both date and kickoff time.

    Optional already-confirmed fixture:
      1;12/09/2026;18:00;La Cistérniga;C.D. Noname
    """
    rows: list[dict] = []
    errors: list[str] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = [p.strip() for p in raw.split(";")]
        if len(parts) < 4:
            errors.append(f"Línea {line_no}: se esperan al menos 4 campos separados por ;")
            continue
        try:
            round_name = parts[0] if not parts[0].isdigit() else f"Jornada {parts[0]}"
            reference_date = _parse_date(parts[1], default_year)
            kickoff_time = None
            if len(parts) >= 5 and re.fullmatch(r"\d{1,2}[:.]\d{2}|pendiente|sin hora|-", parts[2], re.I):
                kickoff_time = _parse_time(parts[2])
                home, away = parts[3], parts[4]
                venue = parts[5] if len(parts) > 5 else None
            else:
                home, away = parts[2], parts[3]
                venue = parts[4] if len(parts) > 4 else None
            if not home or not away or home.casefold() == away.casefold():
                raise ValueError("local y visitante deben ser distintos")
            kickoff_at = datetime.combine(reference_date, kickoff_time) if kickoff_time else None
            rows.append({
                "round_name": round_name,
                "window_start": None,
                "window_end": None,
                "match_date": reference_date,
                "kickoff_at": kickoff_at,
                "schedule_status": "confirmed" if kickoff_at else "provisional",
                "home_team": home,
                "away_team": away,
                "venue": venue or None,
            })
        except Exception as exc:
            errors.append(f"Línea {line_no}: {exc}")
    return rows, errors
