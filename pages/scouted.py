from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from core.constants import POSITIONS
from core.database import session_scope
from core.scouting_model import attributes_for, roles_for
from repositories import advanced_scouting as scout_repo
from repositories import league_intelligence as league_repo
from repositories import scouting as repo
from repositories import planning as planning_repo
from repositories import player_report as player_report_repo
from reports.player_report_pdf import generate_player_executive_pdf, generate_player_360_pdf, player_report_filename
from ui import player_report as player_report_ui
from ui.styles import page_header


def _rating(value) -> float:
    return float(value) if value is not None else 0.0


def _observed_table(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Jugador": r["full_name"],
        "POS": r.get("primary_position") or "-",
        "Obs.": r["observations"],
        "Media": round(r["avg_general"], 2),
        "Destacados": r["standouts"],
        "Informadores": r["reporter_count"],
        "Confianza": league_repo.confidence_score(r["observations"], r["reporter_count"], r["rating_dispersion"], r.get("last_observed"))["label"],
    } for r in rows])


def _review_form(profile, review, user: dict) -> None:
    player = profile.player
    default_position = review.observed_position if review and review.observed_position else profile.model_position or player.primary_position or "Otro"
    try:
        attrs = json.loads(review.attributes_json or "{}") if review else {}
    except Exception:
        attrs = {}
    st.markdown(f"### Ficha scout · {player.display_name or player.full_name}")
    st.caption("Esta ficha es deliberadamente más completa que el informe postpartido. Solo rellena lo que realmente puedas sostener con lo observado.")
    with st.form(f"scout_review_{profile.id}_{user['id']}"):
        c1, c2 = st.columns(2)
        observed_position = c1.selectbox("Posición observada", POSITIONS, index=POSITIONS.index(default_position) if default_position in POSITIONS else len(POSITIONS)-1)
        recommendation = c2.selectbox("Conclusión del scout", scout_repo.SCOUT_RECOMMENDATIONS, index=scout_repo.SCOUT_RECOMMENDATIONS.index(review.recommendation) if review and review.recommendation in scout_repo.SCOUT_RECOMMENDATIONS else 0)
        c1, c2, c3 = st.columns(3)
        current_level = c1.slider("Nivel actual", 0.0, 10.0, _rating(review.current_level if review else None), .5, help="0 = sin valorar")
        potential = c2.slider("Proyección", 0.0, 10.0, _rating(review.potential_score if review else None), .5, help="0 = sin valorar")
        model_fit = c3.slider("Encaje en nuestro modelo", 0.0, 10.0, _rating(review.model_fit_score if review else None), .5, help="0 = sin valorar")

        st.markdown("#### Valoración por bloques")
        c1, c2, c3, c4 = st.columns(4)
        technical = c1.slider("Técnico", 0.0, 10.0, _rating(review.technical_rating if review else None), .5)
        tactical = c2.slider("Táctico", 0.0, 10.0, _rating(review.tactical_rating if review else None), .5)
        physical = c3.slider("Físico", 0.0, 10.0, _rating(review.physical_rating if review else None), .5)
        mental = c4.slider("Mental", 0.0, 10.0, _rating(review.mental_rating if review else None), .5)

        with st.expander("Atributos específicos · opcional", expanded=False):
            new_attrs = {}
            for group, names in attributes_for(observed_position).items():
                st.markdown(f"**{group}**")
                cols = st.columns(2)
                for idx, name in enumerate(names):
                    old = float(attrs.get(group, {}).get(name, 0) or 0)
                    new_attrs.setdefault(group, {})[name] = cols[idx % 2].slider(name, 0.0, 10.0, old, .5, key=f"attr_{profile.id}_{group}_{name}")
        strengths = st.text_area("Fortalezas", value=review.strengths or "" if review else "", placeholder="2-4 ideas concretas")
        weaknesses = st.text_area("A mejorar / riesgos", value=review.weaknesses or "" if review else "", placeholder="Solo si se han observado")
        summary = st.text_area("Resumen scout", value=review.summary or "" if review else "", height=120, placeholder="Qué jugador creemos que es y en qué contexto puede rendir")
        c1, c2 = st.columns(2)
        save = c1.form_submit_button("Guardar borrador", use_container_width=True)
        submit = c2.form_submit_button("Entregar ficha scout", type="primary", use_container_width=True)
    if save or submit:
        with session_scope() as session:
            fresh = scout_repo.get_or_create_review(session, profile.id, user["id"])
            scout_repo.save_review(
                session, fresh.id, user["id"], observed_position=observed_position,
                technical_rating=technical or None, tactical_rating=tactical or None,
                physical_rating=physical or None, mental_rating=mental or None,
                current_level=current_level or None, potential_score=potential or None,
                model_fit_score=model_fit or None, attributes=new_attrs,
                strengths=strengths.strip() or None, weaknesses=weaknesses.strip() or None,
                summary=summary.strip() or None, recommendation=recommendation, submit=submit,
            )
        st.success("Ficha scout entregada." if submit else "Borrador scout guardado.")
        st.rerun()


