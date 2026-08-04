from __future__ import annotations

import streamlit as st

from core.database import session_scope
from repositories import scouting as repo

SESSION_USER_KEY = "postmatch_user"


def current_user(revalidate: bool = True) -> dict | None:
    cached = st.session_state.get(SESSION_USER_KEY)
    if not cached or not revalidate:
        return cached
    with session_scope() as session:
        user = repo.get_user(session, int(cached["id"]))
        if not user or not user.active or user.session_revision != cached.get("session_revision"):
            st.session_state.pop(SESSION_USER_KEY, None)
            return None
        cached.update({
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "must_change_password": user.must_change_password,
            "session_revision": user.session_revision,
        })
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
        return True


def logout() -> None:
    st.session_state.pop(SESSION_USER_KEY, None)


def require_role(*roles: str) -> bool:
    user = current_user()
    return bool(user and user.get("role") in roles)
