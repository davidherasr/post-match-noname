from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import streamlit as st

from core.constants import CONFIDENCE_LEVELS, OBSERVATION_STATUSES, PDF_MODES, RECOMMENDATIONS, REPORT_STATUSES, STRENGTH_TAGS
from core.database import session_scope
from repositories import scouting as repo
from services.report_service import generate_report_pdf, report_filename
from services.storage_service import load_document_bytes, save_pdf
from ui.helpers import match_label
from ui.styles import page_header


def _default_index(options: list[str], value: str | None, default: int = 0) -> int:
    return options.index(value) if value in options else default


def _summary_autosave(report_id: int, user_id: int) -> None:
    prefix = f"summary_{report_id}_"
    try:
        with session_scope() as session:
            updated = repo.save_report_summary(
                session,
                report_id,
                rival_level=st.session_state.get(prefix + "level"),
                opponent_overview=(st.session_state.get(prefix + "overview") or "").strip() or None,
                own_team_note=(st.session_state.get(prefix + "own") or "").strip() or None,
                key_takeaways=(st.session_state.get(prefix + "takeaways") or "").strip() or None,
                standout_player_id=st.session_state.get(prefix + "mvp"),
                actor_id=user_id,
                expected_revision=st.session_state.get(f"report_revision_{report_id}"),
            )
            st.session_state[f"report_revision_{report_id}"] = updated.revision
            st.session_state[f"save_status_{report_id}"] = f"Guardado automáticamente · {datetime.now().strftime('%H:%M:%S')}"
    except Exception as exc:
        st.session_state[f"save_status_{report_id}"] = f"Cambios sin guardar: {exc}"


def _quick_autosave(report_id: int, user_id: int, team_id: int) -> None:
    editor_key = f"quick_rival_{report_id}"
    state = st.session_state.get(editor_key, {})
    edits = state.get("edited_rows", {}) if isinstance(state, dict) else {}
    base = st.session_state.get(f"quick_base_{report_id}", [])
    if not edits or not base:
        return
    label_to_status = {label: key for key, label in OBSERVATION_STATUSES.items()}
    try:
        with session_scope() as session:
            for idx_raw, changes in edits.items():
                idx = int(idx_raw)
                row = dict(base[idx])
                row.update(changes)
                status_key = label_to_status.get(str(row["Estado"]), "not_observed")
                evaluated = status_key == "evaluated"
                repo.upsert_evaluation(
                    session, report_id, int(row["player_id"]), team_id, int(row["participation_id"]), actor_id=user_id,
                    observation_status=status_key,
                    general_rating=float(row["Nota"]) if evaluated and pd.notna(row["Nota"]) else None,
                    recommendation=str(row["Decisión"]) if evaluated else None,
                    short_note=("" if pd.isna(row["Observación"]) else str(row["Observación"]).strip()) or None,
                    standout=bool(row["Destacado"]) if evaluated else False,
                    pdf_include=bool(row.get("PDF", True)) if evaluated else False,
                )
                base[idx] = row
        st.session_state[f"quick_base_{report_id}"] = base
        with session_scope() as session:
            refreshed = repo.get_report(session, report_id)
            if refreshed:
                st.session_state[f"report_revision_{report_id}"] = refreshed.revision
        st.session_state[f"save_status_{report_id}"] = f"Tabla guardada automáticamente · {datetime.now().strftime('%H:%M:%S')}"
    except Exception as exc:
        st.session_state[f"save_status_{report_id}"] = f"Cambios sin guardar: {exc}"