def _director_profile(profile, user: dict) -> None:
    player = profile.player
    with session_scope() as session:
        users = repo.list_users(session, active_only=True)
        reviews = scout_repo.list_reviews(session, profile.id)  # informes legado 3.3/3.4
        observations = planning_repo.list_observations(session, player_id=player.id, limit=100)
        model_roles = planning_repo.list_model_roles(session)
        positions = league_repo.observed_position_counts(session, player.id)
        active_season = repo.get_active_season(session)
        evidence = planning_repo.scouting_evidence_summary(session, player.id, season_id=active_season.id if active_season else None)
    # La asignación avanzada se dirige a perfiles Scout; admin/director también pueden cubrirla.
    with session_scope() as session:
        reporters = planning_repo.list_scout_users(session)
    labels = {u.id: f"{u.full_name} · Scout" for u in reporters}
    observed_default = positions[0]["position"] if positions else player.primary_position or "Otro"
    selected_pos = profile.model_position or observed_default
    roles = roles_for(selected_pos)
    st.markdown(f"### Encaje No Name · {player.display_name or player.full_name}")
    if positions:
        st.caption("Posiciones observadas: " + " · ".join(f"{r['position']} ({r['observations']})" for r in positions))
    st.caption(
        f"Evidencia: {evidence['postmatch_observations']} postpartido · "
        f"{evidence['specific_observations']} scout específicas · "
        f"{evidence['specific_scouts']} scouts · {evidence['specific_strength']}"
    )
    with st.form(f"dd_scout_profile_{profile.id}"):
        c1, c2 = st.columns(2)
        model_position = c1.selectbox("Posición en nuestro modelo", POSITIONS, index=POSITIONS.index(selected_pos) if selected_pos in POSITIONS else len(POSITIONS)-1)
        configured_roles = [r.name for r in model_roles if r.position == model_position]
        current_roles = configured_roles or roles_for(model_position)
        role_default = profile.model_role if profile.model_role in current_roles else current_roles[0]
        model_role = c2.selectbox("Rol en nuestro modelo", current_roles, index=current_roles.index(role_default))
        c1, c2, c3 = st.columns(3)
        fit_score = c1.slider("Encaje DD", 0.0, 10.0, _rating(profile.fit_score), .5)
        current_level = c2.slider("Nivel actual DD", 0.0, 10.0, _rating(profile.current_level), .5)
        potential_score = c3.slider("Proyección DD", 0.0, 10.0, _rating(profile.potential_score), .5)
        assigned_options = [None] + [u.id for u in reporters]
        assigned = st.selectbox("Solicitar / asignar ficha scout a", assigned_options, index=assigned_options.index(profile.assigned_to) if profile.assigned_to in assigned_options else 0, format_func=lambda uid: "Sin asignar" if uid is None else labels[uid])
        decision = st.selectbox("Decisión final", scout_repo.SCOUT_DECISIONS, index=scout_repo.SCOUT_DECISIONS.index(profile.final_decision) if profile.final_decision in scout_repo.SCOUT_DECISIONS else 0)
        summary = st.text_area("Conclusión de Dirección Deportiva", value=profile.director_summary or "", height=120)
        c1, c2 = st.columns(2)
        save = c1.form_submit_button("Guardar encaje", use_container_width=True)
        approve = c2.form_submit_button("Cerrar como jugador ojeado", type="primary", use_container_width=True)
    if save or approve:
        with session_scope() as session:
            scout_repo.update_profile(
                session, profile.id, user["id"], status="requested" if assigned and not approve else None,
                assigned_to=assigned, model_position=model_position, model_role=model_role,
                fit_score=fit_score or None, current_level=current_level or None,
                potential_score=potential_score or None, final_decision=decision,
                director_summary=summary.strip() or None, approve=approve,
            )
        st.success("Ficha scout cerrada." if approve else "Encaje guardado.")
        st.rerun()
    if observations:
        st.markdown("#### Observaciones scout específicas")
        st.dataframe(pd.DataFrame([{
            "Fecha": o.observed_at, "Scout": o.reviewer.full_name,
            "Partido": "-" if not o.match else f"{o.match.home_team.name} - {o.match.away_team.name}",
            "Tipo": o.source_type, "POS": o.observed_position or "-", "Nota visionado": o.general_rating, "Encaje": o.model_fit_score,
            "Nivel": o.current_level, "Recomendación": o.recommendation or "", "Resumen": o.summary or "",
        } for o in observations]), hide_index=True, use_container_width=True)
    if reviews:
        st.markdown("#### Informes scout legado")
        st.dataframe(pd.DataFrame([{
            "Informador": r.reviewer.full_name, "Estado": r.status, "POS": r.observed_position or "-",
            "Técnico": r.technical_rating, "Táctico": r.tactical_rating, "Físico": r.physical_rating,
            "Mental": r.mental_rating, "Encaje": r.model_fit_score, "Conclusión": r.recommendation or "",
        } for r in reviews]), hide_index=True, use_container_width=True)



