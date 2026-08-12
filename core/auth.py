from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from core.database import session_scope
from repositories import scouting as repo

SESSION_USER_KEY = "postmatch_user"
SESSION_REVALIDATED_KEY = "postmatch_user_revalidated_at"
SESSION_REVALIDATE_SECONDS = 90


def _utc_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def current_user(revalidate: bool = True, force: bool = False) -> dict | None:
    """Return the logged-in user without hitting PostgreSQL on every Streamlit rerun.

    The session is revalidated periodically, while write operations keep enforcing
    authorization again in the repository layer. This preserves security without
    paying a network roundtrip for every slider, radio or navigation click.
    """
    cached = st.session_state.get(SESSION_USER_KEY)
    if not cached or not revalidate:
        return cached

    last = float(st.session_state.get(SESSION_REVALIDATED_KEY, 0.0) or 0.0)
    now = _utc_ts()
    if not force and (now - last) < SESSION_REVALIDATE_SECONDS:
        return cached

    with session_scope() as session:
        user = repo.get_user(session, int(cached["id"]))
        if not user or not user.active or user.session_revision != cached.get("session_revision"):
            st.session_state.pop(SESSION_USER_KEY, None)
            st.session_state.pop(SESSION_REVALIDATED_KEY, None)
            return None
        cached.update({
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "must_change_password": user.must_change_password,
            "session_revision": user.session_revision,
        })
        st.session_state[SESSION_REVALIDATED_KEY] = now
    return cached


def login(email: str, password: str) -> bool:
    with session_scope() as session:
        user = repo.authenticate(session, email, password)
        if not user:
            return False
        st.session_state[SESSION_USER_KEY] = {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "must_change_password": user.must_change_password,
            "session_revision": user.session_revision,
        }
        st.session_state[SESSION_REVALIDATED_KEY] = _utc_ts()
        return True


def logout() -> None:
    st.session_state.pop(SESSION_USER_KEY, None)
    st.session_state.pop(SESSION_REVALIDATED_KEY, None)
    # Report workspaces contain club data and must not leak between logins.
    for key in list(st.session_state):
        if str(key).startswith("report_workspace_") or str(key).startswith("eval_form_"):
            st.session_state.pop(key, None)


def require_role(*roles: str) -> bool:
    user = current_user()
    return bool(user and user.get("role") in roles)