def _individual_autosave(report_id: int, user_id: int, participation, team_id: int, own_team: bool) -> None:
    prefix = f"eval_{report_id}_{participation.player_id}_"
    status = st.session_state.get(prefix + "status", "evaluated")
    advanced = bool(st.session_state.get(prefix + "advanced", False))
    try:
        with session_scope() as session:
            existing = repo.get_evaluation(session, report_id, participation.player_id)
            item = repo.upsert_evaluation(
                session, report_id, participation.player_id, team_id, participation.id, actor_id=user_id,
                expected_revision=existing.revision if existing else None,
                observation_status=status,
                general_rating=st.session_state.get(prefix + "general") if status == "evaluated" else None,
                recommendation=None if own_team or status != "evaluated" else st.session_state.get(prefix + "recommendation"),
                confidence=None if own_team or status != "evaluated" else st.session_state.get(prefix + "confidence"),
                short_note=(st.session_state.get(prefix + "note") or "").strip() or None,
                standout=bool(st.session_state.get(prefix + "standout", False)) if status == "evaluated" else False,
                pdf_include=bool(st.session_state.get(prefix + "pdf", True)) if status == "evaluated" else False,
                technical_rating=(st.session_state.get(prefix + "technical") or None) if advanced and not own_team else None,
                tactical_rating=(st.session_state.get(prefix + "tactical") or None) if advanced and not own_team else None,
                physical_rating=(st.session_state.get(prefix + "physical") or None) if advanced and not own_team else None,
                strengths=st.session_state.get(prefix + "strengths", []) if advanced and not own_team else [],
                detailed_note=(st.session_state.get(prefix + "detail") or "").strip() or None if advanced and not own_team else None,
            )
            st.session_state[prefix + "revision"] = item.revision
            refreshed = repo.get_report(session, report_id)
            if refreshed:
                st.session_state[f"report_revision_{report_id}"] = refreshed.revision
        st.session_state[f"save_status_{report_id}"] = f"Ficha guardada automáticamente · {datetime.now().strftime('%H:%M:%S')}"
    except Exception as exc:
        st.session_state[f"save_status_{report_id}"] = f"Cambios sin guardar: {exc}"


def _quick_rival_editor(report_id: int, rival_players, team_id: int, read_only: bool, user_id: int, evaluations: dict) -> None:
    label_to_status = {label: key for key, label in OBSERVATION_STATUSES.items()}
    status_labels = list(label_to_status.keys())
    rows = []
    for part in rival_players:
        ev = evaluations.get(part.player_id)
        rows.append({
            "player_id": part.player_id, "participation_id": part.id,
            "Jugador": part.player.display_name or part.player.full_name,
            "Posición": part.position or part.player.primary_position or "-",
            "Minutos": f"{part.minute_in}-{part.minute_out}",
            "Estado": OBSERVATION_STATUSES.get(ev.observation_status, "No observado") if ev else "No observado",
            "Nota": ev.general_rating if ev and ev.general_rating is not None else 6.0,
            "Decisión": ev.recommendation if ev and ev.recommendation else "Anotar en base de datos",
            "Observación": ev.short_note if ev and ev.short_note else "",
            "Destacado": bool(ev and ev.standout),
            "PDF": bool(ev.pdf_include) if ev else True,
        })
    st.session_state[f"quick_base_{report_id}"] = rows
    edited = st.data_editor(
        pd.DataFrame(rows), use_container_width=True, hide_index=True, key=f"quick_rival_{report_id}",
        on_change=_quick_autosave, args=(report_id, user_id, team_id),
        column_config={
            "player_id": None, "participation_id": None,
            "Jugador": st.column_config.TextColumn(width="medium"), "Posición": st.column_config.TextColumn(width="small"),
            "Minutos": st.column_config.TextColumn(width="small"),
            "Estado": st.column_config.SelectboxColumn(options=status_labels, required=True),
            "Nota": st.column_config.NumberColumn(min_value=1.0, max_value=10.0, step=0.5, format="%.1f"),
            "Decisión": st.column_config.SelectboxColumn(options=RECOMMENDATIONS, required=True),
            "Observación": st.column_config.TextColumn(width="large", max_chars=700),
            "Destacado": st.column_config.CheckboxColumn(help="Puede haber varios destacados."),
            "PDF": st.column_config.CheckboxColumn(help="Incluye ficha individual en el PDF completo."),
        },
        disabled=True if read_only else ["Jugador", "Posición", "Minutos"], num_rows="fixed",
    )
    if read_only:
        st.caption("Informe bloqueado: la tabla es solo de consulta.")
    else:
        st.caption("Los cambios de la tabla se guardan automáticamente. El MVP se elige una sola vez en el resumen.")


