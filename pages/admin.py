from __future__ import annotations

import base64
import json

import pandas as pd
import streamlit as st
from sqlalchemy import desc, select

from core.config import settings
from core.constants import ROLES
from core.database import session_scope
from models.entities import LoginAttempt
from repositories import scouting as repo
from services.export_service import technical_backup_zip
from services.health_service import database_probe, live_acceptance_rollback
from core.performance import clear_performance_events, measure, performance_events, performance_summary
from services.storage_service import load_document_bytes, retry_remote_storage
from ui.styles import page_header


def _pretty_json(value: str | None) -> str:
    if not value:
        return ""
    try:
        return json.dumps(json.loads(value), ensure_ascii=False, indent=2, default=str)
    except Exception:
        return value


def _section_users(user: dict) -> None:
    with session_scope() as session:
        users = repo.list_users(session)
    st.dataframe(pd.DataFrame([{
        "ID": u.id, "Nombre": u.full_name, "Correo": u.email, "Rol": ROLES.get(u.role, u.role),
        "Activo": u.active, "Cambio de contraseña": u.must_change_password, "Bloqueado hasta": u.locked_until,
        "Revisión sesión": u.session_revision, "Último acceso": u.last_login_at,
    } for u in users]), use_container_width=True, hide_index=True)
    with st.form("new_user"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nombre completo")
        email = c2.text_input("Correo")
        c3, c4 = st.columns(2)
        role = c3.selectbox("Rol", list(ROLES.keys()), format_func=lambda r: ROLES[r])
        password = c4.text_input("Contraseña inicial", type="password", help="Mínimo 10 caracteres, mayúscula, minúscula, número y símbolo.")
        force_change = st.checkbox("Obligar a cambiarla en el primer acceso", value=True)
        create = st.form_submit_button("Crear usuario", type="primary")
    if create:
        try:
            with session_scope() as session:
                repo.create_user(session, name, email, password, role=role, actor_id=user["id"], must_change_password=force_change)
            st.success("Usuario creado.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if users:
        selected = st.selectbox("Editar usuario", [u.id for u in users], format_func=lambda uid: next(f"{u.full_name} · {u.email}" for u in users if u.id == uid))
        selected_user = next(u for u in users if u.id == selected)
        with st.form(f"edit_user_{selected}"):
            full_name = st.text_input("Nombre completo", value=selected_user.full_name)
            c1, c2 = st.columns(2)
            role_new = c1.selectbox("Rol", list(ROLES.keys()), index=list(ROLES.keys()).index(selected_user.role), format_func=lambda r: ROLES[r])
            active = c2.checkbox("Activo", value=selected_user.active)
            password_new = st.text_input("Nueva contraseña", type="password", help="Déjala vacía para mantener la actual. Si se cambia, el usuario deberá sustituirla al entrar.")
            save = st.form_submit_button("Guardar usuario")
        if save:
            if selected == user["id"] and not active:
                st.error("No puedes desactivar tu propia cuenta durante la sesión.")
            else:
                try:
                    with session_scope() as session:
                        repo.update_user(session, selected, role_new, active, password_new or None, user["id"], full_name=full_name)
                    st.success("Usuario actualizado. Sus sesiones anteriores han quedado invalidadas.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def _section_brand(user: dict) -> None:
    with session_scope() as session:
        app_settings = repo.get_all_settings(session)
    if app_settings.get("logo_b64"):
        try:
            st.image(base64.b64decode(app_settings["logo_b64"]), width=110, caption="Logotipo actual")
        except Exception:
            st.warning("El logotipo guardado no se ha podido previsualizar.")
    with st.form("brand_form"):
        club_name = st.text_input("Nombre de la aplicación / club", value=app_settings.get("club_name") or "NO NAME")
        report_subtitle = st.text_input("Subtítulo del informe PDF", value=app_settings.get("report_subtitle") or "Dirección deportiva · Observación de rivales")
        confidentiality = st.text_input("Leyenda de confidencialidad", value=app_settings.get("report_confidentiality") or "Documento interno y confidencial")
        c1, c2 = st.columns(2)
        primary = c1.color_picker("Color principal", value=app_settings.get("primary_color") or "#B91C1C")
        secondary = c2.color_picker("Color secundario", value=app_settings.get("secondary_color") or "#111827")
        pdf_default = st.selectbox("PDF por defecto", ["executive", "full"], index=0 if app_settings.get("pdf_default_mode", "executive") == "executive" else 1, format_func=lambda v: "Resumen" if v == "executive" else "Completo")
        require_approval = st.checkbox("Exigir aprobación de dirección deportiva", value=(app_settings.get("require_report_approval", "true").lower() == "true"))
        logo = st.file_uploader("Escudo o logotipo (PNG/JPG)", type=["png", "jpg", "jpeg"])
        remove_logo = st.checkbox("Eliminar el logotipo actual", disabled=not bool(app_settings.get("logo_b64")))
        save = st.form_submit_button("Guardar identidad", type="primary")
    if save:
        with session_scope() as session:
            repo.set_setting(session, "club_name", club_name.strip() or "NO NAME", user["id"])
            repo.set_setting(session, "report_subtitle", report_subtitle.strip() or None, user["id"])
            repo.set_setting(session, "report_confidentiality", confidentiality.strip() or None, user["id"])
            repo.set_setting(session, "primary_color", primary, user["id"])
            repo.set_setting(session, "secondary_color", secondary, user["id"])
            repo.set_setting(session, "pdf_default_mode", pdf_default, user["id"])
            repo.set_setting(session, "require_report_approval", "true" if require_approval else "false", user["id"])
            if remove_logo:
                repo.set_setting(session, "logo_b64", None, user["id"])
                repo.set_setting(session, "logo_mime", None, user["id"])
            elif logo:
                repo.set_setting(session, "logo_b64", base64.b64encode(logo.getvalue()).decode("ascii"), user["id"])
                repo.set_setting(session, "logo_mime", logo.type, user["id"])
        st.cache_data.clear()
        st.success("Identidad y reglas de informe actualizadas.")
        st.rerun()


def _section_security(user: dict) -> None:
    st.subheader("Configuración de acceso")
    c1, c2, c3 = st.columns(3)
    c1.metric("Intentos antes del bloqueo", settings.login_max_attempts)
    c2.metric("Bloqueo temporal", f"{settings.login_lock_minutes} min")
    c3.metric("Modo", "Demostración" if settings.demo_mode else "Producción")
    if not settings.demo_mode:
        st.success("El despliegue está configurado en modo producción: las credenciales de demostración no se muestran.")
    else:
        st.warning("Modo demo activo. No introduzcas datos sensibles.")
    with session_scope() as session:
        attempts = list(session.scalars(select(LoginAttempt).order_by(desc(LoginAttempt.created_at)).limit(200)).all())
    if attempts:
        st.dataframe(pd.DataFrame([{
            "Fecha": a.created_at, "Correo": a.email, "Usuario ID": a.user_id,
            "Resultado": "Correcto" if a.success else "Fallido", "Detalle": a.detail,
        } for a in attempts]), use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay intentos de acceso registrados.")


def _section_storage(user: dict) -> None:
    with session_scope() as session:
        documents = repo.list_documents(session)
    if not documents:
        st.info("No hay documentos generados.")
    else:
        st.dataframe(pd.DataFrame([{
            "ID": d.id, "Informe": d.report_id, "Versión": d.version, "Tipo": d.document_type,
            "Estado": d.storage_status, "Tamaño": d.size_bytes, "Checksum": d.checksum,
            "Ruta remota": d.storage_path, "Ruta local": d.local_path, "Error": d.error_message,
        } for d in documents]), use_container_width=True, hide_index=True)
        failed = [d for d in documents if d.storage_status not in {"stored_remote", "local_only"}]
        if failed:
            st.error(f"Hay {len(failed)} documentos con almacenamiento incompleto. El estado ya no se oculta.")
        selected_doc = st.selectbox("Comprobar/descargar documento", [d.id for d in documents], format_func=lambda did: next(f"Informe {d.report_id} · V{d.version} · {d.document_type} · {d.storage_status}" for d in documents if d.id == did))
        doc = next(d for d in documents if d.id == selected_doc)
        try:
            payload = load_document_bytes(bucket=doc.storage_bucket, storage_path=doc.storage_path, local_path=doc.local_path)
            if payload:
                st.download_button("Descargar archivo almacenado", payload, f"informe_{doc.report_id}_v{doc.version}_{doc.document_type}.pdf", "application/pdf")
            else:
                st.warning("El registro existe, pero el archivo no puede recuperarse. Revisa la ruta o regenera una nueva versión.")
        except Exception as exc:
            st.error(f"Error al recuperar el documento: {exc}")
        if doc.storage_status == "remote_failed" and st.button("Reintentar subida remota", key=f"retry_doc_{doc.id}"):
            try:
                result = retry_remote_storage(doc.report_id, doc.version, doc.document_type, local_path=doc.local_path)
                with session_scope() as session:
                    refreshed = session.get(type(doc), doc.id)
                    refreshed.storage_bucket = result.get("storage_bucket")
                    refreshed.storage_path = result.get("storage_path")
                    refreshed.local_path = result.get("local_path")
                    refreshed.storage_status = str(result.get("storage_status"))
                    refreshed.error_message = result.get("error_message")
                    refreshed.checksum = result.get("checksum")
                    refreshed.size_bytes = result.get("size_bytes")
                    repo.audit(session, user["id"], "retry_document_storage", "document", doc.id, detail=refreshed.storage_status)
                st.success(f"Reintento completado: {result.get('storage_status')}")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _section_audit(user: dict) -> None:
    action_filter = st.text_input("Filtrar por acción")
    with session_scope() as session:
        logs = repo.list_audit_logs(session, limit=500, action=action_filter.strip() or None)
        users = {u.id: u.full_name for u in repo.list_users(session)}
    if logs:
        st.dataframe(pd.DataFrame([{
            "Fecha": log.created_at, "Usuario": users.get(log.user_id, "Sistema"), "Acción": log.action,
            "Entidad": log.entity_type, "ID": log.entity_id, "Detalle": log.detail,
        } for log in logs]), use_container_width=True, hide_index=True)
        selected_log = st.selectbox("Abrir detalle", [log.id for log in logs], format_func=lambda lid: next(f"{log.created_at} · {log.action} · {log.entity_type or '-'} {log.entity_id or ''}" for log in logs if log.id == lid))
        log = next(log for log in logs if log.id == selected_log)
        c1, c2 = st.columns(2)
        c1.text_area("Antes", value=_pretty_json(log.before_json), height=260, disabled=True)
        c2.text_area("Después", value=_pretty_json(log.after_json), height=260, disabled=True)
    else:
        st.info("No hay eventos registrados.")


def _section_backup(user: dict) -> None:
    st.warning("El backup técnico contiene todos los datos estructurados, incluidos hashes de contraseña. Trátalo como un archivo confidencial y almacénalo cifrado.")
    st.caption("No se consulta ni serializa toda la base al entrar aquí. El ZIP solo se prepara cuando lo solicitas.")
    if st.button("Preparar backup técnico", type="primary", use_container_width=True):
        with st.spinner("Preparando backup..."):
            with measure("Backup técnico", "admin"):
                with session_scope() as session:
                    st.session_state["admin_backup_34"] = technical_backup_zip(session)
    backup = st.session_state.get("admin_backup_34")
    if backup:
        st.download_button("Descargar backup técnico restaurable", backup, "noname_postmatch_3_4_backup.zip", "application/zip", type="primary", use_container_width=True)
    st.caption("Este backup es distinto de la exportación analítica Excel: conserva tablas y relaciones para recuperación técnica.")


def _section_performance(user: dict) -> None:
    st.subheader("Rendimiento y aceptación")
    st.caption("Diagnóstico interno: no se guarda telemetría adicional en Supabase.")
    a, b = st.columns(2)
    if a.button("Probar conexión y lecturas", use_container_width=True):
        with measure("Diagnóstico DB", "admin"):
            with session_scope() as session:
                st.session_state["admin_db_probe_34"] = database_probe(session)
    if b.button("Ejecutar aceptación real (rollback)", type="primary", use_container_width=True, help="Crea datos temporales dentro de un SAVEPOINT y los revierte al terminar."):
        try:
            with measure("Aceptación live rollback", "admin"):
                with session_scope() as session:
                    st.session_state["admin_acceptance_34"] = live_acceptance_rollback(session, user["id"])
            st.success("Flujo crítico verificado contra la base configurada; los datos de prueba se han revertido.")
        except Exception as exc:
            st.error(f"La aceptación ha detectado un problema: {exc}")
    if st.session_state.get("admin_db_probe_34"):
        st.json(st.session_state["admin_db_probe_34"])
    if st.session_state.get("admin_acceptance_34"):
        st.json(st.session_state["admin_acceptance_34"])
    events = performance_events()
    if events:
        st.markdown("#### Últimas operaciones")
        st.dataframe(pd.DataFrame(events[-50:]), hide_index=True, use_container_width=True)
        summary = performance_summary()
        if summary:
            st.markdown("#### Cuellos de botella")
            st.dataframe(pd.DataFrame(summary[:20]), hide_index=True, use_container_width=True)
        if st.button("Limpiar mediciones", use_container_width=True):
            clear_performance_events(); st.rerun()
    else:
        st.info("Todavía no hay mediciones en esta sesión.")


def render(user: dict) -> None:
    page_header("Administración", 'Abre solo lo que necesites. Cada sección consulta la base de datos únicamente al entrar.')
    section = st.radio(
        "Sección",
        ['Usuarios', 'Identidad', 'Seguridad', 'Documentos', 'Auditoría', 'Backup', 'Rendimiento'],
        horizontal=True,
        key="admin_section",
        help="Solo se consulta la sección que abras; el resto no ejecuta consultas en segundo plano.",
    )
    if section == 'Usuarios':
        _section_users(user)
    elif section == 'Identidad':
        _section_brand(user)
    elif section == 'Seguridad':
        _section_security(user)
    elif section == 'Documentos':
        _section_storage(user)
    elif section == 'Auditoría':
        _section_audit(user)
    elif section == 'Backup':
        _section_backup(user)
    elif section == 'Rendimiento':
        _section_performance(user)
