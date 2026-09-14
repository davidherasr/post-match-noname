from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormationSlot:
    code: str
    label: str


# Deliberately pragmatic: these are lineup-entry templates, not tactical doctrine.
# The aim is to prefill eleven sensible slots so administration only has to choose names.
FORMATION_SLOTS: dict[str, list[FormationSlot]] = {
    "4-3-3": [
        FormationSlot("POR", "Portero"), FormationSlot("LD", "Lateral derecho"),
        FormationSlot("DFC", "Central derecho"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("LI", "Lateral izquierdo"), FormationSlot("MCD", "Mediocentro"),
        FormationSlot("MC", "Interior derecho"), FormationSlot("MC", "Interior izquierdo"),
        FormationSlot("ED", "Extremo derecho"), FormationSlot("DC", "Delantero centro"),
        FormationSlot("EI", "Extremo izquierdo"),
    ],
    "4-2-3-1": [
        FormationSlot("POR", "Portero"), FormationSlot("LD", "Lateral derecho"),
        FormationSlot("DFC", "Central derecho"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("LI", "Lateral izquierdo"), FormationSlot("MCD", "Mediocentro derecho"),
        FormationSlot("MCD", "Mediocentro izquierdo"), FormationSlot("ED", "Extremo derecho"),
        FormationSlot("MP", "Mediapunta"), FormationSlot("EI", "Extremo izquierdo"),
        FormationSlot("DC", "Delantero centro"),
    ],
    "4-4-2": [
        FormationSlot("POR", "Portero"), FormationSlot("LD", "Lateral derecho"),
        FormationSlot("DFC", "Central derecho"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("LI", "Lateral izquierdo"), FormationSlot("ED", "Banda derecha"),
        FormationSlot("MC", "Mediocentro derecho"), FormationSlot("MC", "Mediocentro izquierdo"),
        FormationSlot("EI", "Banda izquierda"), FormationSlot("DC", "Delantero derecho"),
        FormationSlot("DC", "Delantero izquierdo"),
    ],
    "4-1-4-1": [
        FormationSlot("POR", "Portero"), FormationSlot("LD", "Lateral derecho"),
        FormationSlot("DFC", "Central derecho"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("LI", "Lateral izquierdo"), FormationSlot("MCD", "Pivote"),
        FormationSlot("ED", "Banda derecha"), FormationSlot("MC", "Interior derecho"),
        FormationSlot("MC", "Interior izquierdo"), FormationSlot("EI", "Banda izquierda"),
        FormationSlot("DC", "Delantero centro"),
    ],
    "4-3-1-2": [
        FormationSlot("POR", "Portero"), FormationSlot("LD", "Lateral derecho"),
        FormationSlot("DFC", "Central derecho"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("LI", "Lateral izquierdo"), FormationSlot("MCD", "Pivote"),
        FormationSlot("MC", "Interior derecho"), FormationSlot("MC", "Interior izquierdo"),
        FormationSlot("MP", "Mediapunta"), FormationSlot("DC", "Delantero derecho"),
        FormationSlot("DC", "Delantero izquierdo"),
    ],
    "4-4-1-1": [
        FormationSlot("POR", "Portero"), FormationSlot("LD", "Lateral derecho"),
        FormationSlot("DFC", "Central derecho"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("LI", "Lateral izquierdo"), FormationSlot("ED", "Banda derecha"),
        FormationSlot("MC", "Mediocentro derecho"), FormationSlot("MC", "Mediocentro izquierdo"),
        FormationSlot("EI", "Banda izquierda"), FormationSlot("MP", "Segundo punta"),
        FormationSlot("DC", "Delantero centro"),
    ],
    "3-4-3": [
        FormationSlot("POR", "Portero"), FormationSlot("DFC", "Central derecho"),
        FormationSlot("DFC", "Central"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("CAD", "Carrilero derecho"), FormationSlot("MC", "Mediocentro derecho"),
        FormationSlot("MC", "Mediocentro izquierdo"), FormationSlot("CAI", "Carrilero izquierdo"),
        FormationSlot("ED", "Extremo derecho"), FormationSlot("DC", "Delantero centro"),
        FormationSlot("EI", "Extremo izquierdo"),
    ],
    "3-4-2-1": [
        FormationSlot("POR", "Portero"), FormationSlot("DFC", "Central derecho"),
        FormationSlot("DFC", "Central"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("CAD", "Carrilero derecho"), FormationSlot("MC", "Mediocentro derecho"),
        FormationSlot("MC", "Mediocentro izquierdo"), FormationSlot("CAI", "Carrilero izquierdo"),
        FormationSlot("MP", "Mediapunta derecho"), FormationSlot("MP", "Mediapunta izquierdo"),
        FormationSlot("DC", "Delantero centro"),
    ],
    "3-5-2": [
        FormationSlot("POR", "Portero"), FormationSlot("DFC", "Central derecho"),
        FormationSlot("DFC", "Central"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("CAD", "Carrilero derecho"), FormationSlot("MCD", "Pivote"),
        FormationSlot("MC", "Interior derecho"), FormationSlot("MC", "Interior izquierdo"),
        FormationSlot("CAI", "Carrilero izquierdo"), FormationSlot("DC", "Delantero derecho"),
        FormationSlot("DC", "Delantero izquierdo"),
    ],
    "3-1-4-2": [
        FormationSlot("POR", "Portero"), FormationSlot("DFC", "Central derecho"),
        FormationSlot("DFC", "Central"), FormationSlot("DFC", "Central izquierdo"),
        FormationSlot("MCD", "Pivote"), FormationSlot("CAD", "Carrilero derecho"),
        FormationSlot("MC", "Interior derecho"), FormationSlot("MC", "Interior izquierdo"),
        FormationSlot("CAI", "Carrilero izquierdo"), FormationSlot("DC", "Delantero derecho"),
        FormationSlot("DC", "Delantero izquierdo"),
    ],
    "5-4-1": [
        FormationSlot("POR", "Portero"), FormationSlot("CAD", "Carrilero derecho"),
        FormationSlot("DFC", "Central derecho"), FormationSlot("DFC", "Central"),
        FormationSlot("DFC", "Central izquierdo"), FormationSlot("CAI", "Carrilero izquierdo"),
        FormationSlot("ED", "Banda derecha"), FormationSlot("MC", "Mediocentro derecho"),
        FormationSlot("MC", "Mediocentro izquierdo"), FormationSlot("EI", "Banda izquierda"),
        FormationSlot("DC", "Delantero centro"),
    ],
    "5-3-2": [
        FormationSlot("POR", "Portero"), FormationSlot("CAD", "Carrilero derecho"),
        FormationSlot("DFC", "Central derecho"), FormationSlot("DFC", "Central"),
        FormationSlot("DFC", "Central izquierdo"), FormationSlot("CAI", "Carrilero izquierdo"),
        FormationSlot("MCD", "Pivote"), FormationSlot("MC", "Interior derecho"),
        FormationSlot("MC", "Interior izquierdo"), FormationSlot("DC", "Delantero derecho"),
        FormationSlot("DC", "Delantero izquierdo"),
    ],
}


def slots_for(formation: str | None) -> list[FormationSlot]:
    """Return a copy-safe XI template for a known formation."""
    return list(FORMATION_SLOTS.get((formation or "").strip(), []))


def position_codes_for(formation: str | None) -> list[str]:
    return [slot.code for slot in slots_for(formation)]


def available_lineup_player_ids(roster_ids: list[int], slot_values: list[int | None], slot_index: int) -> list[int]:
    """Return roster ids still available for one XI slot.

    A player selected in another position is hidden, while the current slot keeps
    its own value so Streamlit can preserve the selection safely across reruns.
    """
    current = slot_values[slot_index] if 0 <= slot_index < len(slot_values) else None
    used_elsewhere = {
        pid for idx, pid in enumerate(slot_values)
        if idx != slot_index and pid is not None
    }
    return [pid for pid in roster_ids if pid not in used_elsewhere or pid == current]
