from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.constants import CONFIDENCE_LEVELS, FOLLOW_UP_STATUSES, POSITIONS, RECOMMENDATIONS, REPORT_STATUSES
from core.database import session_scope
from repositories import scouting as repo
from services.export_service import analytics_export_xlsx, technical_backup_zip
from services.report_service import report_filename
from services.storage_service import load_document_bytes
from ui.styles import page_header


def _fmt(value):
    return "Sin muestra" if value is None or pd.isna(value) else round(float(value), 2)


def render(user: dict) -> None:
    page_header("Dirección deportiva", "Datos aprobados, revisión, consenso y agenda de seguimiento.")
    tabs = st.tabs(["Ranking validado", "Revisión y archivo", "Consenso por partido", "Comparador", "Seguimientos", "Exportar / Backup"])

    with session_scope() as session:
        seasons = repo.list_seasons(session)
        competitions = repo.list_competitions(session)
        teams = repo.list_teams(session)
        reporters = [u for u in repo.list_users(session, active_only=True) if u.role in {"reporter", "admin", "director"}]

    with tabs[0]:
        st.caption("Solo se incluyen jugadores rivales evaluados en informes aprobados. Los borradores y las notas del equipo propio quedan excluidos.")
        r1 = st.columns(4)
        position = r1[0].selectbox("Posición", ["Todas"] + POSITIONS)
        minimum = r1[1].number_input("Mínimo de observaciones", 1, 50, 1)
        recommendation = r1[2].selectbox("Decisión", ["Todas"] + RECOMMENDATIONS)
        confidence = r1[3].selectbox("Confianza", ["Todas"] + CONFIDENCE_LEVELS)
        r2 = st.columns(4)
        season_id = r2[0].selectbox("Temporada", [None] + [s.id for s in seasons], format_func=lambda sid: "Todas" if sid is None else next(s.name for s in seasons if s.id == sid))
        competition_id = r2[1].selectbox("Competición", [None] + [c.id for c in competitions], format_func=lambda cid: "Todas" if cid is None else next(c.name for c in competitions if c.id == cid))
        team_id = r2[2].selectbox("Equipo observado", [None] + [t.id for t in teams], format_func=lambda tid: "Todos" if tid is None else next(t.name for t in teams if t.id == tid))
        reporter_id = r2[3].selectbox("Informador", [None] + [u.id for u in reporters], format_func=lambda uid: "Todos" if uid is None else next(u.full_name for u in reporters if u.id == uid))
        r3 = st.columns(3)
        minimum_minutes = r3[0].number_input("Mínimo de minutos", 0, 120, 0)
        date_from = r3[1].date_input("Desde", value=None)
        date_to = r3[2].date_input("Hasta", value=None)
        with session_scope() as session:
            rows = repo.player_rankings(
                session, int(minimum), position, recommendation, season_id=season_id,
                competition_id=competition_id, team_id=team_id, reporter_id=reporter_id,
                confidence=confidence, date_from=date_from, date_to=date_to,
                minimum_minutes=int(minimum_minutes) or None,
            )
        if rows:
            df = pd.DataFrame(rows).rename(columns={
                "full_name": "Jugador", "primary_position": "Posición", "observations": "Observaciones",
                "reporter_count": "Informadores", "avg_general": "General", "rating_dispersion": "Dispersión",
                "avg_technical": "Técnica", "avg_tactical": "Táctica", "avg_physical": "Física",
                "standouts": "Destacados", "last_observed": "Última observación", "recommendation": "Decisión más repetida",
            })
            for col in ["General", "Dispersión", "Técnica", "Táctica", "Física"]:
                df[col] = df[col].map(_fmt)
            st.dataframe(df[["Jugador", "Posición", "Observaciones", "Informadores", "General", "Dispersión", "Técnica", "Táctica", "Física", "Destacados", "Decisión más repetida", "Última observación"]], use_container_width=True, hide_index=True)
        else:
            st.info("No hay resultados para los filtros seleccionados.")

    with tabs[1]:
        with session_scope() as session:
            reports = repo.list_reports(session)
        pending = [r for r in reports if r.status == "submitted"]
        approved = [r for r in reports if r.status in {"approved", "final"}]
        st.subheader("Pendientes de revisión")
        if not pending:
            st.info("No hay informes pendientes.")
        for report in pending:
            with st.expander(f"{report.match.home_team.name} - {report.match.away_team.name} · {report.reporter.full_name} · V{report.version}"):
                st.write(report.opponent_overview or "Sin resumen.")
                with session_scope() as session:
                    docs = repo.list_documents(session, report.id)
                for doc in docs:
                    try:
                        content = load_document_bytes(bucket=doc.storage_bucket, storage_path=doc.storage_path, local_path=doc.local_path)
                        with session_scope() as session:
                            filename = report_filename(session, report.id, version=doc.version, mode=doc.document_type)
                        st.download_button(f"Descargar {doc.document_type}", content, filename, "application/pdf", key=f"review_doc_{doc.id}")
                    except Exception as exc:
                        st.warning(str(exc))
                review_note = st.text_area("Nota de revisión", key=f"review_note_{report.id}")
                c1, c2 = st.columns(2)
                if c1.button("Aprobar", type="primary", key=f"approve_{report.id}"):
                    try:
                        with session_scope() as session:
                            repo.approve_report(session, report.id, user["id"], review_note or None)
                        st.success("Informe aprobado y habilitado para analíticas."); st.rerun()
                    except Exception as exc: st.error(str(exc))
                if c2.button("Devolver para corregir", key=f"return_{report.id}"):
                    if not review_note.strip():
                        st.error("Indica qué debe corregirse.")
                    else:
                        with session_scope() as session:
                            repo.return_report(session, report.id, user["id"], review_note)
                        st.success("Informe devuelto."); st.rerun()
        st.subheader("Archivo aprobado")
        if approved:
            selected = st.selectbox("Informe", [r.id for r in approved], format_func=lambda rid: next(f"{r.match.match_date.strftime('%d/%m/%Y')} · {r.match.home_team.name} - {r.match.away_team.name} · {r.reporter.full_name} · V{r.version}" for r in approved if r.id == rid))
            with session_scope() as session:
                versions = repo.list_report_versions(session, selected)
                docs = repo.list_documents(session, selected)
            for v in versions:
                st.markdown(f"**V{v.version} · {REPORT_STATUSES.get(v.status, v.status)}**")
                for doc in [d for d in docs if d.version == v.version]:
                    try:
                        content = load_document_bytes(bucket=doc.storage_bucket, storage_path=doc.storage_path, local_path=doc.local_path)
                        with session_scope() as session:
                            filename = report_filename(session, selected, version=v.version, mode=doc.document_type)
                        st.download_button(f"Descargar {doc.document_type} V{v.version}", content, filename, "application/pdf", key=f"archive_{doc.id}")
                    except Exception as exc: st.warning(str(exc))
            if user["role"] == "admin":
                reason = st.text_input("Motivo de reapertura", key=f"reopen_reason_{selected}")
                if st.button("Reabrir como nueva versión", key=f"reopen_{selected}"):
                    with session_scope() as session:
                        repo.return_report(session, selected, user["id"], reason or "Reapertura administrativa")
                    st.success("Informe reabierto; las versiones anteriores siguen intactas."); st.rerun()
        else:
            st.info("Todavía no hay informes aprobados.")

    with tabs[2]:
        with session_scope() as session:
            matches = repo.list_matches(session)
        if not matches:
            st.info("No hay partidos.")
        else:
            match_id = st.selectbox("Partido para consolidar", [m.id for m in matches], format_func=lambda mid: next(f"{m.match_date.strftime('%d/%m/%Y')} · {m.home_team.name} - {m.away_team.name}" for m in matches if m.id == mid))
            with session_scope() as session:
                consensus = repo.match_consensus(session, match_id)
                consolidation = repo.get_or_create_consolidation(session, match_id, user["id"])
                existing = {e.player_id: e for e in repo.list_consolidated_evaluations(session, consolidation.id)}
            if not consensus:
                st.info("Se necesitan informes aprobados para construir consenso.")
            else:
                st.caption("La dispersión muestra cuánto difieren las notas. Cero significa acuerdo total.")
                base = []
                for row in consensus:
                    saved = existing.get(row["player_id"])
                    base.append({
                        "player_id": row["player_id"], "Jugador": row["player_name"], "Informes": row["sample_size"],
                        "Media": round(row["average"], 2), "Dispersión": round(row["dispersion"], 2),
                        "Nota final": saved.final_rating if saved and saved.final_rating is not None else round(row["average"], 1),
                        "Decisión final": saved.final_recommendation if saved and saved.final_recommendation else (max(set(row["recommendations"]), key=row["recommendations"].count) if row["recommendations"] else "Anotar en base de datos"),
                        "Conclusión": saved.consensus_note if saved else "",
                    })
                edited = st.data_editor(pd.DataFrame(base), hide_index=True, use_container_width=True, column_config={
                    "player_id": None, "Jugador": st.column_config.TextColumn(disabled=True), "Informes": st.column_config.NumberColumn(disabled=True),
                    "Media": st.column_config.NumberColumn(disabled=True), "Dispersión": st.column_config.NumberColumn(disabled=True),
                    "Nota final": st.column_config.NumberColumn(1.0, 10.0, step=.5),
                    "Decisión final": st.column_config.SelectboxColumn(options=RECOMMENDATIONS),
                    "Conclusión": st.column_config.TextColumn(width="large"),
                })
                overview = st.text_area("Resumen consolidado", value=consolidation.overview or "")
                takeaways = st.text_area("Conclusiones para dirección deportiva", value=consolidation.key_takeaways or "")
                approve_consolidation = st.checkbox("Aprobar consolidación")
                if st.button("Guardar consolidación", type="primary"):
                    rows_to_save = [{
                        "player_id": int(r["player_id"]), "final_rating": float(r["Nota final"]) if pd.notna(r["Nota final"]) else None,
                        "final_recommendation": r["Decisión final"], "consensus_note": r["Conclusión"] or None,
                        "sample_size": int(r["Informes"]), "dispersion": float(r["Dispersión"]),
                        "confidence_summary": "Alta" if int(r["Informes"]) >= 3 and float(r["Dispersión"]) <= .75 else "Media" if int(r["Informes"]) >= 2 else "Baja",
                    } for _, r in edited.iterrows()]
                    with session_scope() as session:
                        repo.save_consolidation(session, consolidation.id, user["id"], overview or None, takeaways or None, rows_to_save, approve_consolidation)
                    st.success("Consolidación guardada."); st.rerun()

    with tabs[3]:
        with session_scope() as session:
            rows = repo.player_rankings(session, 1)
        if len(rows) < 2:
            st.info("Se necesitan al menos dos jugadores aprobados.")
        else:
            ids = [int(r["player_id"]) for r in rows]
            labels = {int(r["player_id"]): f"{r['full_name']} · {r['primary_position'] or '-'}" for r in rows}
            selected = st.multiselect("Selecciona de 2 a 4", ids, max_selections=4, format_func=lambda pid: labels[pid])
            if len(selected) >= 2:
                picked = [r for r in rows if int(r["player_id"]) in selected]
                compare = pd.DataFrame([{
                    "Jugador": r["full_name"], "Posición": r["primary_position"], "Observaciones": r["observations"],
                    "General": _fmt(r["avg_general"]), "Técnica": _fmt(r["avg_technical"]),
                    "Táctica": _fmt(r["avg_tactical"]), "Física": _fmt(r["avg_physical"]), "Dispersión": _fmt(r["rating_dispersion"]),
                } for r in picked])
                st.dataframe(compare, use_container_width=True, hide_index=True)
                numeric = compare.set_index("Jugador")[["General", "Técnica", "Táctica", "Física"]].apply(pd.to_numeric, errors="coerce")
                st.bar_chart(numeric.T)
                st.caption("Las dimensiones no evaluadas se muestran como ausencia de dato, nunca como cero.")

    with tabs[4]:
        with session_scope() as session:
            items = repo.list_follow_ups(session)
            users = repo.list_users(session, active_only=True)
            matches = repo.list_matches(session, limit=100)
            ranked = repo.player_rankings(session, 1)
        if items:
            st.dataframe(pd.DataFrame([{
                "Prioridad": f.priority, "Jugador": f.player.full_name, "Estado": f.status,
                "Responsable": f.assignee.full_name if f.assignee else "Sin asignar",
                "Próxima revisión": f.next_review_date, "Partido objetivo": f.target_match.round_name if f.target_match else "",
                "Nota": f.note, "Actualizado": f.updated_at,
            } for f in items]), use_container_width=True, hide_index=True)
        player_options = sorted({int(r["player_id"]): r["full_name"] for r in ranked}.items())
        if player_options:
            pid = st.selectbox("Jugador", [x[0] for x in player_options], format_func=lambda x: dict(player_options)[x])
            current = next((f for f in items if f.player_id == pid), None)
            c1, c2, c3 = st.columns(3)
            status = c1.selectbox("Estado", FOLLOW_UP_STATUSES, index=FOLLOW_UP_STATUSES.index(current.status) if current and current.status in FOLLOW_UP_STATUSES else 1)
            priority = c2.selectbox("Prioridad", [1, 2, 3, 4], index=(current.priority - 1) if current else 1, format_func=lambda x: {1:"1 · Alta", 2:"2 · Media", 3:"3 · Baja", 4:"4 · Archivo"}[x])
            assignee = c3.selectbox("Responsable", [None] + [u.id for u in users], index=([None] + [u.id for u in users]).index(current.assigned_to) if current and current.assigned_to in [u.id for u in users] else 0, format_func=lambda uid: "Sin asignar" if uid is None else next(u.full_name for u in users if u.id == uid))
            c4, c5 = st.columns(2)
            next_date = c4.date_input("Próxima revisión", value=current.next_review_date if current else None)
            target = c5.selectbox("Partido objetivo", [None] + [m.id for m in matches], index=([None] + [m.id for m in matches]).index(current.target_match_id) if current and current.target_match_id in [m.id for m in matches] else 0, format_func=lambda mid: "Sin partido" if mid is None else next(f"{m.match_date.strftime('%d/%m')} · {m.home_team.name}-{m.away_team.name}" for m in matches if m.id == mid))
            note = st.text_area("Nota / siguiente acción", value=current.note if current else "")
            closed_reason = st.text_area("Motivo de descarte o cierre", value=current.closed_reason if current else "")
            if st.button("Guardar seguimiento", type="primary"):
                with session_scope() as session:
                    repo.upsert_follow_up(session, pid, status, priority, note or None, user["id"], assigned_to=assignee, next_review_date=next_date, target_match_id=target, closed_reason=closed_reason or None, expected_revision=current.revision if current else None)
                st.success("Seguimiento actualizado."); st.rerun()
            if current:
                with session_scope() as session:
                    history = repo.follow_up_history(session, current.id)
                with st.expander("Historial"):
                    for h in history: st.write(f"{h.created_at.strftime('%d/%m/%Y %H:%M')} · {h.status} · {h.note or ''}")
        else:
            st.info("No hay jugadores aprobados para seguimiento.")

    with tabs[5]:
        st.subheader("Exportación analítica")
        st.write("Excel legible con rankings validados, evaluaciones, participaciones, asignaciones, seguimientos y consolidaciones.")
        if st.button("Preparar Excel", type="primary"):
            with session_scope() as session: st.session_state["analytics_export"] = analytics_export_xlsx(session)
        if "analytics_export" in st.session_state:
            st.download_button("Descargar Excel", st.session_state["analytics_export"], "postmatch_scout_2_0_analitica.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.subheader("Copia técnica restaurable")
        st.warning("Contiene datos sensibles y hashes de contraseña. Debe guardarse en una ubicación segura.")
        if st.button("Preparar backup técnico"):
            with session_scope() as session: st.session_state["technical_backup"] = technical_backup_zip(session)
        if "technical_backup" in st.session_state:
            st.download_button("Descargar backup ZIP", st.session_state["technical_backup"], "postmatch_scout_2_0_backup.zip", "application/zip")
