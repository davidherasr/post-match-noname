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

st.set_option("client.showSidebarNavigation", False)

st.set_page_config(
    page_title=f"{APP_NAME} {APP_VERSION}",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
bootstrap_application()

@st.cache_data(ttl=180, show_spinner=False)
def _load_app_settings() -> dict:
    with session_scope() as session:
        return repo.get_all_settings(session)

app_settings = _load_app_settings()

apply_global_styles(
    app_settings.get("primary_color") or "#B91C1C",
    app_settings.get("secondary_color") or "#111827",
)


def _render_reports_route(user: dict, mode: str) -> None:
    """Render the reports page and fail clearly when deployment files are mixed."""
    from pages import reports as reports_page

    expected_api = "3.6.0"
    deployed_api = getattr(reports_page, "REPORTS_PAGE_API_VERSION", None)
    if deployed_api != expected_api:
        st.error("La aplicación tiene archivos mezclados de versiones distintas.")
        st.markdown(
            "`app.py` es de No Name PostMatch 3.6, pero `pages/reports.py` no corresponde a esta versión. "
            "Sustituye **todo el contenido del repositorio** por el paquete 3.6 y reinicia la aplicación."
        )
        st.code(
            f"API esperada: {expected_api}\nAPI encontrada: {deployed_api or 'incompatible'}\n"
            "Archivo que debes comprobar: pages/reports.py",
            language="text",
        )
        st.stop()

    renderer_name = "render_archive" if mode == "archive" else "render_work"
    renderer = getattr(reports_page, renderer_name, None)
    if not callable(renderer):
        st.error(f"No se encuentra la función requerida: pages.reports.{renderer_name}().")
        st.info("Vuelve a subir el paquete completo No Name PostMatch 3.6 y reinicia la aplicación.")
        st.stop()
    renderer(user)


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
            st.info(f"Modo local. Administrador inicial: {settings.bootstrap_admin_email}. No se cargan datos deportivos de ejemplo.")


user = current_user()
if not user:
    # En login no mostramos ni la navegación automática de Streamlit ni un sidebar vacío.
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
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
        ("Inicio", "dashboard"),
        ("Calendario", "calendar"),
        ("Valorar partido", "report_work"),
        ("Mis informes", "report_archive"),
        ("Jugadores", "players"),
        ("Jugadores ojeados", "scouted"),
    ],
    "scout": [
        ("Inicio Scout", "dashboard"),
        ("Calendario de liga", "calendar"),
        ("Misiones", "scout"),
        ("Jugadores ojeados", "scouted"),
        ("Jugadores", "players"),
    ],
    "director": [
        ("Inicio", "dashboard"),
        ("Calendario", "calendar"),
        ("Revisar y decidir", "director"),
        ("Modelo No Name", "model"),
        ("Informes", "report_archive"),
        ("Jugadores", "players"),
        ("Jugadores ojeados", "scouted"),
    ],
    "admin": [
        ("Inicio", "dashboard"),
        ("Calendario", "calendar"),
        ("Nuevo postpartido", "postmatch"),
        ("Partidos", "matches"),
        ("Informes", "report_archive"),
        ("Jugadores", "players"),
        ("Jugadores ojeados", "scouted"),
        ("Dirección deportiva", "director"),
        ("Modelo No Name", "model"),
        ("Scout", "scout"),
        ("Base de datos", "catalog"),
        ("Administración", "admin"),
    ],
}

available_roles = [r for r in (user.get("roles") or [user.get("role")]) if r in ROLE_NAVIGATION]
if not available_roles:
    available_roles = ["reporter"]
active_role = st.session_state.get("active_profile_role")
if active_role not in available_roles:
    active_role = user.get("role") if user.get("role") in available_roles else available_roles[0]
    st.session_state["active_profile_role"] = active_role
# Pages receive the active operating profile, while repositories re-check every
# privileged write against all persisted user roles.
user = dict(user)
user["role"] = active_role
user["roles"] = available_roles

navigation_items = ROLE_NAVIGATION.get(active_role, ROLE_NAVIGATION["reporter"])
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
    if len(available_roles) > 1:
        selected_role = st.selectbox("Perfil activo", available_roles, index=available_roles.index(active_role), format_func=lambda r: ROLES.get(r, r), key="profile_role_selector")
        if selected_role != active_role:
            st.session_state["active_profile_role"] = selected_role
            st.session_state.pop(nav_key, None)
            st.rerun()
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
    _render_reports_route(user, mode="work")
elif route == "report_archive":
    _render_reports_route(user, mode="archive")
elif route == "players":
    from pages.players import render
    render(user)
elif route == "calendar":
    from pages.calendar import render
    render(user)
elif route == "scout":
    from pages.scout import render
    render(user)
elif route == "model":
    from pages.model import render
    render(user)
elif route == "director":
    from pages.director import render
    render(user)
elif route == "scouted":
    from pages.scouted import render
    render(user)
elif route == "postmatch":
    from pages.postmatch import render
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
