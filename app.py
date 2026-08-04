from __future__ import annotations

import base64

import streamlit as st

from core.auth import current_user, login, logout
from core.config import APP_NAME, APP_VERSION, settings, validate_production_settings
from core.constants import ROLES
from core.database import init_db, session_scope
from core.utils import safe_html
from repositories import scouting as repo
from services.bootstrap import bootstrap_application
from ui.styles import apply_global_styles

validate_production_settings()

st.set_page_config(
    page_title=f"{APP_NAME} {APP_VERSION}",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
bootstrap_application()

with session_scope() as session:
    app_settings = repo.get_all_settings(session)

apply_global_styles(app_settings.get("primary_color") or "#B91C1C", app_settings.get("secondary_color") or "#111827")


def render_login() -> None:
    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        st.markdown("<br/><br/>", unsafe_allow_html=True)
        if app_settings.get("logo_b64"):
            mime = safe_html(app_settings.get("logo_mime") or "image/png")
            st.markdown(
                f'<div style="text-align:center"><img src="data:{mime};base64,{app_settings["logo_b64"]}" style="max-height:90px;max-width:150px"></div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f"""
            <div class="pm-card" style="padding:28px">
              <div class="pm-kicker">Aplicación interna</div>
              <div class="pm-page-title" style="font-size:2.25rem">{safe_html(app_settings.get('club_name') or APP_NAME)}</div>
              <div class="pm-page-subtitle">Informes postpartido, consenso y seguimiento · Versión {APP_VERSION}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            email = st.text_input("Correo", placeholder="nombre@club.com")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if submitted:
            if login(email, password):
                st.rerun()
            else:
                st.error("Acceso no válido. Tras varios intentos la cuenta se bloquea temporalmente.")
        if settings.demo_mode:
            st.info(
                f"Modo demostración. Administrador: {settings.bootstrap_admin_email} / {settings.bootstrap_admin_password}. "
                "Informador: informador@postmatch.local / DemoReporter2026!"
            )


user = current_user()
if not user:
    render_login()
    st.stop()

if user.get("must_change_password"):
    st.warning("Debes cambiar la contraseña inicial antes de utilizar la aplicación.")
    with st.form("mandatory_password_change"):
        current = st.text_input("Contraseña actual", type="password")
        new = st.text_input("Nueva contraseña", type="password")
        repeat = st.text_input("Repite la nueva contraseña", type="password")
        change = st.form_submit_button("Cambiar contraseña", type="primary")
    if change:
        if new != repeat:
            st.error("Las nuevas contraseñas no coinciden.")
        else:
            try:
                with session_scope() as session:
                    repo.change_own_password(session, user["id"], current, new)
                logout()
                st.success("Contraseña actualizada. Vuelve a iniciar sesión.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.stop()

with st.sidebar:
    st.markdown(
        f"""
        <div class="pm-brand">
          <div class="pm-brand-title">{safe_html(app_settings.get('club_name') or APP_NAME)}</div>
          <div class="pm-brand-version">Versión {APP_VERSION} · {safe_html(ROLES.get(user['role'], user['role']))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(user["full_name"])
    navigation = ["Inicio", "Informes", "Jugadores"]
    if user["role"] in {"admin", "director"}:
        navigation.append("Dirección deportiva")
    if user["role"] == "admin":
        navigation.extend(["Partidos", "Base de datos", "Administración"])
    page = st.radio("Navegación", navigation, label_visibility="collapsed")
    st.divider()
    if st.button("Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()
    if settings.demo_mode:
        st.warning("DEMO: base SQLite local")

if page == "Inicio":
    from pages.dashboard import render
elif page == "Informes":
    from pages.reports import render
elif page == "Jugadores":
    from pages.players import render
elif page == "Dirección deportiva":
    from pages.director import render
elif page == "Partidos":
    from pages.matches import render
elif page == "Base de datos":
    from pages.catalog import render
elif page == "Administración":
    from pages.admin import render
else:
    from pages.dashboard import render

render(user)
