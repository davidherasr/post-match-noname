from __future__ import annotations

import re
from dataclasses import dataclass

from core.constants import POSITIONS


@dataclass(frozen=True)
class FederationRosterRow:
    shirt_number: int | None
    name: str
    position: str | None = None


_NUMBERED = re.compile(r"^\s*(\d{1,3})\s*(?:[.):-]|\s)\s*(.+?)\s*$")


def parse_federation_roster(text: str) -> list[FederationRosterRow]:
    """Parse a federation squad pasted as one player per line.

    Accepted examples::

        1;Ángel Pérez;POR
        7 Mario López
        10 - Carlos Gómez
        Pedro García

    A position is optional and only stored when it is a known No Name position
    code. Empty/duplicate lines are ignored. The parser never fabricates a
    shirt number or a position.
    """
    rows: list[FederationRosterRow] = []
    seen: set[tuple[int | None, str]] = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        shirt: int | None = None
        position: str | None = None
        name = ""
        if ";" in line:
            parts = [p.strip() for p in line.split(";")]
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
        key = (shirt, name.casefold())
        if key in seen:
            continue
        seen.add(key)
        rows.append(FederationRosterRow(shirt, name, position))
    return rows
