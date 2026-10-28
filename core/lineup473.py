"""Strict, human-readable two-team XI import for the publishing screen.

This is NOT the legacy loose federation parser: publication requires 11
identified starters with explicit match-specific positions for each side.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from core.constants import POSITIONS
from core.utils import normalize_name


@dataclass(frozen=True)
class XIPlayer:
    shirt: int
    name: str
    position: str | None
    starter: bool = True


ALLOWED = set(POSITIONS) - {"Otro"}
EXPLANATIONS = {"MCD": "Mediocentro derecho", "MCI": "Mediocentro izquierdo",
    "DCD": "Central derecho", "DCI": "Central izquierdo", "DCC": "Central central",
    "MCC": "Mediocentro central", "MC": "Mediocentro único"}


def parse_xi(text: str, *, team_name: str = "") -> list[XIPlayer]:
    """Parse dorsal;nombre;posicion and explicit optional TITULARES/SUPLENTES.

    Without a heading rows are understood as starters because this importer
    belongs exclusively to the official match publishing form. No implicit
    position inference from formation or alphabetical order.
    """
    if not isinstance(text, str) or len(text) > 18000:
        raise ValueError("Texto vacío o demasiado largo para una alineación.")
    result: list[XIPlayer] = []
    role = True
    header = normalize_name(team_name)
    for line_number, raw in enumerate(text.splitlines(), start=1):
        raw = raw.strip().strip("\ufeff")
        if not raw or raw.startswith("#"):
            continue
        token = normalize_name(raw.rstrip(":"))
        if token in {"titulares", "xi", "once titular"}:
            role = True;continue
        if token in {"suplentes", "banquillo"}:
            role = False;continue
        if header and (token==header or (len(token)>3 and header.endswith(' '+token)) or
                       (token in {'noname','cd noname'} and 'noname' in header)):
            continue
        parts = [v.strip() for v in raw.split(";")]
        if len(parts) not in {2,3,4} or (len(parts)==2 and role):
            raise ValueError(f"Línea {line_number}: usa dorsal;nombre;posición. Ejemplo: 2;Yago;LD.")
        shirt_text,name = parts[:2]
        position=parts[2] if len(parts)>2 else '' 
        if not shirt_text.isdigit() or not 1 <= int(shirt_text) <= 99:
            raise ValueError(f"Línea {line_number}: dorsal incorrecto (1–99).")
        if len(name) < 2 or len(name) > 180 or not re.search(r"\w", name):
            raise ValueError(f"Línea {line_number}: introduce un nombre reconocible.")
        pos=position.upper() if position else None
        starter=role
        if len(parts)==4:
            if parts[3].casefold() in {"t", "titular", "starter"}:starter=True
            elif parts[3].casefold() in {"s", "suplente", "sub"}:starter=False
            else:raise ValueError(f"Línea {line_number}: la cuarta columna debe ser T o S.")
        if (starter and pos not in ALLOWED) or (not starter and pos is not None and pos not in ALLOWED):
            raise ValueError(f"Línea {line_number}: posición '{position}' no reconocida. Usa POR, LD, DCD, DCI, MCD, MCI, etc.")
        result.append(XIPlayer(int(shirt_text), " ".join(name.split()), pos, starter))
    starters=[r for r in result if r.starter]
    if len(starters)!=11:
        raise ValueError(f"Se necesitan 11 titulares; has introducido {len(starters)}.")
    if len(result)>30:
        raise ValueError("Máximo 30 jugadores entre titulares y suplentes.")
    if len({r.shirt for r in result})!=len(result):
        raise ValueError("Hay dorsales duplicados dentro del equipo.")
    if len({normalize_name(r.name) for r in result})!=len(result):
        raise ValueError("Hay nombres repetidos dentro del equipo.")
    if len([r for r in starters if r.position=='POR'])!=1:
        raise ValueError("Los once titulares deben incluir exactamente un portero (POR).")
    return result
