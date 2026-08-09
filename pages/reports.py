from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from core.constants import ASSIGNMENT_STATUSES, PDF_MODES, REPORT_STATUSES
from core.database import session_scope
from core.evaluation_rules import AUTO_STANDOUT_THRESHOLD, derive_simple_evaluation_state
from core.utils import safe_html
from repositories import scouting as repo
from services.report_service import generate_report_pdf, report_filename
from services.storage_service import load_document_bytes, save_pdf
from ui.helpers import match_label
from ui.styles import page_header


REPORTS_PAGE_API_VERSION = "3.0.0"


def _minutes_played(participation) -> int:
    minute_in = int(participation.minute_in or 0)
    minute_out = int(participation.minute_out or 90)
    return max(0, minute_out - minute_in)


def _participation_meta(participation) -> str:
    role = "Titular" if participation.starter else f"Entró en el {participation.minute_in}'"
    if participation.minute_out and participation.minute_out < 90:
        role += f" · salió en el {participation.minute_out}'"
    position = participation.position or participation.player.primary_position or "Sin posición"
    return f"{position} · {_minutes_played(participation)} minutos · {role}"


def _init_card_state(prefix: str, existing, own_team: bool) -> None:
    defaults = {
        prefix + "rating": float(existing.general_rating) if existing and existing.general_rating is not None else 0.0,
        prefix + "note": existing.short_note if existing and existing.short_note else "",
        prefix + "standout": bool(existing and existing.standout),
        prefix + "pdf": bool(existing.pdf_include) if existing else True,
        prefix + "revision": existing.revision if existing else None,
        prefix + "standout_touched": False,
        prefix + "pdf_touched": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if own_team:
        st.session_state.setdefault(prefix + "pdf", True)


def _persist_player_card(
    report_id: int,
    user_id: int,
    player_id: int,
    team_id: int,
    participation_id: int,
    own_team: bool,
    prefix: str,
) -> None:
    rating = float(st.session_state.get(prefix + "rating", 0.0) or 0.0)
    state = derive_simple_evaluation_state(
        rating,
        pdf_include=bool(st.session_state.get(prefix + "pdf", True)),
        standout=bool(st.session_state.get(prefix + "standout", False)),
        pdf_manually_changed=bool(st.session_state.get(prefix + "pdf_touched", False)),
        standout_manually_changed=bool(st.session_state.get(prefix + "standout_touched", False)),
    )
    try:
        with session_scope() as session:
            item = repo.upsert_evaluation(
                session,
                report_id,
                player_id,
                team_id,
                participation_id,
                actor_id=user_id,
                expected_revision=st.session_state.get(prefix + "revision"),
                observation_status=state.observation_status,
                general_rating=state.general_rating,
                short_note=(st.session_state.get(prefix + "note") or "").strip() or None,
                standout=state.standout,
                pdf_include=state.pdf_include,
                recommendation=None,
                confidence=None,
            )
            if not own_team:
                repo.sync_report_standout(session, report_id, user_id)
            st.session_state[prefix + "revision"] = item.revision
        st.session_state[f"save_status_{report_id}"] = f"Guardado automáticamente · {datetime.now().strftime('%H:%M:%S')}"
    except Exception as exc:
        st.session_state[f"save_status_{report_id}"] = f"Cambios sin guardar: {exc}"


def _rating_changed(*args) -> None:
    report_id, user_id, player_id, team_id, participation_id, own_team, prefix = args
    rating = float(st.session_state.get(prefix + "rating", 0.0) or 0.0)
    if not st.session_state.get(prefix + "pdf_touched", False) and rating > 0:
        st.session_state[prefix + "pdf"] = True
    if not st.session_state.get(prefix + "standout_touched", False):
        st.session_state[prefix + "standout"] = rating >= AUTO_STANDOUT_THRESHOLD
    _persist_player_card(*args)


def _quick_rating(value: float, *args) -> None:
    prefix = args[-1]
    st.session_state[prefix + "rating"] = float(value)
    _rating_changed(*args)


def _note_changed(*args) -> None:
    _persist_player_card(*args)


def _standout_changed(*args) -> None:
    prefix = args[-1]
    st.session_state[prefix + "standout_touched"] = True
    _persist_player_card(*args)


def _pdf_changed(*args) -> None:
    prefix = args[-1]
    st.session_state[prefix + "pdf_touched"] = True
    _persist_player_card(*args)


def _render_player_card(report_id: int, participation, team_id: int, existing, user: dict, read_only: bool, own_team: bool) -> None:
    player = participation.player
    prefix = f"simple_eval_{report_id}_{player.id}_"
    _init_card_state(prefix, existing, own_team)
    callback_args = (report_id, user["id"], player.id, team_id, participation.id, own_team, prefix)

    with st.container(border=True):
        title_col, score_col = st.columns([4.5, 1])
        display_name = player.display_name or player.full_name
        shirt = f"#{participation.shirt_number}" if participation.shirt_number is not None else "Sin dorsal"
        title_col.markdown(f"### {safe_html(display_name)}", unsafe_allow_html=True)
        title_col.caption(f"{shirt} · {_participation_meta(participation)}")
        current_rating = float(st.session_state.get(prefix + "rating", 0.0) or 0.0)
        score_col.metric("Nota", "Sin valorar" if current_rating <= 0 else f"{current_rating:.1f}")

        slider_col, note_col = st.columns([1.15, 1])
        with slider_col:
            st.slider(
                "Valoración del partido",
                min_value=0.0,
                max_value=10.0,
                step=0.1,
                key=prefix + "rating",
                disabled=read_only,
                on_change=_rating_changed,
                args=callback_args,
                help="0 significa que no has podido valorar al jugador.",
            )
            st.caption("0 = sin valorar · 8 o más se marca automáticamente como destacado")
            quick = st.columns(5)
            for col, value in zip(quick, (5.0, 6.0, 7.0, 8.0, 9.0)):
                col.button(
                    f"{int(value)}",
                    use_container_width=True,
                    disabled=read_only,
                    key=f"{prefix}quick_{int(value)}",
                    on_click=_quick_rating,
                    args=(value, *callback_args),
                    help=f"Poner {value:.0f} rápidamente y ajustar después con la barra si quieres.",
                )
        with note_col:
            st.text_area(
                "Observación opcional",
                key=prefix + "note",
                height=92,
                disabled=read_only,
                on_change=_note_changed,
                args=callback_args,
                placeholder="Ej.: rápido al espacio, buen pie izquierdo, sufrió en duelos...",
            )

        check_a, check_b, status_col = st.columns([1, 1, 2.2])
        check_a.checkbox(
            "Destacado",
            key=prefix + "standout",
            disabled=read_only,
            on_change=_standout_changed,
            args=callback_args,
            help="Se activa automáticamente con una nota de 8 o superior, pero puedes cambiarlo.",
        )
        check_b.checkbox(
            "Incluir en PDF",
            key=prefix + "pdf",
            disabled=read_only,
            on_change=_pdf_changed,
            args=callback_args,
            help="Viene marcado por defecto. Solo se incluirá si el jugador tiene una nota mayor que 0.",
        )
        if current_rating > 0:
            status_col.success("Valoración guardada")
        else:
            status_col.info("Pendiente de valorar")


def _render_players_group(report_id: int, players: list, team_id: int, evaluations: dict, user: dict, read_only: bool, own_team: bool) -> None:
    if not players:
        st.warning("No hay jugadores cargados para este equipo.")
        return
    starters = [p for p in players if p.starter]
    substitutes = [p for p in players if not p.starter]
    if starters:
        st.markdown("#### Titulares")
        for part in starters:
            _render_player_card(report_id, part, team_id, evaluations.get(part.player_id), user, read_only, own_team)
    if substitutes:
        st.markdown("#### Suplentes utilizados")
        for part in substitutes:
            _render_player_card(report_id, part, team_id, evaluations.get(part.player_id), user, read_only, own_team)


def _store_version_documents(session, report_id: int, version_obj) -> list[str]:
    messages = []
    for mode in ("executive", "full"):
        pdf = generate_report_pdf(session, report_id, version=version_obj.version, mode=mode)
        stored = save_pdf(report_id, version_obj.version, pdf, document_type=mode)
        repo.save_document(
            session,
            report_id,
            version_obj.version,
            report_version_id=version_obj.id,
            document_type=mode,
            storage_bucket=stored.get("storage_bucket"),
            storage_path=stored.get("storage_path"),
            local_path=stored.get("local_path"),
            checksum=stored.get("checksum"),
            size_bytes=stored.get("size_bytes"),
            storage_status=str(stored.get("storage_status")),
            error_message=stored.get("error_message"),
        )
        messages.append(f"{PDF_MODES[mode]}: {stored.get('storage_status')}")
    return messages


def _render_finish_tab(report, evaluation_list: list, report_id: int, user: dict, read_only: bool) -> None:
    with session_scope() as session:
        errors = repo.validate_report_for_finalization(session, report_id)
    valid_rival = [
        e for e in evaluation_list
        if e.evaluation_scope == "rival" and e.observation_status == "evaluated" and e.general_rating is not None
    ]
    valid_own = [
        e for e in evaluation_list
        if e.evaluation_scope == "own" and e.observation_status == "evaluated" and e.general_rating is not None
    ]
    metrics = st.columns(4)
    metrics[0].metric("Rivales valorados", len(valid_rival))
    metrics[1].metric("Propios valorados", len(valid_own))
    metrics[2].metric("Incluidos en PDF", len([e for e in (valid_rival + valid_own) if e.pdf_include]))
    metrics[3].metric("Versión", f"V{report.version}")

    st.info("No tienes que rellenarlo todo. Puedes entregar aunque queden jugadores sin valorar; 0 significa simplemente que no has tenido elementos suficientes.")
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
            st.download_button(
                "Descargar borrador",
                st.session_state[f"preview_{report_id}_{mode}"],
                file_name=st.session_state[f"preview_name_{report_id}_{mode}"],
                mime="application/pdf",
                use_container_width=True,
            )
        confirm = st.checkbox("He revisado las notas y quiero entregar el informe.")
        if st.button("Entregar informe", type="primary", disabled=not confirm or bool(errors), use_container_width=True):
            try:
                with session_scope() as session:
                    _, version_obj = repo.submit_report(session, report_id, user["id"])
                    messages = _store_version_documents(session, report_id, version_obj)
                st.success("Informe entregado. " + " · ".join(messages))
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        st.success(f"Informe bloqueado: {REPORT_STATUSES.get(report.status, report.status)}.")
        if report.status == "submitted":
            st.info("Está pendiente de revisión por dirección deportiva.")


def _render_documents(report_id: int, versions: list, documents: list) -> None:
    if not versions:
        st.info("Todavía no existe ninguna versión entregada.")
        return
    for version_obj in versions:
        st.markdown(
            f"**V{version_obj.version} · {REPORT_STATUSES.get(version_obj.status, version_obj.status)} · "
            f"{version_obj.created_at.strftime('%d/%m/%Y %H:%M')}**"
        )
        docs = [d for d in documents if d.version == version_obj.version]
        if not docs:
            st.caption("No hay documentos almacenados para esta versión.")
            continue
        cols = st.columns(len(docs))
        for col, doc in zip(cols, docs):
            col.caption(f"{PDF_MODES.get(doc.document_type, doc.document_type)} · {doc.storage_status}")
            if doc.error_message:
                col.error(doc.error_message)
            try:
                content = load_document_bytes(
                    bucket=doc.storage_bucket,
                    storage_path=doc.storage_path,
                    local_path=doc.local_path,
                )
                with session_scope() as session:
                    filename = report_filename(session, report_id, version=doc.version, mode=doc.document_type)
                col.download_button(
                    f"Descargar {PDF_MODES.get(doc.document_type, doc.document_type)}",
                    content,
                    filename,
                    "application/pdf",
                    key=f"doc_{doc.id}",
                )
            except Exception as exc:
                col.warning(str(exc))


def _render_report_editor(report_id: int, user: dict) -> None:
    with session_scope() as session:
        report = repo.get_report(session, report_id)
        if not report:
            st.error("Informe no encontrado.")
            return
        participations = repo.get_participations(session, report.match_id)
        evaluation_list = repo.list_evaluations(session, report_id)
        versions = repo.list_report_versions(session, report_id)
        documents = repo.list_documents(session, report_id)

    if report.reporter_id != user["id"] and user["role"] not in {"admin", "director"}:
        st.error("No tienes acceso a este informe.")
        return

    rival_players = [p for p in participations if p.team_id == report.rival_team_id]
    own_players = [p for p in participations if p.team_id == report.own_team_id]
    evaluations = {e.player_id: e for e in evaluation_list}
    read_only = report.status not in {"draft", "returned"} or report.reporter_id != user["id"]

    st.markdown(f"## {safe_html(report.match.home_team.name)} - {safe_html(report.match.away_team.name)}", unsafe_allow_html=True)
    st.caption(
        f"{report.match.competition.name} · {report.match.round_name} · "
        f"{report.match.match_date.strftime('%d/%m/%Y')} · "
        f"{REPORT_STATUSES.get(report.status, report.status)} · V{report.version}"
    )
    if report.review_note:
        st.warning(f"Revisión: {report.review_note}")
    if st.session_state.get(f"save_status_{report_id}"):
        st.caption(st.session_state[f"save_status_{report_id}"])

    evaluated_rival = [
        e for e in evaluation_list
        if e.evaluation_scope == "rival" and e.observation_status == "evaluated" and e.general_rating is not None
    ]
    progress = len(evaluated_rival) / len(rival_players) if rival_players else 0
    st.progress(progress, text=f"{len(evaluated_rival)} de {len(rival_players)} rivales valorados")

    tab_own, tab_rival, tab_finish, tab_docs = st.tabs([
        f"Nuestro equipo · {report.own_team.name}",
        f"Rival · {report.rival_team.name}",
        "Finalizar",
        "Documentos",
    ])
    with tab_own:
        st.caption("Mismo sistema sencillo: posición y minutos están bloqueados; tú solo valoras el rendimiento.")
        _render_players_group(report_id, own_players, report.own_team_id, evaluations, user, read_only, True)
    with tab_rival:
        st.caption("Valora únicamente lo que hayas visto. La posición, dorsal, titularidad y minutos ya vienen preparados por administración.")
        _render_players_group(report_id, rival_players, report.rival_team_id, evaluations, user, read_only, False)
    with tab_finish:
        _render_finish_tab(report, evaluation_list, report_id, user, read_only)
    with tab_docs:
        _render_documents(report_id, versions, documents)


def _available_work_matches(user: dict):
    with session_scope() as session:
        all_matches = [m for m in repo.list_matches(session) if m.status in {"published", "closed"}]
        assignments = repo.list_assignments(session, user_id=user["id"])
        reports = repo.list_reports(session, reporter_id=user["id"])
    assigned_ids = {a.match_id for a in assignments if a.status != "waived"}
    matches = [
        m for m in all_matches
        if user["role"] in {"admin", "director"} or not assignments or m.id in assigned_ids
    ]
    return matches, assignments, reports


def _render_work(user: dict) -> None:
    page_header("Valorar partido", "Solo jugadores: nota, observación opcional y dos checks. El resto ya viene del partido.")
    matches, assignments, reports = _available_work_matches(user)
    if not matches:
        st.info("No tienes partidos asignados.")
        return

    existing_by_match = {r.match_id: r for r in reports}
    assignment_by_match = {a.match_id: a for a in assignments}
    active_matches = [
        m for m in matches
        if m.id not in existing_by_match or existing_by_match[m.id].status in {"draft", "returned"}
    ]
    if not active_matches:
        st.success("No tienes valoraciones pendientes. Puedes consultar lo ya entregado desde Mis informes.")
        return

    labels = {}
    for match in active_matches:
        report = existing_by_match.get(match.id)
        assignment = assignment_by_match.get(match.id)
        state = REPORT_STATUSES.get(report.status, report.status) if report else ASSIGNMENT_STATUSES.get(assignment.status, assignment.status) if assignment else "Pendiente"
        labels[match.id] = f"{match_label(match)} · {state}"

    valid_ids = [m.id for m in active_matches]
    preferred = st.session_state.pop("report_selected_match_id", None)
    default_index = valid_ids.index(preferred) if preferred in valid_ids else 0
    selected_match_id = st.selectbox("Partido que vas a informar", valid_ids, index=default_index, format_func=lambda mid: labels[mid])
    selected_report = existing_by_match.get(selected_match_id)
    if not selected_report:
        st.info("Todo está preparado por administración: alineaciones, posiciones y minutos. Solo tienes que valorar jugadores.")
        if st.button("Empezar a valorar", type="primary", use_container_width=True):
            try:
                with session_scope() as session:
                    report = repo.get_or_create_report(session, selected_match_id, user["id"], actor_role=user["role"])
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        return
    _render_report_editor(selected_report.id, user)


def _render_archive(user: dict) -> None:
    title = "Mis informes" if user["role"] == "reporter" else "Informes"
    page_header(title, "Consulta borradores, entregas y documentos generados.")
    with session_scope() as session:
        reports = repo.list_reports(session, reporter_id=user["id"] if user["role"] == "reporter" else None)
    if not reports:
        st.info("Todavía no hay informes.")
        return

    status_options = ["Todos"] + sorted({REPORT_STATUSES.get(r.status, r.status) for r in reports})
    selected_status = st.selectbox("Estado", status_options)
    visible = [r for r in reports if selected_status == "Todos" or REPORT_STATUSES.get(r.status, r.status) == selected_status]
    if not visible:
        st.info("No hay informes con ese estado.")
        return

    frame = pd.DataFrame([{
        "ID": r.id,
        "Partido": f"{r.match.home_team.name} - {r.match.away_team.name}",
        "Fecha": r.match.match_date,
        "Informador": r.reporter.full_name,
        "Estado": REPORT_STATUSES.get(r.status, r.status),
        "Versión": f"V{r.version}",
        "Actualizado": r.updated_at,
    } for r in visible])
    st.dataframe(frame, use_container_width=True, hide_index=True)
    labels = {
        r.id: f"{r.match.match_date.strftime('%d/%m/%Y')} · {r.match.home_team.name} - {r.match.away_team.name} · "
              f"{REPORT_STATUSES.get(r.status, r.status)} · {r.reporter.full_name}"
        for r in visible
    }
    selected_report_id = st.selectbox("Abrir informe", list(labels), format_func=lambda rid: labels[rid])
    _render_report_editor(selected_report_id, user)


def render_work(user: dict) -> None:
    """Stable entrypoint for the report creation workflow."""
    _render_work(user)


def render_archive(user: dict) -> None:
    """Stable entrypoint for the report archive workflow."""
    _render_archive(user)


def render(user: dict, mode: str = "work") -> None:
    """Backward-compatible dispatcher kept for older internal calls."""
    if mode == "archive":
        render_archive(user)
    else:
        render_work(user)
