from __future__ import annotations

import re
from dataclasses import dataclass

from core.constants import POSITIONS


@dataclass(frozen=True)
class FederationRosterRow:
    shirt_number: int | None
    name: str
    position: str | None = None
    # Match-specific role when the pasted federation list explicitly separates it.
    # None means "season roster only": never infer starter/substitute from order.
    squad_role: str | None = None  # "starter" | "substitute" | None


_NUMBERED = re.compile(r"^\s*(\d{1,3})\s*(?:[.):-]|\s)\s*(.+?)\s*$")
_SECTION_STARTERS = {"titulares", "titular", "once titular", "xi", "xi titular", "iniciales"}
_SECTION_SUBS = {"suplentes", "suplente", "banquillo", "reservas", "sustitutos"}
_SECTION_ROSTER = {"plantilla", "convocados", "convocatoria", "otros"}


def _section_role(line: str) -> str | None | object:
    """Return section role; sentinel False-like object means not a heading."""
    normalized = re.sub(r"[^a-záéíóúüñ0-9 ]+", " ", line.casefold())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized in _SECTION_STARTERS:
        return "starter"
    if normalized in _SECTION_SUBS:
        return "substitute"
    if normalized in _SECTION_ROSTER:
        return None
    return _NOT_HEADING


_NOT_HEADING = object()


def parse_federation_roster(text: str) -> list[FederationRosterRow]:
    """Parse a federation list without inventing match status.

    Accepted examples::

        TITULARES
        1;Ángel Pérez;POR
        7 Mario López
        SUPLENTES
        12;Carlos Gómez;POR

        T;1;Ángel Pérez;POR
        S;12;Carlos Gómez;POR

        10 - Carlos Gómez
        Pedro García

    Headings ``TITULARES`` / ``SUPLENTES`` (or T/S prefixes) are optional. When
    absent, rows update only the season roster. The parser never assumes that the
    first eleven lines are starters.
    """
    rows: list[FederationRosterRow] = []
    seen: set[tuple[int | None, str, str | None]] = set()
    current_role: str | None = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = _section_role(line.rstrip(":"))
        if heading is not _NOT_HEADING:
            current_role = heading
            continue

        shirt: int | None = None
        position: str | None = None
        role = current_role
        name = ""
        if ";" in line:
            parts = [p.strip() for p in line.split(";")]
            # Optional explicit T/S prefix overrides the current section.
            prefix = parts[0].casefold() if parts else ""
            if prefix in {"t", "tit", "titular", "starter"}:
                role = "starter"
                parts = parts[1:]
            elif prefix in {"s", "sup", "suplente", "sub", "substitute"}:
                role = "substitute"
                parts = parts[1:]
            first = parts[0] if parts else ""
            if first.isdigit():
                shirt = int(first)
                name = parts[1] if len(parts) > 1 else ""
                position = parts[2].upper() if len(parts) > 2 and parts[2].strip() else None
            else:
                name = first
                position = parts[1].upper() if len(parts) > 1 and parts[1].strip() else None
        else:
            match = _NUMBERED.match(line)
            if match:
                shirt = int(match.group(1))
                name = match.group(2).strip()
            else:
                name = line
        name = re.sub(r"\s+", " ", name).strip(" -·\t")
        if not name:
            continue
        if position not in POSITIONS:
            position = None
        key = (shirt, name.casefold(), role)
        if key in seen:
            continue
        seen.add(key)
        rows.append(FederationRosterRow(shirt, name, position, role))
    return rows