def _evaluation_form(report_id: int, participation, team_id: int, read_only: bool, own_team: bool, user_id: int, existing) -> None:
    player = participation.player
    prefix = f"eval_{report_id}_{player.id}_"
    title = f"#{participation.shirt_number or '-'} · {player.display_name or player.full_name}"
    badge = f" · {existing.general_rating:.1f}/10" if existing and existing.general_rating is not None else ""
    with st.expander(title + badge, expanded=False):
        st.caption(f"{participation.position or player.primary_position or '-'} · {participation.minute_in}-{participation.minute_out}' · {'Titular' if participation.starter else 'Suplente'}")
        callback = _individual_autosave
        args = (report_id, user_id, participation, team_id, own_team)
        st.selectbox("Estado de observación", list(OBSERVATION_STATUSES), index=_default_index(list(OBSERVATION_STATUSES), existing.observation_status if existing else "evaluated"), format_func=lambda k: OBSERVATION_STATUSES[k], key=prefix+"status", disabled=read_only, on_change=callback, args=args)
        c1, c2 = st.columns([1, 2])
        c1.slider("Nota general", 1.0, 10.0, float(existing.general_rating if existing and existing.general_rating is not None else 6.0), .5, key=prefix+"general", disabled=read_only, on_change=callback, args=args)
        c2.text_area("Observación breve", value=existing.short_note if existing else "", height=95, key=prefix+"note", disabled=read_only, on_change=callback, args=args)
        if not own_team:
            c1, c2, c3 = st.columns(3)
            c1.selectbox("Decisión", RECOMMENDATIONS, index=_default_index(RECOMMENDATIONS, existing.recommendation if existing else None, 1), key=prefix+"recommendation", disabled=read_only, on_change=callback, args=args)
            c2.selectbox("Confianza", CONFIDENCE_LEVELS, index=_default_index(CONFIDENCE_LEVELS, existing.confidence if existing else None, 1), key=prefix+"confidence", disabled=read_only, on_change=callback, args=args)
            c3.checkbox("Incluir ficha en PDF", value=bool(existing.pdf_include) if existing else True, key=prefix+"pdf", disabled=read_only, on_change=callback, args=args)
        st.checkbox("Jugador destacado", value=bool(existing and existing.standout), key=prefix+"standout", disabled=read_only, on_change=callback, args=args)
        if not own_team:
            advanced = st.checkbox("Añadir análisis avanzado", value=bool(existing and any([existing.technical_rating, existing.tactical_rating, existing.physical_rating, existing.strengths, existing.detailed_note])), key=prefix+"advanced", disabled=read_only)
            if advanced:
                a, b, c = st.columns(3)
                a.number_input("Técnica", 0.0, 10.0, float(existing.technical_rating or 0) if existing else 0.0, .5, key=prefix+"technical", disabled=read_only, on_change=callback, args=args)
                b.number_input("Táctica", 0.0, 10.0, float(existing.tactical_rating or 0) if existing else 0.0, .5, key=prefix+"tactical", disabled=read_only, on_change=callback, args=args)
                c.number_input("Física", 0.0, 10.0, float(existing.physical_rating or 0) if existing else 0.0, .5, key=prefix+"physical", disabled=read_only, on_change=callback, args=args)
                current_strengths = []
                if existing and existing.strengths:
                    try: current_strengths = json.loads(existing.strengths)
                    except json.JSONDecodeError: pass
                st.multiselect("Fortalezas", STRENGTH_TAGS, default=current_strengths, key=prefix+"strengths", disabled=read_only, on_change=callback, args=args)
                st.text_area("Nota ampliada", value=existing.detailed_note if existing else "", height=100, key=prefix+"detail", disabled=read_only, on_change=callback, args=args)


def _store_version_documents(session, report_id: int, version_obj, user_id: int) -> list[str]:
    messages = []
    for mode in ("executive", "full"):
        pdf = generate_report_pdf(session, report_id, version=version_obj.version, mode=mode)
        stored = save_pdf(report_id, version_obj.version, pdf, document_type=mode)
        repo.save_document(
            session, report_id, version_obj.version,
            report_version_id=version_obj.id, document_type=mode,
            storage_bucket=stored.get("storage_bucket"), storage_path=stored.get("storage_path"), local_path=stored.get("local_path"),
            checksum=stored.get("checksum"), size_bytes=stored.get("size_bytes"), storage_status=str(stored.get("storage_status")), error_message=stored.get("error_message"),
        )
        messages.append(f"{PDF_MODES[mode]}: {stored.get('storage_status')}")
    return messages


