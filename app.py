from __future__ import annotations

import logging

import streamlit as st

# Keep the very first Streamlit command independent from project imports.
# This lets us show a useful diagnosis even when a deployment contains files
# from different releases (for example a new app.py with an old core/config.py).
st.set_page_config(
    page_title="No Name · Área Técnica",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.set_option("client.showSidebarNavigation", False)

try:
    import core.config as _config

    _required_config = (
        "APP_NAME",
        "APP_VERSION",
        "database_target",
        "settings",
        "validate_production_settings",
    )
    _missing_config = [name for name in _required_config if not hasattr(_config, name)]
    if _missing_config:
        raise ImportError(
            "core/config.py no corresponde a esta release; faltan: "
            + ", ".join(_missing_config)
        )

    APP_NAME = _config.APP_NAME
    APP_VERSION = _config.APP_VERSION
    database_target = _config.database_target
    settings = _config.settings
    validate_production_settings = _config.validate_production_settings

    from core.auth import current_user, login, logout
    from core.constants import ROLES
    from core.permissions import navigation_for, roles_for
    from core.database import DatabaseSchemaError, DatabaseUnavailableError, init_db, session_scope
    from core.utils import safe_html
    from repositories import scouting as repo
    from services.bootstrap import bootstrap_application
    from ui.styles import apply_global_styles
except ImportError as exc:
    st.error("El despliegue contiene archivos mezclados de versiones distintas.")
    st.markdown(
        "No Name · Área Técnica se ha detenido antes de acceder a la base de datos. "
        "Sustituye **todo el contenido del repositorio** por la versión 4.4.1; "
        "no copies archivos sueltos encima de una versión anterior."
    )
    st.code(str(exc), language="text")
    st.info(
        "Comprueba especialmente que existan `views/` y `core/config.py` de la misma release, "
        "y que no exista el directorio `pages/`."
    )
    st.stop()


def _render_database_startup_error(exc: Exception) -> None:
    target = database_target()
    st.error("No Name · Área Técnica no puede conectar con la base de datos.")
    st.markdown(
        "La aplicación se ha detenido **antes de modificar ningún dato**. "
        "Revisa la conexión PostgreSQL/Supabase en los Secrets de Streamlit Cloud."
    )
    host = target.get("host") or "No reconocido"
    port = target.get("port") or "—"
    st.code(f"Host: {host}\nPuerto: {port}\nVersión: {APP_VERSION}", language="text")
    if target.get("is_direct_supabase"):
        st.warning(
            "La URL apunta al host directo de Supabase (`db.<proyecto>.supabase.co`). "
            "En entornos sin IPv6 puede no ser accesible. Usa en `DATABASE_URL` la "
            "**Session pooler connection string** de Supabase (Database → Connect), "
            "manteniendo la misma base y contraseña."
        )
    else:
        st.info(
            "Si usas Supabase, comprueba que `DATABASE_URL` sea la cadena PostgreSQL "
            "de **Session pooler**, que la contraseña esté correctamente escapada y que "
            "no queden valores de ejemplo como `PROJECT_REF`, `PASSWORD` o `REGION`."
        )
    st.caption(
        "La contraseña nunca se muestra ni se registra en esta pantalla. "
        "Después de corregir el Secret, reinicia la app desde Manage app → Reboot."
    )
    st.stop()


_startup_logger = logging.getLogger("noname.startup")


def _render_unexpected_startup_error(exc: Exception, phase: str) -> None:
    _startup_logger.exception("Startup failure during %s", phase)
    st.error("No Name · Área Técnica no ha podido completar el arranque de la base de datos.")
    st.markdown(
        "No se ha continuado con el arranque. Consulta **Manage app → Logs** para el detalle técnico. "
        "La versión actual identifica también la fase exacta del arranque para evitar diagnósticos a ciegas."
    )
    st.caption(f"Fase: {phase} · Tipo de error: {type(exc).__name__} · Versión {APP_VERSION}")
    st.stop()


try:
    validate_production_settings()
except RuntimeError as exc:
    st.error("Configuración de despliegue incompleta.")
    st.write(str(exc))
    st.stop()
except Exception as exc:
    _render_unexpected_startup_error(exc, "configuración")

try:
    init_db()
except DatabaseUnavailableError as exc:
    _render_database_startup_error(exc)
except DatabaseSchemaError as exc:
    st.error("La base de datos necesita completar una actualización de esquema.")
    st.markdown(
        "No se ha ejecutado ninguna pantalla deportiva. La aplicación valida de forma "
        "**no destructiva** que el esquema físico de Supabase coincide con la aplicación."
    )
    if exc.missing:
        lines = []
        for table, columns in exc.missing.items():
            lines.append(f"{table}: {', '.join(columns)}")
        st.code("\n".join(lines), language="text")
    st.info(
        "Comprueba que `RUN_MIGRATIONS = true` en los Secrets de Streamlit Cloud y haz "
        "**Manage app → Reboot**. El proyecto incorpora la migración aditiva 0013: comprueba el head de PostgreSQL antes de iniciar."
    )
    st.stop()
except Exception as exc:
    _render_unexpected_startup_error(exc, "migraciones / validación de esquema")

try:
    bootstrap_application()
except DatabaseUnavailableError as exc:
    _render_database_startup_error(exc)
except Exception as exc:
    _render_unexpected_startup_error(exc, "bootstrap técnico")


@st.cache_data(ttl=180, show_spinner=False)
def _load_app_settings() -> dict:
    with session_scope() as session:
        return repo.get_all_settings(session)

try:
    app_settings = _load_app_settings()
except DatabaseUnavailableError as exc:
    _render_database_startup_error(exc)
except Exception as exc:
    _render_unexpected_startup_error(exc, "carga de ajustes")

apply_global_styles(
    app_settings.get("primary_color") or "#B91C1C",
    app_settings.get("secondary_color") or "#111827",
)


def _render_reports_route(user: dict, mode: str) -> None:
    """Render the reports page and fail clearly when deployment files are mixed."""
    from views import reports as reports_page

    expected_api = "4.4.1"
    deployed_api = getattr(reports_page, "REPORTS_PAGE_API_VERSION", None)
    if deployed_api != expected_api:
        st.error("La aplicación tiene archivos mezclados de versiones distintas.")
        st.markdown(
            "`app.py` y `views/reports.py` no corresponden a la misma versión. "
            "Sustituye **todo el contenido del repositorio** por el paquete 4.4.1 y reinicia la aplicación."
        )
        st.code(
            f"API esperada: {expected_api}\nAPI encontrada: {deployed_api or 'incompatible'}\n"
            "Archivo que debes comprobar: views/reports.py",
            language="text",
        )
        st.stop()

    renderer_name = "render_archive" if mode == "archive" else "render_work"
    renderer = getattr(reports_page, renderer_name, None)
    if not callable(renderer):
        st.error(f"No se encuentra la función requerida: views.reports.{renderer_name}().")
        st.info("Actualiza todos los archivos del proyecto y reinicia la aplicación.")
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
              <div class="pm-kicker">CUERPO TÉCNICO · {safe_html(app_settings.get('club_name') or 'NO NAME')}</div>
              <div class="pm-page-title" style="font-size:2.25rem">{safe_html(APP_NAME)}</div>
              <div class="pm-page-subtitle">Partidos, informes y análisis deportivo</div>
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

# Delete the delivered report's transient widgets on the *next* rerun, before
# any of those widgets can be instantiated again. Never alter persisted data.
_completed_report_id = st.session_state.pop("_pending_report_ui_cleanup", None)
if _completed_report_id is not None:
    from core.report_ui_flow import clear_submitted_report_state
    clear_submitted_report_state(st.session_state, int(_completed_report_id))

# 4.4: password changes are optional. Simple internal passwords are allowed.
# Legacy must_change_password flags are ignored/cleared on successful login.

# 3.8: roles are cumulative capabilities, never an operating profile selector.
st.session_state.pop("active_profile_role", None)
st.session_state.pop("profile_role_selector", None)

labels = navigation_for(user)
nav_key = "main_navigation"
from core.navigation import apply_pending_navigation
apply_pending_navigation(labels, nav_key=nav_key)

role_labels = [ROLES.get(role, role) for role in sorted(roles_for(user))]
with st.sidebar:
    st.markdown(
        f"""
        <div class="pm-brand">
          <div class="pm-brand-title">{safe_html(APP_NAME)}</div>
          <div class="pm-brand-version">{safe_html(app_settings.get('club_name') or 'Cuerpo técnico')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(user["full_name"])
    if role_labels:
        st.caption(" · ".join(role_labels))
    selected_label = st.radio("Navegación", labels, label_visibility="collapsed", key=nav_key)
    st.divider()
    with st.expander("Mi cuenta", expanded=False):
        st.caption("Puedes cambiar tu contraseña cuando lo necesites. Cambiarla es opcional.")
        with st.form("optional_password_change_sidebar"):
            current_password = st.text_input("Contraseña actual", type="password", key="sidebar_current_password")
            new_password = st.text_input("Nueva contraseña", type="password", key="sidebar_new_password", help="Elige una contraseña privada. No puede estar vacía.")
            repeat_password = st.text_input("Repite la nueva", type="password", key="sidebar_repeat_password")
            change_password_submit = st.form_submit_button("Cambiar contraseña", use_container_width=True)
        if change_password_submit:
            if new_password != repeat_password:
                st.error("Las contraseñas nuevas no coinciden.")
            else:
                try:
                    with session_scope() as session:
                        repo.change_own_password(session, user["id"], current_password, new_password)
                    logout()
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
    if st.button("Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()
    if settings.demo_mode:
        st.warning("Modo local")

if selected_label == "Inicio":
    from views.home import render
    render(user)
elif selected_label == "Jornada":
    from views.jornada import render
    render(user)
elif selected_label == "Jugadores":
    from views.player_hub import render
    render(user)
elif selected_label == "Dirección Deportiva":
    from views.squad import render
    render(user)
elif selected_label == "Administración":
    from views.admin_hub import render
    render(user)
else:
    from views.home import render
    render(user)
