from __future__ import annotations

import streamlit as st

_PENDING_NAVIGATION_KEY = "_pending_main_navigation"


def request_navigation(label: str) -> None:
    """Request a sidebar navigation change for the next Streamlit rerun.

    `main_navigation` is the key of the sidebar radio. Streamlit forbids writing
    to a widget-backed session-state key after that widget has been instantiated
    in the current run. Views therefore write to a separate pending key and
    rerun; app.py consumes it before constructing the radio.
    """
    st.session_state[_PENDING_NAVIGATION_KEY] = str(label)


def apply_pending_navigation(labels: list[str], *, nav_key: str = "main_navigation") -> None:
    """Apply a requested navigation target before the radio is instantiated."""
    pending = st.session_state.pop(_PENDING_NAVIGATION_KEY, None)
    if pending in labels:
        st.session_state[nav_key] = pending
    elif st.session_state.get(nav_key) not in labels:
        st.session_state[nav_key] = labels[0]