def _render_report_editor(report_id: int, user: dict) -> None:
    with session_scope() as session:
        report = repo.get_report(session, report_id)
        if not report:
            st.error("Informe no encontrado."); return
        participations = repo.get_participations(session, report.match_id)
        evaluation_list = repo.list_evaluations(session, report_id)
        versions = repo.list_report_versions(session, report_id)
        documents = repo.list_documents(session, report_id)
    if report.reporter_id != user["id"] and user["role"] not in {"admin", "director"}:
        st.error("No tienes acceso a este informe."); return
    rival_players = [p for p in participations if p.team_id == report.rival_team_id]
    own_players = [p for p in participations if p.team_id == report.own_team_id]
    evaluations = {e.player_id: e for e in evaluation_list}
    read_only = report.status not in {"draft", "returned"}
    st.session_state.setdefault(f"report_revision_{report_id}", report.revision)

    st.markdown(f"### {report.match.home_team.name} - {report.match.away_team.name}")
    st.caption(f"{report.match.competition.name} · {report.match.round_name} · {report.match.match_date.strftime('%d/%m/%Y')} · {REPORT_STATUSES.get(report.status, report.status)} · V{report.version}")
    if report.review_note:
        st.warning(f"Revisión: {report.review_note}")
    save_status = st.session_state.get(f"save_status_{report_id}")
    if save_status:
        st.caption(save_status)

    prefix = f"summary_{report_id}_"
    c1, c2 = st.columns(2)
    level_options = ["Bajo", "Medio-bajo", "Medio", "Medio-alto", "Alto"]
    c1.selectbox("Nivel mostrado por el rival", level_options, index=_default_index(level_options, report.rival_level, 2), key=prefix+"level", disabled=read_only, on_change=_summary_autosave, args=(report_id, user["id"]))
    mvp_options = [None] + [p.player_id for p in rival_players]
    labels = {None: "Sin seleccionar", **{p.player_id: p.player.display_name or p.player.full_name for p in rival_players}}
    c2.selectbox("MVP rival", mvp_options, index=mvp_options.index(report.standout_player_id) if report.standout_player_id in mvp_options else 0, format_func=lambda pid: labels[pid], key=prefix+"mvp", disabled=read_only, on_change=_summary_autosave, args=(report_id, user["id"]))
    st.text_area("Impresión general del rival", value=report.opponent_overview or "", height=115, key=prefix+"overview", disabled=read_only, on_change=_summary_autosave, args=(report_id, user["id"]))
    st.text_area("Ideas o nombres que conviene conservar", value=report.key_takeaways or "", height=85, key=prefix+"takeaways", disabled=read_only, on_change=_summary_autosave, args=(report_id, user["id"]))
    st.text_area("Nota breve sobre nuestro equipo (opcional)", value=report.own_team_note or "", height=75, key=prefix+"own", disabled=read_only, on_change=_summary_autosave, args=(report_id, user["id"]))

    tab_rival, tab_own, tab_finish, tab_versions = st.tabs(["Jugadores rivales", "Nuestro equipo", "Entrega y PDF", "Versiones y documentos"])
    with tab_rival:
        if not rival_players: st.warning("No hay alineación rival cargada.")
        else:
            quick, detailed = st.tabs(["Carga rápida", "Fichas opcionales"])
            with quick: _quick_rival_editor(report_id, rival_players, report.rival_team_id, read_only, user["id"], evaluations)
            with detailed:
                for part in rival_players: _evaluation_form(report_id, part, report.rival_team_id, read_only, False, user["id"], evaluations.get(part.player_id))
    with tab_own:
        st.caption("Bloque opcional y separado de las analíticas de scouting rival.")
        for part in own_players: _evaluation_form(report_id, part, report.own_team_id, read_only, True, user["id"], evaluations.get(part.player_id))
    with tab_finish:
        with session_scope() as session:
            errors = repo.validate_report_for_finalization(session, report_id)
        c1, c2, c3 = st.columns(3)
        valid = [e for e in evaluation_list if e.evaluation_scope == "rival" and e.observation_status == "evaluated" and e.general_rating is not None]
        c1.metric("Rivales evaluados", len(valid)); c2.metric("Fichas PDF", len([e for e in valid if e.pdf_include])); c3.metric("Versión", f"V{report.version}")
        if errors and not read_only:
            st.warning(" · ".join(errors))
        mode = st.radio("Vista previa", list(PDF_MODES), format_func=lambda m: PDF_MODES[m], horizontal=True)
        if not read_only:
            if st.button("Generar vista previa", use_container_width=True):
                with session_scope() as session:
                    st.session_state[f"preview_{report_id}_{mode}"] = generate_report_pdf(session, report_id, mode=mode)
                    name = report_filename(session, report_id, mode=mode).replace(".pdf", "_BORRADOR.pdf")
                st.session_state[f"preview_name_{report_id}_{mode}"] = name
            if f"preview_{report_id}_{mode}" in st.session_state:
                st.download_button("Descargar borrador", st.session_state[f"preview_{report_id}_{mode}"], file_name=st.session_state[f"preview_name_{report_id}_{mode}"], mime="application/pdf", use_container_width=True)
            confirm = st.checkbox("He revisado el informe y quiero entregar esta versión inmutable.")
            if st.button("Entregar informe", type="primary", disabled=not confirm or bool(errors), use_container_width=True):
                try:
                    with session_scope() as session:
                        submitted, version_obj = repo.submit_report(session, report_id, user["id"])
                        messages = _store_version_documents(session, report_id, version_obj, user["id"])
                    st.success("Informe entregado. " + " · ".join(messages))
                    st.rerun()
                except Exception as exc: st.error(str(exc))
        else:
            st.success(f"Informe bloqueado: {REPORT_STATUSES.get(report.status, report.status)}.")
            if report.status == "submitted": st.info("Pendiente de revisión por dirección deportiva.")
    with tab_versions:
        if not versions:
            st.info("Todavía no existe ninguna versión entregada.")
        for version_obj in versions:
            st.markdown(f"**V{version_obj.version} · {REPORT_STATUSES.get(version_obj.status, version_obj.status)} · {version_obj.created_at.strftime('%d/%m/%Y %H:%M')}**")
            docs = [d for d in documents if d.version == version_obj.version]
            cols = st.columns(max(1, len(docs)))
            for col, doc in zip(cols, docs):
                col.caption(f"{PDF_MODES.get(doc.document_type, doc.document_type)} · {doc.storage_status}")
                if doc.error_message: col.error(doc.error_message)
                try:
                    content = load_document_bytes(bucket=doc.storage_bucket, storage_path=doc.storage_path, local_path=doc.local_path)
                    with session_scope() as session:
                        filename = report_filename(session, report_id, version=doc.version, mode=doc.document_type)
                    col.download_button(f"Descargar {PDF_MODES.get(doc.document_type, doc.document_type)}", content, filename, "application/pdf", key=f"doc_{doc.id}")
                except Exception as exc: col.warning(str(exc))


