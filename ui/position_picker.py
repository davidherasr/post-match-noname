"""Interactive positional pitch for an incomplete XI (no fabricated player identities)."""
from __future__ import annotations
import streamlit as st
from core.formations import slots_for
from ui.match_study import _FORMATION_COORDS


def pick_position(formation: str, *, key: str) -> tuple[int, str] | None:
    """Select one of eleven positional slots. Repeated codes remain distinct slots."""
    slots = slots_for(formation)
    coords = _FORMATION_COORDS.get(formation)
    if not slots or not coords or len(slots) != len(coords):
        st.caption("No existe un campograma para esta estructura.")
        return None
    st.caption(f"Campograma {formation} · pulsa la posición observada")
    selection = st.session_state.get(key)
    # Invert pitch to read from attackers at top to goalkeeper at bottom.
    rows = {0: [], 1: [], 2: [], 3: [], 4: []}
    for i, (_, (x, y)) in enumerate(zip(slots, coords)):
        band = max(0, min(4, round((y - 12) / 19)))
        rows[band].append((i, x))
    for band in range(5):
        cols = st.columns(5, gap="small")
        used = set()
        for i, x in rows[band]:
            index = min(range(5), key=lambda k: (abs(12.5 + k*18.75 - x), k in used))
            if index in used:
                index = min((k for k in range(5) if k not in used), key=lambda k: abs(12.5 + k*18.75 - x))
            used.add(index)
            slot = slots[i]
            if cols[index].button(f"{slot.code}", key=f"{key}_slot_{i}",
                                  type="primary" if i == selection else "secondary",
                                  use_container_width=True, help=f"{slot.label} · puesto {i+1}"):
                st.session_state[key] = None if selection == i else i
                selection = st.session_state[key]
    if selection is None or selection >= len(slots):
        return None
    st.caption(f"Seleccionado: {slots[selection].label} · posición {slots[selection].code}")
    return int(selection), slots[selection].code
