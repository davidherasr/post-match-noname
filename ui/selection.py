"""Responsive, Spanish-only selection for a small group of eligible users."""
from __future__ import annotations

import streamlit as st


def _set_checks(prefix: str, ids: list[int], selected: bool) -> None:
    """Button callbacks run before widgets are rendered on the next Streamlit rerun."""
    for ident in ids:
        st.session_state[f'{prefix}_{ident}'] = selected


def reporter_checkboxes(options: dict[int, str], defaults: list[int], *, key_prefix: str) -> list[int]:
    """No form buffering, no English 'Select all', no visible implementation IDs."""
    ids = list(options)
    initial = set(defaults)
    for ident in ids:
        key = f'{key_prefix}_{ident}'
        if key not in st.session_state:
            st.session_state[key] = ident in initial
    a, b = st.columns(2)
    a.button('Seleccionar todos', key=f'{key_prefix}_all',
             on_click=_set_checks, args=(key_prefix, ids, True), use_container_width=True)
    b.button('Quitar selección', key=f'{key_prefix}_none',
             on_click=_set_checks, args=(key_prefix, ids, False), use_container_width=True)
    st.markdown('**Informadores**')
    for ident in ids:
        st.checkbox(options[ident], key=f'{key_prefix}_{ident}')
    selected = [ident for ident in ids if st.session_state.get(f'{key_prefix}_{ident}', False)]
    st.caption(f'{len(selected)} de {len(ids)} Informadores seleccionados.')
    return selected
