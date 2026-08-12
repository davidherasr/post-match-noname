from __future__ import annotations

from collections import OrderedDict

# Roles are intentionally club-model labels, not Football Manager roles. They give
# Dirección Deportiva a consistent vocabulary while still allowing a free-text note.
MODEL_ROLES: dict[str, list[str]] = {
    "POR": ["Portero dominador", "Portero de área", "Portero con juego de pies"],
    "LD": ["Lateral profundo", "Lateral equilibrado", "Lateral interior"],
    "LI": ["Lateral profundo", "Lateral equilibrado", "Lateral interior"],
    "CAD": ["Carrilero profundo", "Carrilero equilibrado"],
    "CAI": ["Carrilero profundo", "Carrilero equilibrado"],
    "DFC": ["Central dominante", "Central corrector", "Central iniciador"],
    "MCD": ["Pivote posicional", "Recuperador", "Organizador bajo"],
    "MC": ["Interior", "Box to box", "Organizador", "Mediocentro equilibrado"],
    "MP": ["Mediapunta", "Llegador", "Organizador entre líneas"],
    "ED": ["Extremo abierto", "Extremo interior", "Atacante de banda"],
    "EI": ["Extremo abierto", "Extremo interior", "Atacante de banda"],
    "SD": ["Segundo punta", "Mediapunta móvil"],
    "DC": ["Referencia", "Atacante al espacio", "Delantero asociativo", "Finalizador"],
    "Otro": ["Rol por definir"],
}

# The advanced scout sheet is optional and deliberately position-aware. Zero means
# "sin valorar" so the reviewer never has to invent information they did not see.
ATTRIBUTE_SETS: dict[str, OrderedDict[str, list[str]]] = {
    "POR": OrderedDict({
        "Técnico": ["Juego de pies", "Blocaje", "Desvíos", "1v1", "Centros"],
        "Táctico": ["Posicionamiento", "Dominio del área", "Lectura del espacio", "Salida"],
        "Físico": ["Agilidad", "Explosividad", "Juego aéreo", "Alcance"],
        "Mental": ["Concentración", "Valentía", "Comunicación", "Personalidad"],
    }),
    "DEF": OrderedDict({
        "Técnico": ["Primer toque", "Pase", "Conducción", "Entrada", "Juego aéreo"],
        "Táctico": ["Posicionamiento", "Defensa hacia delante", "Coberturas", "Defensa del área", "Salida de balón"],
        "Físico": ["Velocidad", "Aceleración", "Fuerza", "Agilidad", "Resistencia"],
        "Mental": ["Concentración", "Competitividad", "Valentía", "Trabajo", "Comunicación"],
    }),
    "MID": OrderedDict({
        "Técnico": ["Primer toque", "Pase", "Conducción", "Giro", "Último pase"],
        "Táctico": ["Posicionamiento", "Lectura", "Toma de decisiones", "Apoyos", "Llegada"],
        "Físico": ["Aceleración", "Resistencia", "Fuerza", "Agilidad", "Cambio de ritmo"],
        "Mental": ["Concentración", "Competitividad", "Trabajo", "Personalidad", "Ritmo de juego"],
    }),
    "ATT": OrderedDict({
        "Técnico": ["Primer toque", "Conducción", "1v1", "Finalización", "Centros"],
        "Táctico": ["Desmarques", "Ocupación de área", "Juego entre líneas", "Presión", "Toma de decisiones"],
        "Físico": ["Velocidad", "Aceleración", "Fuerza", "Agilidad", "Potencia"],
        "Mental": ["Competitividad", "Confianza", "Trabajo", "Personalidad", "Agresividad ofensiva"],
    }),
}


def attribute_group(position: str | None) -> str:
    pos = (position or "Otro").upper()
    if pos == "POR":
        return "POR"
    if pos in {"LD", "LI", "DFC", "CAD", "CAI"}:
        return "DEF"
    if pos in {"MCD", "MC", "MP"}:
        return "MID"
    if pos in {"ED", "EI", "SD", "DC"}:
        return "ATT"
    return "MID"


def roles_for(position: str | None) -> list[str]:
    return MODEL_ROLES.get((position or "Otro").upper(), MODEL_ROLES["Otro"])


def attributes_for(position: str | None):
    return ATTRIBUTE_SETS[attribute_group(position)]
