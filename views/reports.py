from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from core.constants import ASSIGNMENT_STATUSES, PDF_MODES, REPORT_STATUSES
from core.database import session_scope
from core.evaluation_rules import AUTO_STANDOUT_THRESHOLD
from core.performance import measure
from core.permissions import can_direct, can_report, can_track_players
from core.navigation import request_navigation
from core.score_picker import rating_choices, rating_from_choice
from core.utils import safe_html
from repositories import scouting as repo
from repositories import tracking as tracking_repo
from repositories import observation_requests as observation_repo
from services.report_service import generate_report_pdf, report_filename
from services.storage_service import load_document_bytes, save_pdf
from ui.helpers import match_label
from ui.styles import page_header

REPORTS_PAGE_API_VERSION = "4.4.3"



def _set_quick_rating(key: str, value: float) -> None:
    st.session_state[key] = float(value)


def _render_exact_rating(key: str, player_name: str, *, read_only: bool) -> None:
    """One-click numeric rating; legacy fractional values stay intact on edit."""
    current = float(st.session_state.get(key, 0.0) or 0.0)
    if read_only:
        st.metric("Nota", "Sin evaluar" if current == 0 else f"{current:g}".replace(".", ","))
        return
    options, default = rating_choices(current)
    selected = st.pills(
        f"Nota · {player_name}", options, default=default, key=key + "_choice",
        help="Pulsa una nota del 1 al 10. Sin evaluar no cuenta como 0 en las medias.",
        label_visibility="collapsed", selection_mode="single",
    )
    st.session_state[key] = rating_from_choice(selected)


def _minutes_played(participation) -> int:
    return max(0, int(participation.minute_out or 90) - int(participation.minute_in or 0))


def _participation_meta(participation) -> str:
    role = "Titular" if participation.starter else f"Entró {participation.minute_in}'"
    if participation.minute_out and participation.minute_out < 90:
        role += f" · salió {participation.minute_out}'"
    position = participation.position or participation.player.primary_position or "Sin posición"
    return f"{position} · {_minutes_played(participation)} min · {role}"


def _evaluation_defaults(existing) -> tuple[float, str, bool, bool]:
    rating = float(existing.general_rating) if existing and existing.general_rating is not None else 0.0
    note = existing.short_note if existing and existing.short_note else ""
    standout = bool(existing and existing.standout) or rating >= AUTO_STANDOUT_THRESHOLD
    pdf_include = bool(existing.pdf_include) if existing else True
    return rating, note, standout, pdf_include


def _ensure_eval_state(report_id: int, part, existing) -> str:
    prefix = f"eval33_{report_id}_{part.player_id}_"
    rating, note, standout, pdf_include = _evaluation_defaults(existing)
    defaults = {"rating": rating, "note": note, "standout": standout, "pdf": pdf_include}
    for suffix, value in defaults.items():
        st.session_state.setdefault(prefix + suffix, value)
    return prefix


def _build_bulk_row(participation, team_id: int, existing, prefix: str) -> dict:
    rating = float(st.session_state.get(prefix + "rating", 0.0) or 0.0)
    note = str(st.session_state.get(prefix + "note", "") or "").strip() or None
    # Daily reporting has no manual highlight/PDF toggles. These values are
    # deterministic from the rating and DD may correct exceptional cases later.
    standout = rating >= AUTO_STANDOUT_THRESHOLD
    pdf_include = rating > 0
    minutes = _minutes_played(participation)
    observation_status = "evaluated" if rating > 0 else ("insufficient" if minutes < 10 else "not_observed")
    return {
        "player_id": int(participation.player_id), "team_id": int(team_id),
        "participation_id": int(participation.id), "expected_revision": existing.revision if existing else None,
        "observation_status": observation_status,
        "general_rating": rating if rating > 0 else None, "short_note": note,
        "standout": standout if rating > 0 else False, "pdf_include": pdf_include,
        "recommendation": None, "confidence": None,
    }


def _workspace_key(report_id: int) -> str:
    return f"report_workspace_33_{report_id}"


def _invalidate_workspace(report_id: int) -> None:
    st.session_state.pop(_workspace_key(report_id), None)


def _load_report_editor(report_id: int):
    key = _workspace_key(report_id)
    payload = st.session_state.get(key)
    if payload is None:
        with measure("Abrir informe · workspace", "report"):
            with session_scope() as session:
                payload = repo.load_report_workspace(session, report_id)
        st.session_state[key] = payload
    if not payload:
        return None, [], []
    return payload["report"], payload["participations"], payload["evaluations"]


def _saved_snapshot_key(report_id: int, team_id: int) -> str:
    return f"eval_saved_snapshot_34_{report_id}_{team_id}"


def _dirty_key(report_id: int, team_id: int) -> str:
    return f"eval_dirty_34_{report_id}_{team_id}"


def _snapshot_from_evaluations(report_id: int, players: list, evaluations: dict) -> dict[int, tuple]:
    snapshot: dict[int, tuple] = {}
    for part in players:
        existing = evaluations.get(part.player_id)
        rating, note, standout, pdf_include = _evaluation_defaults(existing)
        snapshot[int(part.player_id)] = (round(float(rating), 1), str(note or "").strip(), bool(standout), bool(pdf_include))
        _ensure_eval_state(report_id, part, existing)
    return snapshot


def _snapshot_from_widgets(report_id: int, players: list) -> dict[int, tuple]:
    snapshot: dict[int, tuple] = {}
    for part in players:
        prefix = f"eval33_{report_id}_{part.player_id}_"
        snapshot[int(part.player_id)] = (
            round(float(st.session_state.get(prefix + "rating", 0.0) or 0.0), 1),
            str(st.session_state.get(prefix + "note", "") or "").strip(),
            bool(st.session_state.get(prefix + "standout", False)),
            bool(st.session_state.get(prefix + "pdf", True)),
        )
    return snapshot