def render(user: dict) -> None:
    page_header("Informes postpartido", "Asignaciones, autoguardado, revisión y versiones inmutables.")
    with session_scope() as session:
        all_matches = [m for m in repo.list_matches(session) if m.status in {"published", "closed"}]
        assignments = repo.list_assignments(session, user_id=user["id"])
        my_reports = repo.list_reports(session, reporter_id=user["id"])
    assigned_ids = {a.match_id for a in assignments if a.status != "waived"}
    matches = [m for m in all_matches if not assignments or m.id in assigned_ids or user["role"] in {"admin", "director"}]
    if not matches:
        st.info("No tienes partidos asignados."); return
    existing_by_match = {r.match_id: r for r in my_reports}
    labels = {m.id: match_label(m) + (f" · {REPORT_STATUSES.get(existing_by_match[m.id].status, existing_by_match[m.id].status)}" if m.id in existing_by_match else " · pendiente") for m in matches}
    selected_match_id = st.selectbox("Partido", [m.id for m in matches], format_func=lambda mid: labels[mid])
    selected_report = existing_by_match.get(selected_match_id)
    if not selected_report:
        if st.button("Comenzar informe", type="primary", use_container_width=True):
            try:
                with session_scope() as session:
                    report = repo.get_or_create_report(session, selected_match_id, user["id"], actor_role=user["role"])
                st.session_state["active_report_id"] = report.id; st.rerun()
            except Exception as exc: st.error(str(exc))
        return
    _render_report_editor(selected_report.id, user)
