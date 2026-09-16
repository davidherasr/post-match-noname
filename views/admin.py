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
from repositories import data_quality as quality_repo
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
    st.markdown("### Gestión de usuarios")
    st.caption(
        "Desde aquí el Administrador puede añadir, editar, desactivar o eliminar cuentas y repartir roles. "
        "Las contraseñas se gestionan desde cada cuenta y pueden modificarse opcionalmente."
    )

    with st.expander('¿Qué permite cada rol?', expanded=False):
        st.markdown('**Administrador:** usuarios, calendario y datos.  '
                    '**Dirección Deportiva:** análisis y decisiones.  '
                    '**Informador:** evaluaciones e informes.')
        st.caption('El seguimiento de jugadores externos requiere un permiso independiente.')

    with session_scope() as session:
        all_users = repo.list_users(session, include_deleted=True)
        users = [u for u in all_users if u.deleted_at is None]
        deleted_users = [u for u in all_users if u.deleted_at is not None]
        role_map = {u.id: repo.get_user_roles(session, u.id) for u in all_users}

    mode = st.segmented_control(
        "Gestión",
        ["Listado", "Añadir", "Editar / eliminar", "Eliminados"],
        default="Listado",
        key="admin_user_management_411",
    ) or "Listado"

    if mode == "Listado":
        if not users:
            st.info("No hay usuarios activos o desactivados.")
            return
        rows = []
        for u in users:
            rows.append({
                                "Nombre": u.full_name,
                "Correo": u.email,
                "Roles": ", ".join(ROLES.get(r, r) for r in role_map.get(u.id, [u.role])),
                "Estado": "Activo" if u.active else "Desactivado",
                "Último acceso": u.last_login_at,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("Desactivar conserva la cuenta pero impide iniciar sesión. Eliminar la oculta de la gestión habitual y preserva el historial deportivo/auditoría.")
        return

    if mode == "Añadir":
        st.markdown("#### Añadir usuario")
        with st.form("new_user_411"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre completo")
            email = c2.text_input("Correo")
            c3, c4 = st.columns(2)
            roles = c3.multiselect(
                "Roles y accesos",
                ["admin", "director", "reporter"],
                default=["reporter"],
                format_func=lambda r: ROLES[r],
                help="Los roles son independientes. Asigna DD e Informador a quien deba poder realizar informes opcionales.",
            )
            password = c4.text_input(
                "Contraseña",
                type="password",
                help="Utiliza una contraseña privada y no la compartas. No puede estar vacía.",
            )
            active = c4.checkbox("Cuenta activa", value=True)
            track_players = st.checkbox("Puede realizar seguimiento individual de jugadores", value=False, help="Permiso especial para abrir seguimientos de jugadores externos y alimentar su Player Report 360.")
            create = st.form_submit_button("Crear usuario", type="primary", use_container_width=True)
        if create:
            if not roles:
                st.error("Selecciona al menos un rol y acceso para el usuario.")
            else:
                try:
                    with session_scope() as session:
                        repo.create_user(
                            session,
                            name,
                            email,
                            password,
                            role=repo.compatibility_role_for(roles),
                            roles=roles,
                            active=active,
                            actor_id=user["id"],
                            must_change_password=False,
                            can_track_players=track_players,
                        )
                    st.success("Usuario creado correctamente.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        return

    if mode == "Editar / eliminar":
        if not users:
            st.info("No hay usuarios para editar.")
            return
        selected = st.selectbox(
            "Usuario",
            [u.id for u in users],
            format_func=lambda uid: next(f"{u.full_name} · {u.email}" for u in users if u.id == uid),
            key="admin_edit_user_select_411",
        )
        selected_user = next(u for u in users if u.id == selected)
        current_roles = role_map.get(selected, [selected_user.role])

        with st.form(f"edit_user_411_{selected}"):
            c1, c2 = st.columns(2)
            full_name = c1.text_input("Nombre completo", value=selected_user.full_name)
            email = c2.text_input("Correo", value=selected_user.email)
            roles_new = st.multiselect(
                "Roles y accesos",
                ["admin", "director", "reporter"],
                default=[r for r in current_roles if r in {"admin", "director", "reporter"}],
                format_func=lambda r: ROLES[r],
            )
            c3, c4 = st.columns(2)
            c3.caption("Los accesos dependen únicamente de los roles seleccionados; no existe un rol principal.")
            active = c4.checkbox("Cuenta activa", value=selected_user.active)
            track_players = st.checkbox("Puede realizar seguimiento individual de jugadores", value=bool(getattr(selected_user, "can_track_players", False)), help="Habilita el seguimiento individual de jugadores externos de forma independiente a los roles del usuario.")
            password_new = st.text_input(
                "Nueva contraseña (opcional)",
                type="password",
                help="Déjala vacía para mantener la contraseña actual.",
            )
            save = st.form_submit_button("Guardar cambios", type="primary", use_container_width=True)
        if save:
            if not roles_new:
                st.error("Selecciona al menos un rol y acceso para el usuario.")
            elif selected == user["id"] and not active:
                st.error("No puedes desactivar tu propia cuenta durante la sesión.")
            else:
                try:
                    with session_scope() as session:
                        repo.update_user(
                            session,
                            selected,
                            repo.compatibility_role_for(roles_new),
                            active,
                            password_new or None,
                            user["id"],
                            full_name=full_name,
                            email=email,
                            roles=roles_new,
                            force_password_change=False,
                            can_track_players=track_players,
                        )
                    st.success("Usuario actualizado.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        st.markdown("#### Eliminar usuario")
        st.caption("La eliminación bloquea el acceso y oculta la cuenta sin romper informes, seguimientos, asignaciones o auditoría anteriores.")
        if selected == user["id"]:
            st.info("Tu propia cuenta no se puede eliminar mientras estás conectado con ella.")
        else:
            confirm = st.checkbox(
                f"Confirmo que quiero eliminar a {selected_user.full_name}",
                key=f"confirm_delete_user_411_{selected}",
            )
            if st.button(
                "Eliminar usuario",
                type="secondary",
                use_container_width=True,
                disabled=not confirm,
                key=f"delete_user_411_{selected}",
            ):
                try:
                    with session_scope() as session:
                        repo.delete_user(session, selected, user["id"])
                    st.success("Usuario eliminado. Su historial se conserva.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        return

    # Eliminados
    st.markdown("#### Usuarios eliminados")
    if not deleted_users:
        st.info("No hay usuarios eliminados.")
        return
    st.dataframe(pd.DataFrame([{
                "Nombre": u.full_name,
        "Correo": u.email,
        "Eliminado": u.deleted_at,
        "Roles": ", ".join(ROLES.get(r, r) for r in role_map.get(u.id, [u.role])),
    } for u in deleted_users]), use_container_width=True, hide_index=True)
    selected_deleted = st.selectbox(
        "Usuario eliminado",
        [u.id for u in deleted_users],
        format_func=lambda uid: next(f"{u.full_name} · {u.email}" for u in deleted_users if u.id == uid),
        key="admin_deleted_user_select_411",
    )
    restore_password = st.text_input(
        "Nueva contraseña al restaurar (opcional)",
        type="password",
        help="Si la dejas vacía, conservará la contraseña anterior.",
        key=f"restore_password_411_{selected_deleted}",
    )
    if st.button("Restaurar usuario", type="primary", use_container_width=True, key=f"restore_user_411_{selected_deleted}"):
        try:
            with session_scope() as session:
                repo.restore_user(session, selected_deleted, user["id"], password=restore_password or None)
            st.success("Usuario restaurado y activado.")
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
        club_name = st.text_input("Nombre del club", value=app_settings.get("club_name") or "NO NAME")
        report_subtitle = st.text_input("Subtítulo del informe PDF", value=app_settings.get("report_subtitle") or "Dirección deportiva · Observación de rivales")
        confidentiality = st.text_input("Leyenda de confidencialidad", value=app_settings.get("report_confidentiality") or "Documento interno y confidencial")
        c1, c2 = st.columns(2)
        primary = c1.color_picker("Color principal", value=app_settings.get("primary_color") or "#B91C1C")
        secondary = c2.color_picker("Color secundario", value=app_settings.get("secondary_color") or "#111827")
        pdf_default = st.selectbox("PDF por defecto", ["executive", "full"], index=0 if app_settings.get("pdf_default_mode", "executive") == "executive" else 1, format_func=lambda v: "Resumen" if v == "executive" else "Completo")
        st.caption('Los informes entregados se incorporan directamente al análisis deportivo.')
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
            repo.set_setting(session, "require_report_approval", "false", user["id"])
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
            "Fecha": a.created_at, "Correo": a.email, 
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
            "Informe": d.report_id, "Versión": d.version, "Tipo": d.document_type,
            "Estado": d.storage_status, "Tamaño": d.size_bytes, "Checksum": d.checksum,
            "Ruta remota": d.storage_path, "Ruta local": d.local_path, "Error": d.error_message,
        } for d in documents]), use_container_width=True, hide_index=True)
        failed = [d for d in documents if d.storage_status not in {"stored_remote", "local_only"}]
        if failed:
            st.error(f"Hay {len(failed)} documentos con almacenamiento incompleto. El estado ya no se oculta.")
        selected_doc = st.selectbox("Comprobar/descargar documento", [d.id for d in documents], format_func=lambda did: next(f"{d.document_type} · Versión {d.version} · {d.storage_status}" for d in documents if d.id == did))
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
            "Entidad": log.entity_type, "Detalle": log.detail,
        } for log in logs]), use_container_width=True, hide_index=True)
        selected_log = st.selectbox("Abrir detalle", [log.id for log in logs], format_func=lambda lid: next(f"{log.created_at} · {log.action} · {log.entity_type or '-'}" for log in logs if log.id == lid))
        log = next(log for log in logs if log.id == selected_log)
        c1, c2 = st.columns(2)
        c1.text_area("Antes", value=_pretty_json(log.before_json), height=260, disabled=True)
        c2.text_area("Después", value=_pretty_json(log.after_json), height=260, disabled=True)
    else:
        st.info("No hay eventos registrados.")