def _restore_widget_snapshot(report_id: int, snapshot: dict[int, tuple]) -> None:
    for player_id, values in snapshot.items():
        prefix = f"eval33_{report_id}_{player_id}_"
        rating, note, standout, pdf_include = values
        st.session_state[prefix + "rating"] = rating
        st.session_state[prefix + "note"] = note
        st.session_state[prefix + "standout"] = standout
        st.session_state[prefix + "pdf"] = pdf_include


@st.fragment
def _render_team_form(report, players: list, evaluations: dict, user: dict, *, own_team: bool, read_only: bool, next_stage: str | None = None) -> None:
    """Compact evaluation fragment.

    Widget interaction only reruns this fragment. The already-loaded workspace stays in
    memory; persistence only occurs when the user explicitly saves the block.
    """
    if not players:
        st.warning("No hay jugadores cargados para este equipo.")
        return
    team_id = report.own_team_id if own_team else report.rival_team_id
    team_name = report.own_team.name if own_team else report.rival_team.name
    saved_key = _saved_snapshot_key(report.id, team_id)
    dirty_key = _dirty_key(report.id, team_id)
    if saved_key not in st.session_state:
        st.session_state[saved_key] = _snapshot_from_evaluations(report.id, players, evaluations)
    else:
        # Ensure widget state exists after a browser/session refresh.
        for part in players:
            _ensure_eval_state(report.id, part, evaluations.get(part.player_id))

    saved_snapshot = st.session_state.get(saved_key, {})
    evaluated_saved = sum(1 for values in saved_snapshot.values() if float(values[0] or 0.0) > 0)
    pending_saved = max(0, len(players) - evaluated_saved)
    progress = evaluated_saved / len(players) if players else 0.0
    st.caption(f"{team_name} · {evaluated_saved} valoraciones guardadas de {len(players)} participantes conocidos. Puntúa solo a quien hayas podido evaluar.")
    only_pending = st.toggle(
        "Solo pendientes", value=False, key=f"only_pending_341_{report.id}_{team_id}",
        help="Muestra únicamente jugadores que todavía no estaban valorados en el último guardado.",
    )

    pending_ids = {pid for pid, values in saved_snapshot.items() if float(values[0] or 0.0) <= 0}
    visible_players = [p for p in players if (not only_pending or int(p.player_id) in pending_ids)]
    if only_pending and not visible_players:
        st.success("Todos los jugadores de este equipo tienen nota guardada.")

    for heading, group in [("Titulares", [p for p in visible_players if p.starter]), ("Suplentes utilizados", [p for p in visible_players if not p.starter])]:
        if not group:
            continue
        st.markdown(f"#### {heading}")
        for part in group:
            existing = evaluations.get(part.player_id)
            prefix = _ensure_eval_state(report.id, part, existing)
            display_name = part.player.display_name or part.player.full_name
            shirt = f"#{part.shirt_number}" if part.shirt_number is not None else "—"
            st.markdown(
                f'<div class="pm-eval-name"><strong>{safe_html(display_name)}</strong> <span>{safe_html(shirt)} · {safe_html(_participation_meta(part))}</span></div>',
                unsafe_allow_html=True,
            )
            rating_col, note_col = st.columns([1.15, 1.5], gap="small")
            with rating_col:
                _render_exact_rating(prefix + "rating", display_name, read_only=read_only)
            if float(st.session_state.get(prefix + "rating", 0.0) or 0.0) <= 0 and _minutes_played(part) < 10:
                rating_col.caption("Minutos insuficientes · no computará como valoración")
            note_col.text_input(
                f"Observación · {display_name} (opcional)", key=prefix + "note", disabled=read_only,
                placeholder="Comentario opcional…", label_visibility="collapsed",
            )
            st.markdown('<div class="pm-eval-separator"></div>', unsafe_allow_html=True)

    current_snapshot = _snapshot_from_widgets(report.id, players)
    dirty = current_snapshot != saved_snapshot
    st.session_state[dirty_key] = dirty
    if dirty and not read_only:
        st.warning(f"Tienes cambios sin guardar en {team_name}.")
    elif not read_only:
        st.caption(f"✓ {team_name} está sincronizado con la base de datos.")

    if read_only:
        return
    a, b = st.columns([3, 1])
    submit_label = "Guardar y continuar" if next_stage else f"Guardar notas · {team_name}"
    submitted = a.button(submit_label, type="primary", use_container_width=True, disabled=not dirty, key=f"save_eval_34_{report.id}_{team_id}")
    discard = b.button("Deshacer", use_container_width=True, disabled=not dirty, key=f"discard_eval_34_{report.id}_{team_id}")

    if discard:
        _restore_widget_snapshot(report.id, saved_snapshot)
        st.session_state[dirty_key] = False
        st.rerun(scope="fragment")

    if submitted:
        rows = [_build_bulk_row(part, team_id, evaluations.get(part.player_id), f"eval33_{report.id}_{part.player_id}_") for part in players]
        try:
            with st.spinner(f"Guardando {team_name}..."):
                with measure(f"Guardar bloque · {team_name}", "report"):
                    with session_scope() as session:
                        saved = repo.bulk_upsert_evaluations_fast(session, report.id, rows, actor_id=user["id"])
            st.session_state[saved_key] = current_snapshot
            st.session_state[dirty_key] = False
            st.session_state[f"save_status_{report.id}_{team_id}"] = f"{team_name}: {saved} jugadores · {datetime.now().strftime('%H:%M:%S')}"
            _invalidate_workspace(report.id)
            if next_stage:
                st.session_state[f"report_stage_{report.id}"] = next_stage
                st.rerun()
            st.success(st.session_state[f"save_status_{report.id}_{team_id}"])
        except Exception as exc:
            st.error(f"No se ha guardado el bloque: {exc}")


