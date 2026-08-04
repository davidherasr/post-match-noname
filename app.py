from __future__ import annotations

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

apply_global_styles(
    app_settings.get("primary_color") or "#B91C1C",
    app_settings.get("secondary_color") or "#111827",
)


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
              <div class="pm-page-subtitle">Informes postpartido y seguimiento de jugadores · Versión {APP_VERSION}</div>
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

ROLE_NAVIGATION: dict[str, list[tuple[str, str]]] = {
    "reporter": [
        ("Mi panel", "dashboard"),
        ("Hacer informe", "report_work"),
        ("Mis informes", "report_archive"),
        ("Jugadores", "players"),
    ],
    "director": [
        ("Panel de dirección", "dashboard"),
        ("Revisar y analizar", "director"),
        ("Informes", "report_archive"),
        ("Jugadores", "players"),
    ],
    "admin": [
        ("Panel de administración", "dashboard"),
        ("Partidos", "matches"),
        ("Base de datos", "catalog"),
        ("Informes", "report_archive"),
        ("Jugadores", "players"),
        ("Dirección deportiva", "director"),
        ("Administración", "admin"),
    ],
}

navigation_items = ROLE_NAVIGATION.get(user["role"], ROLE_NAVIGATION["reporter"])
labels = [label for label, _ in navigation_items]
route_by_label = dict(navigation_items)
nav_key = "main_navigation"
if st.session_state.get(nav_key) not in labels:
    st.session_state[nav_key] = labels[0]

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
    selected_label = st.radio("Navegación", labels, label_visibility="collapsed", key=nav_key)
    st.divider()
    if st.button("Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()
    if settings.demo_mode:
        st.warning("DEMO: base SQLite local")

route = route_by_label[selected_label]
if route == "dashboard":
    from pages.dashboard import render
    render(user)
elif route == "report_work":
    from pages.reports import render
    render(user, mode="work")
elif route == "report_archive":
    from pages.reports import render
    render(user, mode="archive")
elif route == "players":
    from pages.players import render
    render(user)
elif route == "director":
    from pages.director import render
    render(user)
elif route == "matches":
    from pages.matches import render
    render(user)
elif route == "catalog":
    from pages.catalog import render
    render(user)
elif route == "admin":
    from pages.admin import render
    render(user)
else:
    from pages.dashboard import render
    render(user)
