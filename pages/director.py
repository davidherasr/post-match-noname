from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.constants import FOLLOW_UP_STATUSES, POSITIONS, RECOMMENDATIONS, REPORT_STATUSES
from core.database import session_scope
from repositories import scouting as repo
from services.export_service import analytics_export_xlsx, technical_backup_zip
from services.report_service import report_filename
from services.storage_service import load_document_bytes
from ui.styles import page_header


def _fmt(value):
    return "Sin muestra" if value is None or pd.isna(value) else round(float(value), 2)


def _review_reports(user: dict) -> None:
    with session_scope() as session:
        reports = repo.list_reports(session)
    pending = [r for r in reports if r.status == "submitted"]
    approved = [r for r in reports if r.status in {"approved", "final"}]

    st.subheader("Pendientes de revisión")
    if not pending:
        st.success("No hay informes pendientes.")
    for report in pending:
        with st.expander(f"{report.match.home_team.name} - {report.match.away_team.name} · {report.reporter.full_name} · V{report.version}", expanded=True):
            with session_scope() as session:
                evaluations = repo.list_evaluations(session, report.id)
                docs = repo.list_documents(session, report.id)
            rival = [e for e in evaluations if e.evaluation_scope == "rival" and e.general_rating is not None]
            own = [e for e in evaluations if e.evaluation_scope == "own" and e.general_rating is not None]
            a, b, c = st.columns(3)
            a.metric("Rivales valorados", len(rival))
            b.metric("No Name valorados", len(own))
            c.metric("Destacados", len([e for e in rival if e.standout]))
            if rival:
                top = sorted(rival, key=lambda e: e.general_rating or 0, reverse=True)[:5]
                st.dataframe(pd.DataFrame([{
                    "Jugador": e.player.full_name,
                    "Nota": e.general_rating,
                    "Destacado": "Sí" if e.standout else "",
                    "Observación": e.short_note or "",
                } for e in top]), use_container_width=True, hide_index=True)
            for doc in docs:
                try:
                    content = load_document_bytes(bucket=doc.storage_bucket, storage_path=doc.storage_path, local_path=doc.local_path)
                    with session_scope() as session:
                        filename = report_filename(session, report.id, version=doc.version, mode=doc.document_type)
                    st.download_button(f"Descargar PDF {doc.document_type}", content, filename, "application/pdf", key=f"review_doc_{doc.id}")
                except Exception as exc:
                    st.warning(str(exc))
            review_note = st.text_area("Nota de revisión (opcional al aprobar)", key=f"review_note_{report.id}")
            c1, c2 = st.columns(2)
            if c1.button("Aprobar", type="primary", use_container_width=True, key=f"approve_{report.id}"):
                try:
                    with session_scope() as session:
                        repo.approve_report(session, report.id, user["id"], review_note.strip() or None)
                    st.success("Informe aprobado. Sus datos ya alimentan históricos y scouting.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if c2.button("Devolver para corregir", use_container_width=True, key=f"return_{report.id}"):
                if not review_note.strip():
                    st.error("Indica qué debe corregirse.")
                else:
                    with session_scope() as session:
                        repo.return_report(session, report.id, user["id"], review_note.strip())
                    st.success("Informe devuelto.")
                    st.rerun()

    st.subheader("Archivo aprobado")
    if not approved:
        st.info("Todavía no hay informes aprobados.")
        return
    selected = st.selectbox(
        "Abrir informe aprobado",
        [r.id for r in approved],
        format_func=lambda rid: next(
            f"{r.match.match_date.strftime('%d/%m/%Y')} · {r.match.home_team.name} - {r.match.away_team.name} · {r.reporter.full_name} · V{r.version}"
            for r in approved if r.id == rid
        ),
    )
    with session_scope() as session:
        versions = repo.list_report_versions(session, selected)
        docs = repo.list_documents(session, selected)
    for version in versions:
        st.markdown(f"**V{version.version} · {REPORT_STATUSES.get(version.status, version.status)}**")
        cols = st.columns(max(1, len([d for d in docs if d.version == version.version])))
        for col, doc in zip(cols, [d for d in docs if d.version == version.version]):
            try:
                content = load_document_bytes(bucket=doc.storage_bucket, storage_path=doc.storage_path, local_path=doc.local_path)
                with session_scope() as session:
                    filename = report_filename(session, selected, version=version.version, mode=doc.document_type)
                col.download_button(f"{doc.document_type} · V{version.version}", content, filename, "application/pdf", key=f"archive_{doc.id}")
            except Exception as exc:
                col.warning(str(exc))
    if user["role"] == "admin":
        with st.expander("Reabrir como nueva versión"):
            reason = st.text_input("Motivo", key=f"reopen_reason_{selected}")
            if st.button("Reabrir", key=f"reopen_{selected}"):
                with session_scope() as session:
                    repo.return_report(session, selected, user["id"], reason.strip() or "Reapertura administrativa")
                st.success("Informe reabierto. Las versiones anteriores permanecen inmutables.")
                st.rerun()


def _followups(user: dict) -> None:
    with session_scope() as session:
        items = repo.list_follow_ups(session)
        users = repo.list_users(session, active_only=True)
        matches = repo.list_matches(session, limit=100)
        ranked = repo.player_rankings(session, 1)

    active = [f for f in items if f.status not in {"Descartado", "Cerrado"}]
    st.subheader("Agenda de seguimiento")
    if active:
        st.dataframe(pd.DataFrame([{
            "Prioridad": f.priority,
            "Jugador": f.player.full_name,
            "Estado": f.status,
            "Responsable": f.assignee.full_name if f.assignee else "Sin asignar",
            "Próxima revisión": f.next_review_date,
            "Nota": f.note or "",
        } for f in active]), use_container_width=True, hide_index=True)
    else:
        st.info("No hay seguimientos activos.")

    player_options = sorted({int(r["player_id"]): r["full_name"] for r in ranked}.items())
    if not player_options:
        st.caption("Los jugadores aparecerán aquí cuando exista alguna evaluación rival aprobada.")
        return
    pid = st.selectbox("Jugador", [x[0] for x in player_options], format_func=lambda x: dict(player_options)[x])
    current = next((f for f in items if f.player_id == pid), None)
    c1, c2, c3 = st.columns(3)
    status = c1.selectbox("Estado", FOLLOW_UP_STATUSES, index=FOLLOW_UP_STATUSES.index(current.status) if current and current.status in FOLLOW_UP_STATUSES else 1)
    priority = c2.selectbox("Prioridad", [1, 2, 3, 4], index=(current.priority - 1) if current else 1, format_func=lambda x: {1:"Alta", 2:"Media", 3:"Baja", 4:"Archivo"}[x])
    assignee_ids = [None] + [u.id for u in users]
    assignee = c3.selectbox(
        "Responsable",
        assignee_ids,
        index=assignee_ids.index(current.assigned_to) if current and current.assigned_to in assignee_ids else 0,
        format_func=lambda uid: "Sin asignar" if uid is None else next(u.full_name for u in users if u.id == uid),
    )
    c4, c5 = st.columns(2)
    next_date = c4.date_input("Próxima revisión", value=current.next_review_date if current else None)
    match_ids = [None] + [m.id for m in matches]
    target = c5.selectbox(
        "Partido objetivo",
        match_ids,
        index=match_ids.index(current.target_match_id) if current and current.target_match_id in match_ids else 0,
        format_func=lambda mid: "Sin partido" if mid is None else next(f"{m.match_date.strftime('%d/%m')} · {m.home_team.name}-{m.away_team.name}" for m in matches if m.id == mid),
    )
    note = st.text_area("Siguiente acción / nota", value=current.note if current else "")
    closed_reason = st.text_area("Motivo de cierre o descarte", value=current.closed_reason if current else "")
    if st.button("Guardar seguimiento", type="primary", use_container_width=True):
        with session_scope() as session:
            repo.upsert_follow_up(
                session,
                pid,
                status,
                priority,
                note.strip() or None,
                user["id"],
                assigned_to=assignee,
                next_review_date=next_date,
                target_match_id=target,
                closed_reason=closed_reason.strip() or None,
                expected_revision=current.revision if current else None,
            )
        st.success("Seguimiento actualizado.")
        st.rerun()
    if current:
        with session_scope() as session:
            history = repo.follow_up_history(session, current.id)
        with st.expander("Historial del seguimiento"):
            for h in history:
                st.write(f"{h.created_at.strftime('%d/%m/%Y %H:%M')} · {h.status} · {h.note or ''}")


def _players_decisions() -> None:
    with session_scope() as session:
        seasons = repo.list_seasons(session)
        competitions = repo.list_competitions(session)
        teams = [t for t in repo.list_teams(session) if not t.is_own_team]
        reporters = [u for u in repo.list_users(session, active_only=True) if u.role in {"reporter", "admin", "director"}]

    top = st.columns(3)
    position = top[0].selectbox("Posición", ["Todas"] + POSITIONS)
    minimum = top[1].number_input("Mínimo observaciones", 1, 50, 1)
    minimum_minutes = top[2].number_input("Mínimo minutos", 0, 120, 0)

    with st.expander("Filtros avanzados"):
        r1 = st.columns(4)
        season_id = r1[0].selectbox("Temporada", [None] + [s.id for s in seasons], format_func=lambda sid: "Todas" if sid is None else next(s.name for s in seasons if s.id == sid))
        competition_id = r1[1].selectbox("Competición", [None] + [c.id for c in competitions], format_func=lambda cid: "Todas" if cid is None else next(c.name for c in competitions if c.id == cid))
        team_id = r1[2].selectbox("Equipo", [None] + [t.id for t in teams], format_func=lambda tid: "Todos" if tid is None else next(t.name for t in teams if t.id == tid))
        reporter_id = r1[3].selectbox("Informador", [None] + [u.id for u in reporters], format_func=lambda uid: "Todos" if uid is None else next(u.full_name for u in reporters if u.id == uid))
        r2 = st.columns(2)
        date_from = r2[0].date_input("Desde", value=None)
        date_to = r2[1].date_input("Hasta", value=None)

    with session_scope() as session:
        rows = repo.player_rankings(
            session,
            int(minimum),
            position,
            None,
            season_id=season_id,
            competition_id=competition_id,
            team_id=team_id,
            reporter_id=reporter_id,
            date_from=date_from,
            date_to=date_to,
            minimum_minutes=int(minimum_minutes) or None,
        )
    if not rows:
        st.info("No hay resultados.")
        return
    st.dataframe(pd.DataFrame([{
        "Jugador": r["full_name"],
        "Posición": r["primary_position"] or "-",
        "Obs.": r["observations"],
        "Media": round(r["avg_general"], 2),
        "Dispersión": round(r["rating_dispersion"], 2),
        "Destacados": r["standouts"],
        "Última": r["last_observed"],
    } for r in rows]), use_container_width=True, hide_index=True)


def _consensus(user: dict) -> None:
    with session_scope() as session:
        matches = repo.list_matches(session)
    if not matches:
        st.info("No hay partidos.")
        return
    match_id = st.selectbox(
        "Partido",
        [m.id for m in matches],
        format_func=lambda mid: next(f"{m.match_date.strftime('%d/%m/%Y')} · {m.home_team.name} - {m.away_team.name}" for m in matches if m.id == mid),
    )
    with session_scope() as session:
        consensus = repo.match_consensus(session, match_id)
        consolidation = repo.get_or_create_consolidation(session, match_id, user["id"])
        existing = {e.player_id: e for e in repo.list_consolidated_evaluations(session, consolidation.id)}
    if not consensus:
        st.info("Se necesitan informes aprobados para construir consenso.")
        return
    base = []
    for row in consensus:
        saved = existing.get(row["player_id"])
        base.append({
            "player_id": row["player_id"],
            "Jugador": row["player_name"],
            "Informes": row["sample_size"],
            "Media": round(row["average"], 2),
            "Dispersión": round(row["dispersion"], 2),
            "Nota final": saved.final_rating if saved and saved.final_rating is not None else round(row["average"], 1),
            "Decisión final": saved.final_recommendation if saved and saved.final_recommendation else "Anotar en base de datos",
            "Conclusión": saved.consensus_note if saved else "",
        })
    edited = st.data_editor(
        pd.DataFrame(base),
        hide_index=True,
        use_container_width=True,
        disabled=["player_id", "Jugador", "Informes", "Media", "Dispersión"],
        column_config={
            "player_id": None,
            "Nota final": st.column_config.NumberColumn(min_value=1.0, max_value=10.0, step=.1),
            "Decisión final": st.column_config.SelectboxColumn(options=RECOMMENDATIONS),
            "Conclusión": st.column_config.TextColumn(width="large"),
        },
    )
    approve = st.checkbox("Aprobar consolidación")
    if st.button("Guardar consenso", type="primary", use_container_width=True):
        rows_to_save = [{
            "player_id": int(r["player_id"]),
            "final_rating": float(r["Nota final"]) if pd.notna(r["Nota final"]) else None,
            "final_recommendation": r["Decisión final"],
            "consensus_note": r["Conclusión"] or None,
            "sample_size": int(r["Informes"]),
            "dispersion": float(r["Dispersión"]),
            "confidence_summary": "Alta" if int(r["Informes"]) >= 3 and float(r["Dispersión"]) <= .75 else "Media" if int(r["Informes"]) >= 2 else "Baja",
        } for _, r in edited.iterrows()]
        with session_scope() as session:
            repo.save_consolidation(session, consolidation.id, user["id"], None, None, rows_to_save, approve)
        st.success("Consenso guardado.")
        st.rerun()


def _tools() -> None:
    st.subheader("Comparar jugadores")
    with session_scope() as session:
        rows = repo.player_rankings(session, 1)
    if len(rows) >= 2:
        ids = [int(r["player_id"]) for r in rows]
        labels = {int(r["player_id"]): f"{r['full_name']} · {r['primary_position'] or '-'}" for r in rows}
        selected = st.multiselect("Selecciona de 2 a 4", ids, max_selections=4, format_func=lambda pid: labels[pid])
        if len(selected) >= 2:
            picked = [r for r in rows if int(r["player_id"]) in selected]
            st.dataframe(pd.DataFrame([{
                "Jugador": r["full_name"], "Posición": r["primary_position"], "Observaciones": r["observations"],
                "General": _fmt(r["avg_general"]), "Dispersión": _fmt(r["rating_dispersion"]),
            } for r in picked]), use_container_width=True, hide_index=True)
    else:
        st.info("Se necesitan al menos dos jugadores aprobados para comparar.")

    st.divider()
    st.subheader("Exportación")
    if st.button("Preparar Excel analítico"):
        with session_scope() as session:
            st.session_state["analytics_export"] = analytics_export_xlsx(session)
    if "analytics_export" in st.session_state:
        st.download_button("Descargar Excel", st.session_state["analytics_export"], "noname_postmatch_3_0_analitica.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.subheader("Backup técnico")
    st.warning("Contiene datos sensibles y hashes de contraseña. Guárdalo en una ubicación segura.")
    if st.button("Preparar backup técnico"):
        with session_scope() as session:
            st.session_state["technical_backup"] = technical_backup_zip(session)
    if "technical_backup" in st.session_state:
        st.download_button("Descargar backup ZIP", st.session_state["technical_backup"], "noname_postmatch_3_0_backup.zip", "application/zip")


def render(user: dict) -> None:
    page_header("Dirección deportiva", "Primero decisiones y seguimiento; las estadísticas quedan como herramienta secundaria.")
    tabs = st.tabs(["Ahora", "Revisar informes", "Seguimiento", "Jugadores", "Consenso", "Herramientas"])

    with tabs[0]:
        with session_scope() as session:
            submitted = repo.list_reports(session, status="submitted", limit=20)
            highlights = repo.recent_rival_highlights(session, limit=12, minimum_rating=8.0)
            repeated = repo.player_rankings(session, min_observations=2, limit=10)
            followups = [f for f in repo.list_follow_ups(session) if f.status not in {"Descartado", "Cerrado"}]
        c1, c2, c3 = st.columns(3)
        c1.metric("Informes por revisar", len(submitted))
        c2.metric("Seguimientos activos", len(followups))
        c3.metric("Observados varias veces", len(repeated))
        left, right = st.columns(2)
        with left:
            st.subheader("Han llamado la atención")
            if highlights:
                for item in highlights[:8]:
                    ev, player, match = item["evaluation"], item["player"], item["match"]
                    with st.container(border=True):
                        st.markdown(f"**{player.full_name} · {ev.general_rating:.1f}**")
                        st.caption(f"{match.match_date.strftime('%d/%m/%Y')} · {match.home_team.name} - {match.away_team.name}")
                        if ev.short_note:
                            st.write(ev.short_note)
            else:
                st.info("No hay notas ≥ 8 aprobadas.")
        with right:
            st.subheader("Ya han aparecido varias veces")
            if repeated:
                st.dataframe(pd.DataFrame([{
                    "Jugador": r["full_name"], "Obs.": r["observations"], "Media": round(r["avg_general"], 2), "Última": r["last_observed"]
                } for r in repeated[:8]]), use_container_width=True, hide_index=True)
            else:
                st.info("Todavía no hay perfiles repetidos.")

    with tabs[1]:
        _review_reports(user)
    with tabs[2]:
        _followups(user)
    with tabs[3]:
        _players_decisions()
    with tabs[4]:
        _consensus(user)
    with tabs[5]:
        _tools()