def _render_player_360(player_id: int, user: dict) -> None:
    if st.button("← Volver a jugadores ojeados", key="back_from_player360"):
        st.session_state.pop("scouted_player_360_id", None)
        st.rerun()
    with session_scope() as session:
        active = repo.get_active_season(session)
        payload = player_report_repo.build_player_report_360(session, int(player_id), season_id=active.id if active else None)
        settings = repo.get_all_settings(session)
    player_report_ui.render_header(payload)
    sections = ["Resumen", "Modelo No Name", "Evolución", "Observaciones", "Comparativa", "Datos"]
    if user["role"] in {"director", "admin"}:
        sections.append("Decisión DD")
    section = st.radio("Player Report", sections, horizontal=True, key=f"player360_section_{player_id}")
    if section == "Resumen":
        player_report_ui.render_summary(payload)
    elif section == "Modelo No Name":
        player_report_ui.render_model(payload)
    elif section == "Evolución":
        player_report_ui.render_evolution(payload)
    elif section == "Observaciones":
        player_report_ui.render_observations(payload)
    elif section == "Comparativa":
        player_report_ui.render_comparison(payload)
    elif section == "Datos":
        player_report_ui.render_data(payload)
    else:
        profile = payload.get("profile")
        if profile:
            _director_profile(profile, user)
            role = payload.get("role")
            if role:
                criteria = payload.get("criteria") or []
                st.markdown("### Evaluación DD por criterios del modelo")
                st.caption("Esta valoración es de Dirección Deportiva y queda separada de las observaciones Scout. Se usa en la comparación con nuestra plantilla y en el Player Report 360.")
                with st.form(f"dd_model_criteria_{player_id}_{role.id}"):
                    scores = {}
                    for row in criteria:
                        scores[row["id"]] = st.slider(
                            f"{row['name']} · peso {row['weight']}", 0.0, 10.0,
                            float(row["score"] or 0), .5, key=f"dd360_crit_{player_id}_{row['id']}"
                        )
                    c1,c2 = st.columns(2)
                    current_level = c1.slider("Nivel actual DD", 0.0, 10.0, float(payload.get("current_level") or 0), .5, key=f"dd360_level_{player_id}")
                    potential = c2.slider("Proyección DD", 0.0, 10.0, float(payload.get("potential_score") or 0), .5, key=f"dd360_pot_{player_id}")
                    save_model = st.form_submit_button("Guardar evaluación de modelo", type="primary", use_container_width=True)
                if save_model:
                    with session_scope() as session:
                        active = repo.get_active_season(session)
                        if not active:
                            st.error("No hay temporada activa.")
                        else:
                            existing = next((d for d in planning_repo.list_season_decisions(session, active.id) if d.player_id == int(player_id)), None)
                            planning_repo.upsert_season_decision(
                                session, user["id"], season_id=active.id, player_id=int(player_id),
                                status=existing.status if existing else (profile.final_decision or "Seguimiento"),
                                priority=existing.priority if existing else 2, model_role_id=role.id,
                                director_note=existing.director_note if existing else profile.director_summary,
                                fit_score=profile.fit_score, current_level=current_level or None, potential_score=potential or None,
                                criteria_scores=scores,
                            )
                    st.success("Evaluación DD del modelo guardada.")
                    st.rerun()

    st.divider()
    st.markdown("### Documentos del jugador")
    st.caption("La ficha ejecutiva resume la decisión en 1-2 páginas. El dossier 360 conserva evolución, evidencia y comparaciones. Ninguno inventa datos ausentes.")
    c1,c2 = st.columns(2)
    if c1.button("Preparar ficha Scout ejecutiva", use_container_width=True, key=f"prep_exec_{player_id}"):
        st.session_state[f"player_exec_pdf_{player_id}"] = generate_player_executive_pdf(payload, settings)
    if c2.button("Preparar dossier Player Report 360", use_container_width=True, key=f"prep_360_{player_id}"):
        st.session_state[f"player_360_pdf_{player_id}"] = generate_player_360_pdf(payload, settings)
    if st.session_state.get(f"player_exec_pdf_{player_id}"):
        st.download_button("Descargar ficha Scout ejecutiva", data=st.session_state[f"player_exec_pdf_{player_id}"], file_name=player_report_filename(payload, "executive"), mime="application/pdf", use_container_width=True, key=f"download_exec_{player_id}")
    if st.session_state.get(f"player_360_pdf_{player_id}"):
        st.download_button("Descargar dossier Player Report 360", data=st.session_state[f"player_360_pdf_{player_id}"], file_name=player_report_filename(payload, "360"), mime="application/pdf", use_container_width=True, key=f"download_360_{player_id}")


