from __future__ import annotations

STATUS_ICON = {
    "ready": "🟢",
    "pending": "🟠",
    "action": "🔴",
    "closed": "⚪",
}

PLAYER_STATES = ["Observado", "Interesante", "Seguimiento", "Prioritario", "Descartado"]
NEED_STATES = ["Alta", "Media", "Baja", "Cubierta", "No prioritaria"]


def normalize_player_state(value: str | None) -> str:
    raw = (value or "").strip().casefold()
    mapping = {
        "base": "Observado",
        "candidate": "Observado",
        "observado": "Observado",
        "interesante": "Interesante",
        "jugador interesante": "Interesante",
        "seguimiento": "Seguimiento",
        "seguimiento recomendado": "Seguimiento",
        "prioridad de seguimiento": "Prioritario",
        "prioritario": "Prioritario",
        "approved": "Prioritario",
        "descartado": "Descartado",
        "discarded": "Descartado",
    }
    return mapping.get(raw, value if value in PLAYER_STATES else "Sin decisión")


def normalize_need_state(value: str | None) -> str:
    raw = (value or "").strip().casefold()
    if raw in {"alta", "high", "urgente", "abierta"}:
        return "Alta"
    if raw in {"media", "medium"}:
        return "Media"
    if raw in {"baja", "low"}:
        return "Baja"
    if raw in {"cubierta", "cubierto", "cerrada", "closed"}:
        return "Cubierta"
    if raw in {"no prioritaria", "no prioritario", "sin prioridad", "archivada", "archivado"}:
        return "No prioritaria"
    return "Media"


def status_badge(kind: str, label: str) -> str:
    return f"{STATUS_ICON.get(kind, '⚪')} {label}"