def _section_backup(user: dict) -> None:
    st.warning("La exportación técnica contiene datos personales y hashes de contraseña. Protégela y no la compartas. Para un respaldo restaurable necesitas una copia SQL de PostgreSQL y otra del almacenamiento de documentos.")
    st.caption("No se consulta ni serializa toda la base al entrar aquí. El ZIP se prepara únicamente cuando lo solicitas.")
    if st.button("Preparar exportación técnica", type="primary", use_container_width=True):
        with st.spinner("Preparando exportación..."):
            with measure("Exportación técnica", "admin"):
                with session_scope() as session:
                    st.session_state["admin_export_4232"] = technical_backup_zip(session)
    backup = st.session_state.get("admin_export_4232")
    if backup:
        st.download_button("Descargar exportación técnica", backup, "noname_area_tecnica_exportacion.zip", "application/zip", type="primary", use_container_width=True)
    st.caption("Incluye todas las tablas mapeadas, pero no equivale a una copia SQL restaurable ni incluye los documentos almacenados.")


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


def _section_data_quality(user: dict) -> None:
    st.subheader("Calidad de datos")
    st.caption("Solo aparecen excepciones que merece la pena revisar; no necesitas inspeccionar tablas manualmente.")
    with session_scope() as session:
        issues = quality_repo.quality_issues(session)
    if not issues:
        st.success("No se han detectado incidencias de calidad de datos.")
        return
    counts = {level: len([i for i in issues if i["severity"] == level]) for level in ["Alta","Media","Baja"]}
    a,b,c=st.columns(3); a.metric("Altas",counts["Alta"]); b.metric("Medias",counts["Media"]); c.metric("Bajas",counts["Baja"]);
    st.dataframe(pd.DataFrame(issues),hide_index=True,use_container_width=True)
    st.info("Corrige estas incidencias desde Base de datos. Las posibles identidades duplicadas nunca se fusionan automáticamente.")


def render(user: dict) -> None:
    page_header("Administración", 'Abre solo lo que necesites. Cada sección consulta la base de datos únicamente al entrar.')
    section = st.radio(
        "Sección",
        ['Usuarios', 'Identidad', 'Calidad de datos', 'Seguridad', 'Documentos', 'Auditoría', 'Backup', 'Rendimiento'],
        horizontal=True,
        key="admin_section",
        help="Solo se consulta la sección que abras; el resto no ejecuta consultas en segundo plano.",
    )
    if section == 'Usuarios':
        _section_users(user)
    elif section == 'Identidad':
        _section_brand(user)
    elif section == 'Calidad de datos':
        _section_data_quality(user)
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