def _observed(user: dict) -> None:
    with session_scope() as session:
        active = repo.get_active_season(session)
        rows = repo.player_rankings(session, min_observations=1, season_id=active.id if active else None, limit=400)
        profiles = {p.player_id: p for p in scout_repo.list_profiles(session, limit=500)}
    if not rows:
        st.info("Todavía no hay jugadores rivales observados en informes aprobados.")
        return
    c1, c2 = st.columns([2,1])
    search = c1.text_input("Buscar jugador", placeholder="Nombre")
    min_rating = c2.slider("Nota mínima", 0.0, 10.0, 0.0, .5)
    visible = [r for r in rows if r["avg_general"] >= min_rating and (not search.strip() or search.lower() in r["full_name"].lower())]
    st.dataframe(_observed_table(visible), hide_index=True, use_container_width=True)
    labels = {int(r["player_id"]): f"{r['full_name']} · {r.get('primary_position') or '-'} · {r['avg_general']:.2f}" for r in visible}
    if not labels:
        return
    pid = st.selectbox("Abrir jugador", list(labels), format_func=lambda x: labels[x])
    if st.button("Abrir Player Report 360", type="primary", use_container_width=True, key=f"open360_observed_{pid}"):
        st.session_state["scouted_player_360_id"] = int(pid)
        st.rerun()
    profile = profiles.get(pid)
    if user["role"] in {"director", "admin"}:
        if profile is None:
            if st.button("Crear ficha scout / ubicar en nuestro modelo", type="primary", use_container_width=True):
                with session_scope() as session:
                    scout_repo.request_profile(session, player_id=pid, actor_id=user["id"])
                st.rerun()
        else:
            _director_profile(profile, user)
    else:
        if profile:
            st.info(f"Dirección Deportiva lo tiene como: {scout_repo.SCOUT_STATUSES.get(profile.status, profile.status)} · {profile.model_position or '-'} · {profile.model_role or 'rol por definir'}")