def _store_one_document(session, report_id: int, version_obj, mode: str) -> str:
    pdf = generate_report_pdf(session, report_id, version=version_obj.version, mode=mode)
    stored = save_pdf(report_id, version_obj.version, pdf, document_type=mode)
    repo.save_document(
        session, report_id, version_obj.version, report_version_id=version_obj.id, document_type=mode,
        storage_bucket=stored.get("storage_bucket"), storage_path=stored.get("storage_path"), local_path=stored.get("local_path"),
        checksum=stored.get("checksum"), size_bytes=stored.get("size_bytes"), storage_status=str(stored.get("storage_status")),
        error_message=stored.get("error_message"),
    )
    return str(stored.get("storage_status"))


def _render_finish(report, evaluation_list: list, report_id: int, user: dict, read_only: bool) -> None:
    valid_rival = [e for e in evaluation_list if e.evaluation_scope == "rival" and e.observation_status == "evaluated" and e.general_rating is not None and e.general_rating > 0]
    valid_own = [e for e in evaluation_list if e.evaluation_scope == "own" and e.observation_status == "evaluated" and e.general_rating is not None and e.general_rating > 0]
    valid_players = valid_rival + valid_own
    context_notes = (report.own_team_note, report.opponent_overview, report.key_takeaways)
    has_context = any(len(str(value or "").strip()) >= 10 for value in context_notes)
    has_rating = any(value is not None and value > 0 for value in (report.own_team_rating, report.rival_team_rating))
    has_note = any(len(str(e.short_note or "").strip()) >= 5 for e in evaluation_list)
    errors = [] if valid_players or has_rating or has_context or has_note else [
        "Deja al menos una valoración o un apunte real antes de entregar."]
    if not valid_own and not read_only:
        st.caption("No hay notas individuales propias. Son opcionales si has dejado una lectura real.")
    if not valid_rival and not read_only:
        st.caption("No hay notas individuales del rival. Puedes entregar una lectura colectiva.")
    metrics = st.columns(4)
    metrics[0].metric("Rivales", len(valid_rival)); metrics[1].metric("Propios", len(valid_own))
    metrics[2].metric("Destacados", len([e for e in valid_rival + valid_own if e.standout])); metrics[3].metric("Versión", f"V{report.version}")
    if errors and not read_only:
        st.warning(" · ".join(errors))

    st.markdown("### Lectura global del partido")
    st.caption("La nota de No Name mide nuestro rendimiento colectivo. La del rival mide su actuación en este partido; no equivale a iniciar seguimiento de ningún jugador.")
    if read_only:
        c1, c2 = st.columns(2)
        c1.metric("No Name", "—" if report.own_team_rating is None else f"{report.own_team_rating:.1f}")
        c2.metric(report.rival_team.name, "—" if report.rival_team_rating is None else f"{report.rival_team_rating:.1f}")
        if report.own_team_note:
            st.markdown(f"**Lectura No Name:** {report.own_team_note}")
        if report.opponent_overview:
            st.markdown(f"**Lectura rival:** {report.opponent_overview}")
        if report.key_takeaways:
            st.markdown(f"**Conclusiones:** {report.key_takeaways}")
    else:
        with st.form(f"global_reading_42_{report_id}"):
            c1, c2 = st.columns(2)
            own_options, own_default = rating_choices(report.own_team_rating)
            rival_options, rival_default = rating_choices(report.rival_team_rating)
            own_choice = c1.pills("Nota No Name", own_options, default=own_default,
                                  selection_mode="single", help="Sin evaluar no cuenta como nota cero.")
            rival_choice = c2.pills(f"Nota {report.rival_team.name}", rival_options, default=rival_default,
                                    selection_mode="single", help="Sin evaluar no cuenta como nota cero.")
            own_rating = rating_from_choice(own_choice)
            rival_rating = rating_from_choice(rival_choice)
            own_note = st.text_area("Lectura No Name", value=report.own_team_note or "", height=80, placeholder="Qué hicimos bien, qué nos costó, sensaciones colectivas...")
            rival_note = st.text_area("Lectura rival", value=report.opponent_overview or "", height=80, placeholder="Qué propuso el rival y cómo nos condicionó...")
            takeaways = st.text_area("Conclusiones", value=report.key_takeaways or "", height=80, placeholder="2-3 ideas que merece la pena conservar")
            save_global = st.form_submit_button("Guardar lectura global", use_container_width=True)
        if save_global:
            try:
                with session_scope() as session:
                    repo.save_report_summary(
                        session, report_id, rival_level=report.rival_level, opponent_overview=rival_note,
                        own_team_note=own_note, key_takeaways=takeaways, standout_player_id=report.standout_player_id,
                        actor_id=user["id"], expected_revision=report.revision,
                        own_team_rating=own_rating, rival_team_rating=rival_rating,
                    )
                _invalidate_workspace(report_id)
                st.success("Lectura global guardada.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if not read_only:
        selected_tracking = []
        if can_track_players(user) and valid_rival:
            eligible_by_id = {int(e.id): e for e in valid_rival}
            selected_tracking = st.multiselect(
                "Ampliar seguimiento individual (opcional)", list(eligible_by_id), default=[],
                format_func=lambda eid: f"{eligible_by_id[eid].player.display_name or eligible_by_id[eid].player.full_name} · {eligible_by_id[eid].general_rating:g}/10",
                key=f"optin_follow_443_{report_id}",
                help="Nadie está marcado por defecto. Reutiliza la nota de este partido, sin duplicarla.")
        st.caption("Revisa el resumen antes de incorporar el informe. Guarda cualquier cambio de la lectura global antes de entregar.")
        c1, c2 = st.columns(2)
        if c1.button("← Revisar No Name", use_container_width=True):
            st.session_state[f"report_stage_{report_id}"] = "own"; st.rerun()
        if c2.button("← Revisar Rival", use_container_width=True):
            st.session_state[f"report_stage_{report_id}"] = "rival"; st.rerun()
        confirm_key = f"confirm_submit_38_{report_id}"
        if not st.session_state.get(confirm_key):
            if st.button("Entregar informe", type="primary", disabled=bool(errors), use_container_width=True, key=f"submit_report_38_{report_id}"):
                st.session_state[confirm_key] = True
                st.rerun()
        else:
            st.warning("¿Incorporar este informe? Se añadirá inmediatamente a las estadísticas. Una corrección posterior requiere reapertura autorizada y motivo registrado.")
            a,b=st.columns(2)
            if a.button("Cancelar",use_container_width=True,key=f"cancel_submit_38_{report_id}"):
                st.session_state.pop(confirm_key,None); st.rerun()
            if b.button("Sí, entregar",type="primary",use_container_width=True,key=f"confirm_submit_button_38_{report_id}"):
                try:
                    with st.spinner("Entregando informe..."):
                        with measure("Entregar informe", "report"):
                            with session_scope() as session:
                                repo.submit_report(session, report_id, user["id"])
                                for evaluation_id in selected_tracking:
                                    tracking_repo.enrich_postmatch_evaluation(
                                        session, evaluation_id=int(evaluation_id), author_id=user["id"])
                    st.session_state.pop(confirm_key,None)
                    _invalidate_workspace(report_id)
                    st.session_state["report_submission_notice"] = {
                        "match_id": int(report.match_id),
                        "title": f"{report.match.home_team.name} – {report.match.away_team.name}",
                    }
                    st.session_state["_pending_report_ui_cleanup"] = int(report_id)
                    st.session_state.pop("postmatch_tracking_wizard", None)
                    st.session_state.pop("match_hub_mode", None)
                    st.session_state.pop("workspace_match_id", None)
                    st.session_state.pop("archive_open_report_33", None)
                    request_navigation("Inicio")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
    else:
        st.success(f"Informe bloqueado: {REPORT_STATUSES.get(report.status, report.status)}.")
        if report.status == "submitted":
            st.caption('Este informe conserva su estado histórico de entrega.')


def _render_documents(report_id: int) -> None:
    with measure("Cargar documentos", "documents"):
        with session_scope() as session:
            versions = repo.list_report_versions(session, report_id)
            documents = repo.list_documents(session, report_id)
    if not versions:
        st.info("Todavía no existe ninguna versión entregada.")
        return
    for version_obj in versions:
        st.markdown(f"**V{version_obj.version} · {REPORT_STATUSES.get(version_obj.status, version_obj.status)} · {version_obj.created_at.strftime('%d/%m/%Y %H:%M')}**")
        docs_by_type = {d.document_type: d for d in documents if d.version == version_obj.version}
        if "full" not in docs_by_type and st.button(f"Generar PDF Completo · V{version_obj.version}", key=f"generate_full_{report_id}_{version_obj.version}", use_container_width=True):
            try:
                with measure("Generar PDF completo", "pdf"):
                    with session_scope() as session:
                        fresh_version = repo.get_report_version(session, report_id, version_obj.version)
                        status = _store_one_document(session, report_id, fresh_version, "full")
                st.success(f"PDF Completo: {status}"); st.rerun()
            except Exception as exc:
                st.error(str(exc))
        for mode in ("executive", "full"):
            doc = docs_by_type.get(mode)
            if not doc:
                continue
            with st.container(border=True):
                st.markdown(f"**{PDF_MODES.get(mode, mode)}** · {doc.storage_status}")
                if doc.error_message:
                    st.error(doc.error_message); continue
                try:
                    content = load_document_bytes(bucket=doc.storage_bucket, storage_path=doc.storage_path, local_path=doc.local_path)
                    with session_scope() as session:
                        filename = report_filename(session, report_id, version=doc.version, mode=doc.document_type)
                    st.download_button(f"Descargar {PDF_MODES.get(mode, mode)}", content, filename, "application/pdf", key=f"doc_{doc.id}", use_container_width=True)
                except Exception as exc:
                    st.warning(str(exc))


def _finish_tracking_step(report_id: int) -> None:
    st.session_state.pop("postmatch_tracking_wizard", None)
    st.session_state.pop("match_hub_mode", None)
    st.session_state.pop("workspace_match_id", None)
    st.session_state.pop("archive_open_report_33", None)
    request_navigation("Inicio")
    st.rerun()


def _render_postmatch_tracking_step(report_id: int, user: dict) -> None:
    """Optional one-time post-delivery enrichment; a selection is never automatic."""
    try:
        with session_scope() as session:
            candidates = tracking_repo.report_tracking_candidates(session, report_id, user["id"])
            existing = {ev.id: tracking_repo.match_observations(session, ev.player_id, user["id"], ev.report.match_id)
                        for ev in candidates}
    except Exception as exc:
        st.error(str(exc))
        if st.button("Volver a Inicio", key=f"track_invalid_{report_id}"):
            _finish_tracking_step(report_id)
        return
    st.markdown("## Seguimiento individual · opcional")
    st.success("El postpartido ya está entregado e incorporado. No tienes que volver a puntuar a ningún jugador.")
    st.caption("Selecciona expresamente cualquier jugador que quieras seguir. Una nota alta nunca lo marca por ti.")
    by_id = {ev.id: ev for ev in candidates}
    selected = st.multiselect("Jugadores a seguir", list(by_id), default=[],
            format_func=lambda eid: f"{by_id[eid].player.display_name or by_id[eid].player.full_name} · {by_id[eid].general_rating:g}/10",
            help="Las notas y los comentarios del postpartido se reutilizan: no se crea otra valoración del partido.",
            key=f"track_choices_442_{report_id}")
    with st.form(f"postmatch_tracking_step_442_{report_id}"):
        details = {}
        for eid in selected:
            ev = by_id[eid]
            previous = next((o for o in existing[eid] if o.player_evaluation_id == eid), None)
            previous = previous or (existing[eid][0] if existing[eid] else None)
            with st.container(border=True):
                st.markdown(f"**{ev.player.display_name or ev.player.full_name} · {ev.general_rating:g}/10**")
                if len(existing[eid]) > 1:
                    st.warning("Hay observaciones repetidas en el histórico. Se reutilizará la existente; DD puede resolver los duplicados.")
                summary = st.text_area("Conclusión del seguimiento", value=(previous.summary if previous and previous.summary else ev.short_note or ""),
                    key=f"follow_summary_442_{report_id}_{eid}", height=90)
                strengths = st.text_area("Fortalezas", value=previous.strengths or "" if previous else "",
                    key=f"follow_strength_442_{report_id}_{eid}", height=60)
                weaknesses = st.text_area("Dudas / riesgos", value=previous.weaknesses or "" if previous else "",
                    key=f"follow_weak_442_{report_id}_{eid}", height=60)
                action_options = ["Sin conclusión", "Volver a ver", "Seguimiento", "Prioritario", "Descartado"]
                chosen = previous.recommendation if previous and previous.recommendation in action_options else "Sin conclusión"
                action = st.selectbox("Siguiente acción propuesta", action_options,
                    index=action_options.index(chosen), key=f"follow_next_442_{report_id}_{eid}")
                details[eid] = (summary, strengths, weaknesses, action)
        save = st.form_submit_button("Guardar seguimientos y volver a Inicio", type="primary", use_container_width=True)
    if save:
        try:
            with session_scope() as session:
                for eid in selected:
                    summary, strengths, weaknesses, action = details[eid]
                    tracking_repo.enrich_postmatch_evaluation(session, evaluation_id=eid, author_id=user["id"],
                        summary=summary, strengths=strengths, weaknesses=weaknesses, recommendation=action)
            st.session_state["tracking_saved_notice_442"] = f"Seguimiento guardado para {len(selected)} jugador(es)."
            _finish_tracking_step(report_id)
        except Exception as exc:
            st.error(f"No se han guardado los seguimientos: {exc}")
    if st.button("Finalizar sin añadir seguimientos", use_container_width=True,
                 key=f"skip_followup_442_{report_id}"):
        _finish_tracking_step(report_id)


def _render_quick_report(report, participations: list, evaluations: dict, user: dict) -> None:
    """One optional single-page entrypoint, reusing Report + PlayerEvaluation only."""
    st.markdown("### Tu lectura breve")
    draft_notice = st.session_state.pop(f"quick_draft_notice_443_{report.id}", None)
    if draft_notice:
        st.success(draft_notice)
    st.caption("Valora únicamente lo que has visto. No es necesario puntuar a toda la plantilla.")
    # DD's optional request is visible at the match, before opening the fast form.
    from views.observation_requests import match_prompts
    match_prompts(user, report.match_id)
    eligible_parts = {int(part.player_id): part for part in participations}
    ordered = sorted(eligible_parts, key=lambda pid: (
        0 if eligible_parts[pid].team_id == report.own_team_id else 1,
        not eligible_parts[pid].starter, eligible_parts[pid].shirt_number or 999,
        eligible_parts[pid].player.full_name))
    previous = [pid for pid in ordered if pid in evaluations and (
        evaluations[pid].general_rating or evaluations[pid].short_note)]
    chosen = st.multiselect("Jugadores que quieres valorar o señalar (opcional)", ordered,
        default=previous, key=f"quick_players_443_{report.id}",
        format_func=lambda pid: f"{eligible_parts[pid].player.display_name or eligible_parts[pid].player.full_name} · "
            f"{'No Name' if eligible_parts[pid].team_id == report.own_team_id else report.rival_team.name}",
        help="Solo los jugadores identificados en este encuentro; no se infiere su participación a partir de la plantilla.")
    if len(chosen) > 3:
        st.warning("Para una lectura breve, selecciona hasta tres futbolistas. En el modo detallado puedes valorar toda la plantilla.")
    with st.form(f"quick_report_form_443_{report.id}"):
        c1, c2 = st.columns(2)
        o, od = rating_choices(report.own_team_rating)
        r, rd = rating_choices(report.rival_team_rating)
        own_choice = c1.pills("¿Cómo valoras a No Name?", o, default=od,
            selection_mode="single", help="Pulsa el botón entero; 'Sin evaluar' no cuenta en la media.")
        rival_choice = c2.pills(f"¿Cómo valoras a {report.rival_team.name}?", r, default=rd,
            selection_mode="single", help="Solo si puedes emitir una valoración real.")
        conclusion = st.text_area("Una idea del partido (opcional)", value=report.key_takeaways or "",
            height=70, placeholder="Qué merece recordar el cuerpo técnico…")
        rows = []
        for pid in chosen:
            part = eligible_parts[pid]
            current = evaluations.get(pid)
            name = part.player.display_name or part.player.full_name
            is_rival = part.team_id == report.rival_team_id
            st.markdown(f"**{name}** · {'Rival' if is_rival else 'No Name'}")
            rc, nc = st.columns([1, 1.5])
            opts, default = rating_choices(current.general_rating if current else None)
            grade = rc.pills(f"Nota · {name}", opts, default=default, selection_mode="single",
                help="Selecciona del 1 al 10 o deja sin evaluar.")
            short_note = nc.text_input(f"Apunte · {name}", value=current.short_note or "" if current else "",
                placeholder="Qué observaste (opcional)")
            follow = False
            if is_rival and can_track_players(user):
                follow = st.checkbox(f"Quiero ampliar el seguimiento de {name}", value=False,
                    key=f"quick_follow_443_{report.id}_{pid}",
                    help="No se selecciona automáticamente por nota 8 o superior; reutiliza esta misma evaluación.")
            rows.append((part, rating_from_choice(grade), short_note.strip(), follow))
        st.caption("Puedes guardar el borrador o entregar. No necesitas rellenar la plantilla completa.")
        save = st.form_submit_button("Guardar borrador", use_container_width=True)
        submit = st.form_submit_button("Entregar lectura", type="primary", use_container_width=True)
    if not (save or submit):
        return
    if len(chosen) > 3:
        st.error("Reduce la selección a tres jugadores o usa el modo detallado.")
        return
    try:
        for part, grade, note, follow in rows:
            if not grade and len(note) < 5:
                raise ValueError(f"Si seleccionas a {part.player.display_name or part.player.full_name}, añade nota o un apunte de al menos cinco caracteres.")
            if follow and (part.team_id != report.rival_team_id or grade <= 0):
                raise ValueError("Para ampliar seguimiento debes puntuar explícitamente al rival. No hay selección automática.")
        with session_scope() as session:
            saved = repo.save_report_summary(session, report.id,
                rival_level=report.rival_level, opponent_overview=report.opponent_overview,
                own_team_note=report.own_team_note, key_takeaways=conclusion.strip() or None,
                standout_player_id=report.standout_player_id, actor_id=user["id"],
                expected_revision=report.revision,
                own_team_rating=rating_from_choice(own_choice),
                rival_team_rating=rating_from_choice(rival_choice))
            follow_ids = []
            for part, grade, note, follow in rows:
                record = repo.upsert_evaluation(session, report.id, part.player_id,
                    part.team_id, part.id, actor_id=user["id"],
                    observation_status="evaluated" if grade > 0 else "observed",
                    general_rating=grade if grade > 0 else None, short_note=note or None,
                    standout=grade >= AUTO_STANDOUT_THRESHOLD, pdf_include=grade > 0)
                if follow:
                    follow_ids.append(int(record.id))
            if submit:
                repo.submit_report(session, report.id, user["id"])
                for eid in follow_ids:
                    tracking_repo.enrich_postmatch_evaluation(session, evaluation_id=eid, author_id=user["id"])
        _invalidate_workspace(report.id)
        if submit:
            st.session_state["report_submission_notice"] = {
                "match_id": int(report.match_id),
                "title": f"{report.match.home_team.name} – {report.match.away_team.name}"}
            st.session_state["_pending_report_ui_cleanup"] = int(report.id)
            st.session_state.pop("postmatch_tracking_wizard", None)
            st.session_state.pop("match_hub_mode", None)
            st.session_state.pop("workspace_match_id", None)
            st.session_state.pop("archive_open_report_33", None)
            request_navigation("Inicio")
        else:
            st.session_state[f"quick_draft_notice_443_{report.id}"] = "Borrador guardado correctamente."
        st.rerun()
    except Exception as exc:
        st.error(f"No se ha guardado la lectura: {exc}")


def _render_report_editor(report_id: int, user: dict) -> None:
    if st.session_state.get("postmatch_tracking_wizard") == int(report_id):
        _render_postmatch_tracking_step(report_id, user)
        return
    report, participations, evaluation_list = _load_report_editor(report_id)
    if not report:
        st.error("Informe no encontrado."); return
    if report.reporter_id != user["id"] and not can_direct(user):
        st.error("No tienes acceso a este informe."); return
    rival_players = [p for p in participations if p.team_id == report.rival_team_id]
    own_players = [p for p in participations if p.team_id == report.own_team_id]
    evaluations = {e.player_id: e for e in evaluation_list}
    read_only = report.status not in {"draft", "returned"} or report.reporter_id != user["id"]
    st.markdown(f"## {safe_html(report.match.home_team.name)} - {safe_html(report.match.away_team.name)}", unsafe_allow_html=True)
    st.caption(f"{report.match.competition.name} · {report.match.round_name} · {report.match.match_date.strftime('%d/%m/%Y')} · {REPORT_STATUSES.get(report.status, report.status)} · V{report.version}")
    if report.review_note:
        st.warning(f"Revisión: {report.review_note}")
    evaluated_rival = [e for e in evaluation_list if e.evaluation_scope == "rival" and e.observation_status == "evaluated" and e.general_rating is not None and e.general_rating > 0]
    evaluated_own = [e for e in evaluation_list if e.evaluation_scope == "own" and e.observation_status == "evaluated" and e.general_rating is not None and e.general_rating > 0]
    total_known = len(rival_players) + len(own_players)
    total_evaluated = len(evaluated_rival) + len(evaluated_own)
    if total_known:
        st.caption(f"{total_evaluated} valoraciones individuales registradas · completar la plantilla es opcional.")
    else:
        st.caption("No hay participantes identificados: puedes registrar una lectura colectiva documentada.")

    if read_only:
        section = st.radio("Sección", ["No Name", "Rival", "Finalizar", "Documentos"], horizontal=True, key=f"readonly_report_section_{report_id}")
        if section == "No Name": _render_team_form(report, own_players, evaluations, user, own_team=True, read_only=True)
        elif section == "Rival": _render_team_form(report, rival_players, evaluations, user, own_team=False, read_only=True)
        elif section == "Finalizar": _render_finish(report, evaluation_list, report_id, user, True)
        else: _render_documents(report_id)
        return

    stage_key = f"report_stage_{report_id}"
    stage = st.session_state.get(stage_key, "quick")
    if stage == "quick":
        if st.button("Abrir informe detallado", key=f"detailed_open_443_{report_id}",
                     help="Solo si quieres puntuar titulares, suplentes y añadir comentarios por equipo."):
            st.session_state[stage_key] = "own"
            st.rerun()
        _render_quick_report(report, participations, evaluations, user)
        return
    if st.button("← Volver a la lectura breve", key=f"quick_open_443_{report_id}"):
        if any(bool(st.session_state.get(_dirty_key(report.id, team_id), False))
               for team_id in (report.own_team_id, report.rival_team_id)):
            st.warning("Guarda o deshaz los cambios del informe detallado antes de cambiar de modo.")
        else:
            st.session_state[stage_key] = "quick"
            st.rerun()
    step_labels = {"own": "1 · No Name", "rival": "2 · Rival", "finish": "3 · Entregar"}
    st.caption(" → ".join((f"**{label}**" if key == stage else label) for key, label in step_labels.items()))
    if stage == "own":
        st.markdown("### 1 · No Name")
        _render_team_form(report, own_players, evaluations, user, own_team=True, read_only=False, next_stage="rival")
    elif stage == "rival":
        c1, c2 = st.columns([1,4])
        rival_dirty = bool(st.session_state.get(_dirty_key(report.id, report.rival_team_id), False))
        if c1.button("← No Name", use_container_width=True, disabled=rival_dirty, help="Guarda o deshaz los cambios del rival antes de salir." if rival_dirty else None):
            st.session_state[stage_key] = "own"; st.rerun()
        c2.markdown("### 2 · Rival")
        if rival_dirty:
            c2.caption("Hay cambios sin guardar: guarda o deshaz antes de cambiar de paso.")
        _render_team_form(report, rival_players, evaluations, user, own_team=False, read_only=False, next_stage="finish")
    else:
        st.markdown("### 3 · Entregar")
        _render_finish(report, evaluation_list, report_id, user, False)


def _available_work_matches(user: dict):
    with measure("Cargar trabajo pendiente", "report"):
        with session_scope() as session:
            all_matches = [m for m in repo.list_matches(session) if m.status in {"published", "closed"}]
            assignments = repo.list_assignments(session, user_id=user["id"])
            reports = repo.list_reports(session, reporter_id=user["id"])
    assigned_ids = {a.match_id for a in assignments if a.status not in {"waived", "declined"}}
    # Own-match report writing is assignment-driven even for hybrid DD/Informador.
    matches = [m for m in all_matches if m.id in assigned_ids]
    return matches, assignments, reports


def render_decline_control(user: dict, match_id: int, *, key_prefix: str) -> None:
    """Explicitly decline optional work without deleting a draft or touching DD data."""
    if not can_report(user):
        return
    with st.expander("No puedo realizar este informe", expanded=False):
        st.caption("La tarea desaparecerá de tu bandeja. Si ya tienes un borrador, se conservará; Administración podrá reactivar la asignación.")
        reason = st.text_input("Motivo (opcional)", key=f"decline_reason_{key_prefix}",
                               placeholder="Por ejemplo, no puedo asistir al partido")
        confirm = st.checkbox("Confirmo que no voy a realizar este informe", key=f"decline_confirm_{key_prefix}")
        if st.button("Rechazar asignación", type="secondary", disabled=not confirm,
                     use_container_width=True, key=f"decline_submit_{key_prefix}"):
            try:
                with session_scope() as session:
                    existing = repo.report_for_user(session, int(match_id), int(user["id"]))
                    draft_id = existing.id if existing and existing.status in {"draft", "returned"} else None
                    repo.decline_report_assignment(session, int(match_id), int(user["id"]), reason)
                if draft_id:
                    st.session_state["_pending_report_ui_cleanup"] = int(draft_id)
                st.session_state["assignment_declined_notice"] = "Has rechazado la asignación. Ya no aparece entre tus tareas pendientes."
                st.session_state.pop("match_hub_mode", None)
                st.session_state.pop("workspace_match_id", None)
                request_navigation("Inicio")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _render_work(user: dict) -> None:
    if not can_report(user):
        st.error("Para valorar partidos necesitas el rol Informador.")
        return
    page_header("Valorar partido", "Valora únicamente lo que hayas observado y guarda cuando estés listo.")
    pending_tracking = st.session_state.get("postmatch_tracking_wizard")
    if pending_tracking:
        _render_postmatch_tracking_step(int(pending_tracking), user)
        return
    matches, assignments, reports = _available_work_matches(user)
    if not matches:
        st.info("No tienes partidos asignados."); return
    existing_by_match = {r.match_id: r for r in reports}; assignment_by_match = {a.match_id: a for a in assignments}
    active_matches = [m for m in matches if m.id not in existing_by_match or existing_by_match[m.id].status in {"draft", "returned"}]
    if not active_matches:
        st.success("No tienes valoraciones pendientes. Consulta lo entregado desde Mis informes."); return
    labels = {}
    for match in active_matches:
        report = existing_by_match.get(match.id); assignment = assignment_by_match.get(match.id)
        state = REPORT_STATUSES.get(report.status, report.status) if report else ASSIGNMENT_STATUSES.get(assignment.status, assignment.status) if assignment else "Pendiente"
        labels[match.id] = f"{match_label(match)} · {state}"
    valid_ids = [m.id for m in active_matches]
    preferred = st.session_state.pop("report_selected_match_id", None)
    selected_match_id = st.selectbox("Partido", valid_ids, index=valid_ids.index(preferred) if preferred in valid_ids else 0, format_func=lambda mid: labels[mid])
    render_decline_control(user, selected_match_id, key_prefix=f"work_441_{selected_match_id}")
    selected_report = existing_by_match.get(selected_match_id)
    if not selected_report:
        if st.button("Empezar a valorar", type="primary", use_container_width=True):
            try:
                with session_scope() as session:
                    repo.get_or_create_report(session, selected_match_id, user["id"], actor_role="reporter")
                st.rerun()
            except Exception as exc: st.error(str(exc))
        return
    _render_report_editor(selected_report.id, user)


def _render_archive(user: dict) -> None:
    title = "Informes" if can_direct(user) else "Mis informes"
    page_header(title, "Filtra primero y abre solo el informe que necesites. El editor no se carga hasta pulsar Abrir.")
    with session_scope() as session:
        seasons = repo.list_seasons(session)
        teams = repo.list_teams(session, active_only=True)
        users = repo.list_users(session, active_only=True) if can_direct(user) else []
    c1, c2, c3, c4 = st.columns(4)
    season_opts = [None] + [s.id for s in seasons]
    season_id = c1.selectbox("Temporada", season_opts, format_func=lambda x: "Todas" if x is None else next(s.name for s in seasons if s.id == x))
    status_keys = [None] + list(REPORT_STATUSES)
    status = c2.selectbox("Estado", status_keys, format_func=lambda x: "Todos" if x is None else REPORT_STATUSES[x])
    rival_opts = [None] + [t.id for t in teams if not t.is_own_team and not t.is_test and t.archived_at is None]
    rival_id = c3.selectbox("Rival", rival_opts, format_func=lambda x: "Todos" if x is None else next(t.name for t in teams if t.id == x))
    round_query = c4.text_input("Jornada", placeholder="Ej. Jornada 8")
    reporter_id = None if can_direct(user) else user["id"]
    if users:
        reporter_opts = [None] + [u.id for u in users]
        reporter_id = st.selectbox("Informador", reporter_opts, format_func=lambda x: "Todos" if x is None else next(u.full_name for u in users if u.id == x))
    with measure("Filtrar archivo de informes", "archive"):
        with session_scope() as session:
            reports = repo.list_reports(session, reporter_id=reporter_id, status=status, season_id=season_id, rival_team_id=rival_id, limit=80)
    if round_query.strip():
        needle = round_query.strip().casefold()
        reports = [r for r in reports if needle in (r.match.round_name or "").casefold()]
    if not reports:
        st.info("No hay informes con esos filtros."); return
    st.dataframe(pd.DataFrame([{"Partido": f"{r.match.home_team.name} - {r.match.away_team.name}", "Fecha": r.match.match_date, "Informador": r.reporter.full_name, "Estado": REPORT_STATUSES.get(r.status,r.status), "V": r.version} for r in reports]), hide_index=True, use_container_width=True)
    labels = {r.id: f"{r.match.match_date.strftime('%d/%m/%Y')} · {r.match.home_team.name} - {r.match.away_team.name} · {r.reporter.full_name}" for r in reports}
    selected = st.selectbox("Informe", list(labels), format_func=lambda rid: labels[rid])
    if st.button("Abrir informe", type="primary", use_container_width=True):
        st.session_state["archive_open_report_33"] = selected
    opened = st.session_state.get("archive_open_report_33")
    if opened in labels:
        st.divider(); _render_report_editor(opened, user)



def render_match_report(user: dict, match_id: int) -> None:
    """Contextual postmatch editor opened from Match Hub."""
    if not can_report(user):
        st.error("Para completar un postpartido necesitas el rol Informador.")
        return
    contextual = dict(user)
    contextual["role"] = "reporter"
    with session_scope() as session:
        assignment = next((row for row in repo.list_assignments(session, user_id=user["id"])
                           if row.match_id == int(match_id)), None)
        report = repo.report_for_user(session, int(match_id), int(user["id"]))
    if assignment and assignment.status in {"waived", "declined"}:
        st.info("Tu asignación no está activa. Administración puede reactivarla.")
        return
    if assignment and assignment.status in {"pending", "in_progress", "returned"}:
        render_decline_control(user, match_id, key_prefix=f"match_editor_441_{match_id}")
    if not report:
        if st.button("Empezar informe", type="primary", use_container_width=True, key=f"start_match_report_{match_id}"):
            try:
                with session_scope() as session:
                    report = repo.get_or_create_report(session, int(match_id), int(user["id"]), actor_role=contextual["role"])
                st.session_state[f"match_report_id_{match_id}"] = report.id
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        return
    _render_report_editor(report.id, contextual)


def render_work(user: dict) -> None: _render_work(user)
def render_archive(user: dict) -> None: _render_archive(user)
def render(user: dict, mode: str = "work") -> None:
    render_archive(user) if mode == "archive" else render_work(user)