def _assigned(user: dict) -> None:
    with session_scope() as session:
        profiles = scout_repo.list_profiles(session, assigned_to=user["id"], limit=100)
    if not profiles:
        st.info("No tienes fichas scout solicitadas.")
        return
    labels = {p.id: f"{p.player.full_name} · {scout_repo.SCOUT_STATUSES.get(p.status, p.status)}" for p in profiles}
    profile_id = st.selectbox("Ficha asignada", list(labels), format_func=lambda x: labels[x])
    profile = next(p for p in profiles if p.id == profile_id)
    with session_scope() as session:
        review = scout_repo.get_or_create_review(session, profile.id, user["id"])
    _review_form(profile, review, user)


def _scouted(user: dict) -> None:
    with session_scope() as session:
        profiles = scout_repo.list_profiles(session, status="scouted", limit=300)
    if not profiles:
        st.info("Todavía no hay fichas scout cerradas por Dirección Deportiva.")
        return
    st.dataframe(pd.DataFrame([{
        "Jugador": p.player.full_name, "Modelo POS": p.model_position or "-", "Rol": p.model_role or "-",
        "Encaje": p.fit_score, "Nivel": p.current_level, "Proyección": p.potential_score,
        "Decisión": p.final_decision or "Sin decidir",
    } for p in profiles]), hide_index=True, use_container_width=True)
    labels = {p.id: p.player.full_name for p in profiles}
    pid = st.selectbox("Ver expediente", list(labels), format_func=lambda x: labels[x])
    profile = next(p for p in profiles if p.id == pid)
    st.markdown(f"### {profile.player.full_name}")
    st.write(profile.director_summary or "Sin conclusión de Dirección Deportiva.")
    if st.button("Abrir Player Report 360", type="primary", use_container_width=True, key=f"open360_scouted_{profile.player_id}"):
        st.session_state["scouted_player_360_id"] = int(profile.player_id)
        st.rerun()


def render(user: dict) -> None:
    page_header("Jugadores ojeados", "El postpartido detecta. Dirección Deportiva decide si merece una ficha scout, lo ubica en nuestro modelo y cierra el expediente.")
    opened = st.session_state.get("scouted_player_360_id")
    if opened:
        _render_player_360(int(opened), user)
        return
    if user["role"] == "reporter":
        sections = ["Observados", "Mis fichas solicitadas", "Ojeados"]
    elif user["role"] == "scout":
        sections = ["Observados", "Ojeados"]
    else:
        sections = ["Observados", "Fichas solicitadas", "Ojeados"]
    section = st.selectbox("Sección", sections, key="scouted_section")
    if section == "Observados":
        _observed(user)
    elif section in {"Mis fichas solicitadas", "Fichas solicitadas"}:
        if user["role"] == "reporter":
            _assigned(user)
        else:
            with session_scope() as session:
                profiles = [p for p in scout_repo.list_profiles(session, limit=200) if p.status in {"candidate", "requested", "in_review"}]
            if not profiles:
                st.info("No hay fichas scout abiertas.")
            else:
                labels = {p.id: f"{p.player.full_name} · {scout_repo.SCOUT_STATUSES.get(p.status,p.status)}" for p in profiles}
                selected = st.selectbox("Ficha", list(labels), format_func=lambda x: labels[x])
                profile = next(p for p in profiles if p.id == selected)
                _director_profile(profile, user)
                if profile.assigned_to == user["id"]:
                    with session_scope() as session:
                        review = scout_repo.get_or_create_review(session, profile.id, user["id"])
                    _review_form(profile, review, user)
    else:
        _scouted(user)
