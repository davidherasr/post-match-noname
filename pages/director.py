from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core.constants import FOLLOW_UP_STATUSES, FORMATIONS, POSITIONS, RECOMMENDATIONS
from core.database import session_scope
from core.formations import slots_for
from core.performance import clear_performance_events, measure, performance_events, performance_summary
from core.utils import safe_html
from repositories import advanced_scouting as scout_repo
from repositories import league_intelligence as league_repo
from repositories import scouting as repo
from repositories import planning as planning_repo
from services.export_service import analytics_export_xlsx, technical_backup_zip
from ui.styles import page_header

DECISION_STATES = ["Base", "Interesante", "Seguimiento", "Prioritario", "Descartado"]
PRIORITY_LABELS = {1: "Alta", 2: "Media", 3: "Baja", 4: "Archivo"}


def _age(dob) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _season_context():
    with session_scope() as session:
        active = repo.get_active_season(session)
        seasons = repo.list_seasons(session, active_only=True)
    return active, seasons


def _ranking_frame(rows: list[dict], team_map: dict[int, dict], profiles: dict[int, object]) -> pd.DataFrame:
    data = []
    for row in rows:
        pid = int(row["player_id"])
        conf = league_repo.confidence_score(row["observations"], row["reporter_count"], row["rating_dispersion"], row.get("last_observed"))
        profile = profiles.get(pid)
        data.append({
            "Jugador": row["full_name"], "Equipo": team_map.get(pid, {}).get("team_name", "-"),
            "POS": row.get("observed_position") or row.get("primary_position") or "-", "Edad": _age(row.get("date_of_birth")) or "-",
            "Obs.": row["observations"], "Media": round(row["avg_general"], 2), "Dest.": row["standouts"],
            "Informadores": row["reporter_count"], "Confianza": f"{conf['score']}/100 · {conf['label']}",
            "Estado": profile.decision_status if profile else "Base", "Última": row.get("last_observed"),
        })
    return pd.DataFrame(data)


def _panorama(user: dict) -> None:
    active, _ = _season_context()
    season_id = active.id if active else None
    with measure("DD · Panorama", "director"):
        with session_scope() as session:
            metrics = repo.league_panorama(session, season_id=season_id)
            queue = league_repo.enhanced_decision_queue(session, season_id=season_id, limit=10)
            highlights = repo.recent_rival_highlights(session, limit=8, minimum_rating=8.0)
            trends = league_repo.robust_trends(session, season_id=season_id, min_observations=4, limit=8)
            teams = repo.league_team_summaries(session, season_id=season_id)
            open_scouts = [p for p in scout_repo.list_profiles(session, limit=200) if p.status in {"candidate", "requested", "in_review"}]
    st.caption(f"{active.name if active else 'Todas las temporadas'} · solo nuestra liga")
    k = st.columns(6)
    k[0].metric("Jugadores vistos", metrics["players_observed"])
    k[1].metric("2+ observaciones", metrics["players_repeated"])
    k[2].metric("Seguimiento", metrics["followups_active"])
    k[3].metric("Prioritarios", metrics["priority_players"])
    k[4].metric("Fichas scout abiertas", len(open_scouts))
    k[5].metric("Informes por revisar", metrics["reports_pending_review"])

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Requieren atención")
        if not queue:
            st.success("No hay perfiles que necesiten decisión ahora mismo.")
        for row in queue:
            with st.container(border=True):
                a, b = st.columns([4, 1])
                a.markdown(f"**{safe_html(row['full_name'])}** · {safe_html(row.get('team_name') or '-')}", unsafe_allow_html=True)
                a.caption(f"{row.get('observed_position') or row.get('primary_position') or '-'} · " + " · ".join(row["reasons"]))
                b.metric("Media", f"{row['avg_general']:.2f}")
                st.caption(f"Confianza {row['confidence_score']}/100 · {row['confidence']} · {row['observations']} observaciones")
                if st.button("Abrir expediente", key=f"attention_{row['player_id']}", use_container_width=True):
                    st.session_state["director_player_id"] = int(row["player_id"])
                    st.session_state["director_section"] = "Jugadores"
                    st.rerun()
    with right:
        st.subheader("Destacados recientes")
        if highlights:
            st.dataframe(pd.DataFrame([{
                "Jugador": x["player"].full_name, "Nota": x["evaluation"].general_rating,
                "Partido": f"{x['match'].home_team.name} - {x['match'].away_team.name}", "Fecha": x["match"].match_date,
            } for x in highlights]), hide_index=True, use_container_width=True)
        else:
            st.info("Aparecerán al aprobar informes con notas altas.")

    st.subheader("Evolución reciente")
    if trends:
        st.dataframe(pd.DataFrame([{
            "Jugador": r["full_name"], "Obs.": r["observations"], "Inicio": round(r["early_average"], 2),
            "Reciente": round(r["recent_average"], 2), "Δ": round(r["delta"], 2), "Tendencia": r["direction"],
            "Fiabilidad": r["trend_reliability"], "Variabilidad": round(r["dispersion"], 2),
        } for r in trends]), hide_index=True, use_container_width=True)
    else:
        st.caption("Se activa con al menos cuatro observaciones; compara ventanas no solapadas, no solo primera vs última.")

    st.subheader("Equipos de la liga")
    if teams:
        st.dataframe(pd.DataFrame([{
            "Equipo": r["team_name"], "Partidos": int(r["matches"] or 0), "Jugadores": int(r["players"] or 0),
            "Media": round(float(r["avg_rating"] or 0), 2), "Destacados": int(r["standouts"] or 0), "Última": r["last_observed"],
        } for r in teams]), hide_index=True, use_container_width=True)


def _player_360(user: dict, player_id: int) -> None:
    with measure("DD · Expediente 360", "director"):
        with session_scope() as session:
            from models.entities import Player
            player = session.get(Player, int(player_id))
            history = repo.player_history_by_scope(session, int(player_id), scope="rival")
            profile = repo.get_league_profile(session, int(player_id))
            followup = repo.get_follow_up_for_player(session, int(player_id))
            team_map = repo.latest_player_team_map(session, [int(player_id)])
            positions = league_repo.observed_position_counts(session, int(player_id))
            scout_profile = scout_repo.get_profile(session, int(player_id))
            active_season = repo.get_active_season(session)
            evidence = planning_repo.scouting_evidence_summary(session, int(player_id), season_id=active_season.id if active_season else None)
    if not player:
        st.error("Jugador no encontrado."); return
    ratings = [float(x["evaluation"].general_rating) for x in history if x["evaluation"].general_rating is not None]
    avg = sum(ratings) / len(ratings) if ratings else None
    reporter_count = len({x["reporter"].id for x in history})
    dispersion = ((sum((v - avg) ** 2 for v in ratings) / len(ratings)) ** .5) if ratings else 0.0
    conf = league_repo.confidence_score(len(ratings), reporter_count, dispersion, history[0]["match"].match_date if history else None)
    team_name = team_map.get(int(player_id), {}).get("team_name", "-")

    st.markdown(f"### {safe_html(player.display_name or player.full_name)}", unsafe_allow_html=True)
    st.caption(f"{team_name} · Posiciones observadas: " + (" · ".join(f"{p['position']} ({p['observations']})" for p in positions) if positions else player.primary_position or "-"))
    k = st.columns(6)
    k[0].metric("Media", "-" if avg is None else f"{avg:.2f}"); k[1].metric("Observaciones", len(ratings))
    k[2].metric("Informadores", reporter_count); k[3].metric("Última", "-" if not ratings else f"{ratings[0]:.1f}")
    k[4].metric("Dispersión", f"{dispersion:.2f}"); k[5].metric("Confianza", f"{conf['score']}/100")
    st.caption(f"Confianza {conf['label']}: {conf['consensus']} consenso · recencia {conf['recency']}")
    if evidence["specific_observations"]:
        st.success(
            f"Evidencia scout específica: {evidence['specific_observations']} observaciones · "
            f"{evidence['specific_scouts']} scouts · fuerza {evidence['specific_strength']}. "
            "Se muestra como evidencia intencionada; no multiplica artificialmente la nota postpartido."
        )
    else:
        st.caption("Todavía no hay observaciones scout específicas; la confianza procede del postpartido.")
    component_cols = st.columns(4)
    for col, (name, component) in zip(component_cols, conf["components"].items()):
        col.metric(name, f"{component['score']}/{component['max']}", component["detail"], delta_color="off")

    if len(history) >= 2:
        chart = pd.DataFrame([{"Fecha": x["match"].match_date, "Nota": float(x["evaluation"].general_rating)} for x in reversed(history) if x["evaluation"].general_rating is not None]).set_index("Fecha")
        st.line_chart(chart)

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Observaciones")
        for item in history[:12]:
            ev, match = item["evaluation"], item["match"]
            with st.container(border=True):
                pos = item["participation"].position if item.get("participation") else player.primary_position or "-"
                st.markdown(f"**{match.match_date.strftime('%d/%m/%Y')} · {ev.general_rating:.1f} · {pos}**")
                st.caption(f"{match.home_team.name} - {match.away_team.name} · {item['reporter'].full_name}")
                st.write(ev.short_note or "Sin observación escrita.")
    with right:
        st.subheader("Decisión DD")
        with st.form(f"director_profile_{player_id}"):
            current_status = profile.decision_status if profile else "Base"
            status = st.selectbox("Estado", DECISION_STATES, index=DECISION_STATES.index(current_status) if current_status in DECISION_STATES else 0)
            priority = st.selectbox("Prioridad", [1,2,3,4], index=(profile.priority - 1) if profile else 2, format_func=lambda x: PRIORITY_LABELS[x])
            note = st.text_area("Conclusión DD", value=profile.director_note if profile else "", height=120)
            save = st.form_submit_button("Guardar decisión", type="primary", use_container_width=True)
        if save:
            with session_scope() as session:
                repo.upsert_league_profile(session, player_id, user["id"], decision_status=status, priority=priority, director_note=note.strip() or None)
            st.success("Decisión guardada."); st.rerun()
        if scout_profile:
            st.info(f"Ficha scout: {scout_repo.SCOUT_STATUSES.get(scout_profile.status, scout_profile.status)} · {scout_profile.model_position or '-'} · {scout_profile.model_role or 'rol por definir'}")
            if st.button("Abrir Jugadores ojeados", type="primary", use_container_width=True):
                st.session_state["main_navigation"] = "Jugadores ojeados"; st.rerun()
        else:
            if st.button("Abrir ficha scout / ubicar en nuestro modelo", type="primary", use_container_width=True):
                with session_scope() as session:
                    scout_repo.request_profile(session, player_id=player_id, actor_id=user["id"], model_position=positions[0]["position"] if positions else player.primary_position)
                st.session_state["main_navigation"] = "Jugadores ojeados"; st.rerun()

        st.subheader("Seguimiento")
        with st.form(f"followup_{player_id}"):
            fstatus = st.selectbox("Estado seguimiento", FOLLOW_UP_STATUSES, index=FOLLOW_UP_STATUSES.index(followup.status) if followup and followup.status in FOLLOW_UP_STATUSES else 1)
            fpriority = st.selectbox("Prioridad seguimiento", [1,2,3,4], index=(followup.priority-1) if followup else 1, format_func=lambda x: PRIORITY_LABELS[x])
            next_date = st.date_input("Próxima revisión", value=followup.next_review_date if followup and followup.next_review_date else date.today()+timedelta(days=14))
            fnote = st.text_area("Nota", value=followup.note or "" if followup else "")
            fsave = st.form_submit_button("Guardar seguimiento", use_container_width=True)
        if fsave:
            with session_scope() as session:
                repo.upsert_follow_up(session, player_id, fstatus, fpriority, fnote.strip() or None, user["id"], next_review_date=next_date)
            st.success("Seguimiento actualizado."); st.rerun()


def _players(user: dict) -> None:
    active, _ = _season_context(); season_id = active.id if active else None
    c1, c2, c3 = st.columns(3)
    search = c1.text_input("Buscar jugador")
    position = c2.selectbox("Posición observada", ["Todas"] + POSITIONS)
    min_obs = c3.selectbox("Mínimo observaciones", [1,2,3,4,5], index=0)
    page = int(st.number_input("Página", min_value=1, value=1, step=1, key="director_players_page"))
    per_page = 50
    with session_scope() as session:
        rows = repo.player_rankings(
            session, min_observations=min_obs, position=position, season_id=season_id,
            search=search, limit=per_page, offset=(page-1)*per_page,
        )
        teams = repo.latest_player_team_map(session, [int(r["player_id"]) for r in rows])
        profiles = {p.player_id: p for p in repo.list_league_profiles(session)}
    if not rows:
        st.info("No hay jugadores con esos filtros."); return
    st.caption(f"Página {page} · hasta {per_page} jugadores · consulta filtrada en PostgreSQL")
    st.dataframe(_ranking_frame(rows, teams, profiles), hide_index=True, use_container_width=True)
    labels = {int(r["player_id"]): f"{r['full_name']} · {teams.get(int(r['player_id']),{}).get('team_name','-')} · {r['avg_general']:.2f}" for r in rows}
    default_pid = st.session_state.pop("director_player_id", None)
    ids = list(labels); idx = ids.index(default_pid) if default_pid in ids else 0
    pid = st.selectbox("Abrir expediente", ids, index=idx, format_func=lambda x: labels[x])
    _player_360(user, pid)


def _positions() -> None:
    active, _ = _season_context(); season_id = active.id if active else None
    c1, c2 = st.columns(2)
    pos = c1.selectbox("Posición observada", POSITIONS)
    min_obs = c2.selectbox("Mínimo de observaciones en esa posición", [1,2,3,4], index=0)
    with session_scope() as session:
        rows = league_repo.ranking_for_observed_position(session, pos, season_id=season_id, min_observations=min_obs, limit=100)
        teams = repo.latest_player_team_map(session, [int(r["player_id"]) for r in rows])
        profiles = {p.player_id: p for p in repo.list_league_profiles(session)}
    st.caption("El ranking usa la posición en la que lo vimos, no solo su posición principal de ficha.")
    if rows: st.dataframe(_ranking_frame(rows, teams, profiles), hide_index=True, use_container_width=True)
    else: st.info("Sin muestra suficiente en esta posición.")


def _teams() -> None:
    active, _ = _season_context(); season_id = active.id if active else None
    with session_scope() as session:
        summaries = repo.league_team_summaries(session, season_id=season_id)
    if not summaries:
        st.info("Todavía no hay rivales analizados."); return
    labels = {int(r["team_id"]): r["team_name"] for r in summaries}
    team_id = st.selectbox("Equipo rival", list(labels), format_func=lambda x: labels[x])
    with measure("DD · Dossier rival", "director"):
        with session_scope() as session:
            bundle = league_repo.team_intelligence(session, team_id, season_id=season_id)
    st.markdown(f"### {safe_html(bundle['team'].name if bundle.get('team') else labels[team_id])}", unsafe_allow_html=True)
    k = st.columns(4)
    k[0].metric("Jugadores conocidos", bundle["known"]); k[1].metric("Destacados", bundle["standouts"])
    k[2].metric("Seguimiento", bundle["followups"]); k[3].metric("Prioritarios", bundle["priority"])
    if bundle["latest_match"]:
        st.caption(f"Último enfrentamiento: {bundle['latest_match'].match_date.strftime('%d/%m/%Y')} · {bundle['latest_match'].home_team.name} - {bundle['latest_match'].away_team.name}")
    if bundle.get("known_xi"):
        st.subheader("Último XI conocido")
        st.dataframe(pd.DataFrame([{
            "#": x.get("shirt_number") or "-", "Jugador": x["full_name"], "POS": x["position"]
        } for x in bundle["known_xi"]]), hide_index=True, use_container_width=True)
    if bundle.get("interest"):
        st.subheader("Los que más nos interesan")
        st.dataframe(pd.DataFrame([{
            "Jugador": r["full_name"], "POS": r.get("primary_position") or "-", "Obs.": r["observations"],
            "Media": round(r["avg_general"],2), "Dest.": r["standouts"], "Conf.": f"{r.get('confidence_score',0)}/100",
            "Estado": r["decision_status"], "Seguimiento": r["followup_status"] or "-",
        } for r in bundle["interest"]]), hide_index=True, use_container_width=True)
    if bundle.get("most_observed"):
        st.subheader("Los que mejor conocemos")
        st.dataframe(pd.DataFrame([{
            "Jugador": r["full_name"], "POS": r.get("primary_position") or "-", "Obs.": r["observations"],
            "Media": round(r["avg_general"],2), "Última": r.get("last_observed")
        } for r in bundle["most_observed"]]), hide_index=True, use_container_width=True)


def _followups(user: dict) -> None:
    with session_scope() as session:
        items = repo.list_follow_ups(session)
    if not items:
        st.info("No hay jugadores en seguimiento."); return
    today = date.today(); end_week = today + timedelta(days=7)
    groups = {
        "Vencidos": [x for x in items if x.next_review_date and x.next_review_date < today and x.status not in {"Descartado","Cerrado"}],
        "Esta semana": [x for x in items if x.next_review_date and today <= x.next_review_date <= end_week and x.status not in {"Descartado","Cerrado"}],
        "Próximos": [x for x in items if (x.next_review_date is None or x.next_review_date > end_week) and x.status not in {"Descartado","Cerrado"}],
    }
    for title, group in groups.items():
        st.subheader(title)
        if not group: st.caption("Nada pendiente."); continue
        for item in sorted(group, key=lambda x: x.next_review_date or date.max):
            with st.container(border=True):
                c1, c2, c3 = st.columns([3,1,1])
                c1.markdown(f"**{item.player.full_name}**")
                context=[item.status]
                if item.assignee: context.append(f"Responsable: {item.assignee.full_name}")
                if item.target_match: context.append(f"Objetivo: {item.target_match.home_team.name} - {item.target_match.away_team.name}")
                if item.note: context.append(item.note)
                c1.caption(" · ".join(context))
                c2.metric("Prioridad", PRIORITY_LABELS.get(item.priority, item.priority)); c3.metric("Revisión", item.next_review_date.strftime('%d/%m') if item.next_review_date else "Sin fecha")
                a,b,c=st.columns(3)
                if a.button("Abrir jugador",key=f"fu_open_{item.id}",use_container_width=True):
                    st.session_state["director_player_id"]=item.player_id; st.session_state["director_section"]="Jugadores"; st.rerun()
                if b.button("+7 días",key=f"fu_week_{item.id}",use_container_width=True):
                    with session_scope() as session:
                        repo.upsert_follow_up(session,item.player_id,item.status,item.priority,item.note,user["id"],assigned_to=item.assigned_to,next_review_date=(item.next_review_date or date.today())+timedelta(days=7),target_match_id=item.target_match_id,expected_revision=item.revision)
                    st.rerun()
                if c.button("Completar",key=f"fu_done_{item.id}",use_container_width=True):
                    with session_scope() as session:
                        repo.upsert_follow_up(session,item.player_id,"Cerrado",item.priority,item.note,user["id"],assigned_to=item.assigned_to,next_review_date=None,target_match_id=item.target_match_id,closed_reason="Seguimiento completado",expected_revision=item.revision)
                    st.rerun()


def _compare() -> None:
    active, _ = _season_context(); season_id = active.id if active else None
    with session_scope() as session:
        rows = repo.player_rankings(session, min_observations=1, season_id=season_id, limit=300)
        teams = repo.latest_player_team_map(session, [int(r["player_id"]) for r in rows])
        model_roles = planning_repo.list_model_roles(session)
        decisions = planning_repo.list_season_decisions(session, season_id) if season_id else []
    role_options=[None]+[r.id for r in model_roles]
    role_id=st.selectbox("Comparar para nuestro modelo",role_options,format_func=lambda rid:"Comparación general" if rid is None else next(f"{r.position} · {r.name}" for r in model_roles if r.id==rid))
    labels = {int(r["player_id"]): f"{r['full_name']} · {teams.get(int(r['player_id']),{}).get('team_name','-')}" for r in rows}
    selected = st.multiselect("Comparar 2-4 jugadores", list(labels), max_selections=4, format_func=lambda x: labels[x])
    if len(selected) < 2: st.info("Selecciona al menos dos."); return
    decision_map={(d.player_id,d.model_role_id):d for d in decisions}
    frame = []
    criterion_rows=[]
    with session_scope() as session:
        criteria=planning_repo.list_model_criteria(session,role_id) if role_id else []
        for pid in selected:
            row = next(r for r in rows if int(r["player_id"]) == pid)
            conf = league_repo.confidence_score(row["observations"], row["reporter_count"], row["rating_dispersion"], row.get("last_observed"))
            positions = league_repo.observed_position_counts(session, pid, season_id=season_id)
            history = repo.player_history(session, pid)
            recent = [float(h["evaluation"].general_rating) for h in history[:3] if h["evaluation"].general_rating is not None]
            decision=decision_map.get((pid,role_id)) if role_id else next((d for d in decisions if d.player_id==pid),None)
            observations=planning_repo.list_observations(session,player_id=pid,limit=30)
            specific=[o for o in observations if o.status=="submitted"]
            last_fit=next((o.model_fit_score for o in specific if o.model_fit_score is not None),None)
            frame.append({"Jugador": row["full_name"], "Equipo": teams.get(pid,{}).get("team_name","-"), "Media": round(row["avg_general"],2), "Últimos 3": round(sum(recent)/len(recent),2) if recent else None, "Obs. postpartido": row["observations"], "Obs. scout": len(specific), "Dest.": row["standouts"], "Confianza": f"{conf['score']}/100", "Encaje DD": decision.fit_score if decision else None, "Último encaje scout":last_fit, "Posiciones": ", ".join(p["position"] for p in positions[:3])})
            if criteria:
                scores={c.id:[] for c in criteria}
                for obs in specific:
                    try: data=__import__('json').loads(obs.attributes_json or '{}')
                    except Exception: data={}
                    if int(data.get('model_role_id') or 0)!=int(role_id): continue
                    for c in criteria:
                        value=data.get(str(c.id))
                        if value is not None: scores[c.id].append(float(value))
                criterion_rows.append({"Jugador":row["full_name"],**{c.name:(round(sum(scores[c.id])/len(scores[c.id]),2) if scores[c.id] else None) for c in criteria}})
    st.dataframe(pd.DataFrame(frame), hide_index=True, use_container_width=True)
    if criterion_rows:
        st.markdown("#### Criterios de nuestro modelo")
        st.dataframe(pd.DataFrame(criterion_rows),hide_index=True,use_container_width=True)


def _best_xi(user: dict) -> None:
    active, _ = _season_context(); season_id = active.id if active else None
    c1, c2, c3 = st.columns(3)
    formation = c1.selectbox("Formación", [f for f in FORMATIONS if f != "Personalizada"], index=0)
    min_obs = c2.selectbox("Mínimo de observaciones", [1,2,3,4,5], index=1)
    criterion = c3.selectbox("Criterio", ["Mejor media", "Mayor confianza", "Forma reciente", "Selección DD"])
    f1, f2 = st.columns(2)
    confidence_min = f1.selectbox("Confianza mínima", ["Cualquiera", "Media", "Alta"], index=0)
    dd_filter = f2.selectbox("Estado DD", ["Todos", "Seguimiento/prioritarios", "Solo prioritarios"], index=0)
    with session_scope() as session:
        pool = league_repo.position_candidate_pool(session, season_id=season_id, min_observations=min_obs)
        profiles = {p.player_id:p for p in repo.list_league_profiles(session)}
        trends = {r["player_id"]: r for r in league_repo.robust_trends(session, season_id=season_id, min_observations=max(4,min_obs), limit=500)}
    by_pos: dict[str,list[dict]] = {}
    rank = {"Baja": 0, "Media": 1, "Alta": 2}
    for r in pool:
        profile = profiles.get(r["player_id"])
        r["decision_status"] = profile.decision_status if profile else "Base"
        r["recent_score"] = trends.get(r["player_id"],{}).get("recent_average", r["avg_general"])
        if confidence_min != "Cualquiera" and rank.get(r.get("confidence"), 0) < rank[confidence_min]:
            continue
        if dd_filter == "Seguimiento/prioritarios" and r["decision_status"] not in {"Seguimiento", "Prioritario"}:
            continue
        if dd_filter == "Solo prioritarios" and r["decision_status"] != "Prioritario":
            continue
        by_pos.setdefault(r["observed_position"], []).append(r)
    def score(r):
        if criterion == "Mayor confianza": return (r["confidence_score"], r["avg_general"])
        if criterion == "Forma reciente": return (r["recent_score"], r["confidence_score"])
        if criterion == "Selección DD": return (r["decision_status"] == "Prioritario", r["decision_status"] == "Seguimiento", r["avg_general"])
        return (r["avg_general"], r["confidence_score"])
    used=set(); xi=[]
    for slot in slots_for(formation):
        candidates=sorted(by_pos.get(slot.code,[]), key=score, reverse=True)
        chosen=next((r for r in candidates if r["player_id"] not in used), None)
        if chosen: used.add(chosen["player_id"])
        xi.append((slot,chosen))
    st.caption("Propuesta por posición realmente observada y filtros de DD. Puedes sustituir cualquier nombre antes de guardarlo.")
    editable=[]
    for idx,(slot,chosen) in enumerate(xi):
        candidates=sorted(by_pos.get(slot.code,[]), key=score, reverse=True)
        opts=[None]+[r["player_id"] for r in candidates if r["player_id"] not in {x.get("player_id") for x in editable if x}]
        current=chosen["player_id"] if chosen else None
        a,b=st.columns([1.5,4])
        a.markdown(f"**{slot.label}**"); a.caption(slot.code)
        selected=b.selectbox(f"Jugador {idx+1}", opts, index=opts.index(current) if current in opts else 0, format_func=lambda pid: "Sin propuesta" if pid is None else next(f"{r['full_name']} · {r['avg_general']:.2f} · {r['confidence_score']}/100" for r in candidates if r["player_id"]==pid), key=f"xi34_{idx}", label_visibility="collapsed")
        editable.append(next((r for r in candidates if r["player_id"]==selected), None))
    if st.button("Guardar XI como lista", type="primary", use_container_width=True):
        with session_scope() as session:
            item=repo.create_scouting_list(session,user["id"],name=f"XI de la liga · {formation}",list_type="xi",formation=formation,season_id=season_id)
            for idx,(slot,chosen) in enumerate(zip(slots_for(formation),editable)):
                if chosen: repo.add_scouting_list_item(session,item.id,chosen["player_id"],user["id"],position=slot.code,order_index=idx)
        st.success("XI guardado como lista editable.")


def _lists(user: dict) -> None:
    active,_=_season_context(); season_id=active.id if active else None
    with session_scope() as session:
        lists=repo.list_scouting_lists(session); rows=repo.player_rankings(session,1,season_id=season_id,limit=400)
    with st.form("create_scouting_list_33"):
        c1,c2=st.columns(2); name=c1.text_input("Nombre"); kind=c2.selectbox("Tipo",["custom","shortlist","xi"],format_func=lambda x:{"custom":"Lista","shortlist":"Lista corta","xi":"XI"}[x])
        desc=st.text_area("Descripción (opcional)"); create=st.form_submit_button("Crear lista",type="primary",use_container_width=True)
    if create and name.strip():
        with session_scope() as session: repo.create_scouting_list(session,user["id"],name=name.strip(),description=desc.strip() or None,list_type=kind,season_id=season_id)
        st.rerun()
    if not lists: return
    selected=st.selectbox("Lista",[x.id for x in lists],format_func=lambda lid:next(x.name for x in lists if x.id==lid))
    with session_scope() as session: items=repo.list_scouting_list_items(session,selected)
    if items:
        base=pd.DataFrame([{"player_id":i.player_id,"Jugador":i.player.full_name,"POS":i.position or i.player.primary_position,"Orden":i.order_index,"Nota":i.note or ""} for i in items])
        with st.form(f"edit_list_{selected}"):
            edited=st.data_editor(base,hide_index=True,use_container_width=True,disabled=["player_id","Jugador"],column_config={"player_id":None,"Orden":st.column_config.NumberColumn(min_value=0,step=1)})
            save=st.form_submit_button("Guardar orden y notas",type="primary",use_container_width=True)
        if save:
            with session_scope() as session: repo.bulk_update_scouting_list_items(session,selected,[{"player_id":int(r.player_id),"position":r.POS,"order_index":int(r.Orden),"note":r.Nota} for r in edited.itertuples()],user["id"])
            st.success("Lista actualizada."); st.rerun()
    labels={int(r["player_id"]):f"{r['full_name']} · {r['avg_general']:.2f}" for r in rows}
    if labels:
        pid=st.selectbox("Añadir jugador",list(labels),format_func=lambda x:labels[x])
        if st.button("Añadir",use_container_width=True):
            row=next(r for r in rows if int(r["player_id"])==pid)
            with session_scope() as session: repo.add_scouting_list_item(session,selected,pid,user["id"],position=row.get("primary_position"))
            st.rerun()


def _review_reports(user: dict) -> None:
    with measure("DD · Bandeja informes", "director"):
        with session_scope() as session: queue=repo.load_review_queue(session,limit=30)
    if not queue: st.success("No hay informes pendientes de revisión."); return
    for bundle in queue:
        report=bundle["report"]; rival=[e for e in bundle["evaluations"] if e.evaluation_scope=="rival" and e.general_rating is not None]
        with st.expander(f"{report.match.home_team.name} - {report.match.away_team.name} · {report.reporter.full_name} · V{report.version}"):
            c1,c2,c3=st.columns(3); c1.metric("Rivales",len(rival)); c2.metric("Destacados",len([e for e in rival if e.standout])); c3.metric("Media","-" if not rival else f"{sum(e.general_rating for e in rival)/len(rival):.2f}")
            if rival: st.dataframe(pd.DataFrame([{"Jugador":e.player.full_name,"Nota":e.general_rating,"★":e.standout,"Comentario":e.short_note or ""} for e in rival]),hide_index=True,use_container_width=True)
            note=st.text_area("Nota de revisión",key=f"review_note33_{report.id}")
            promote=st.checkbox("Crear ficha candidata para los destacados al aprobar",value=True,key=f"promote_scout33_{report.id}")
            a,b=st.columns(2)
            if a.button("Aprobar",key=f"approve33_{report.id}",type="primary",use_container_width=True):
                with session_scope() as session:
                    repo.approve_report(session,report.id,user["id"],note.strip() or None)
                    if promote:
                        for ev in rival:
                            if ev.standout:
                                scout_repo.request_profile(session,player_id=ev.player_id,actor_id=user["id"],model_position=ev.participation.position if ev.participation else ev.player.primary_position)
                st.success("Informe aprobado. Los destacados quedan disponibles en Jugadores ojeados."); st.rerun()
            if b.button("Devolver",key=f"return33_{report.id}",use_container_width=True):
                if not note.strip(): st.error("Indica qué debe corregirse.")
                else:
                    with session_scope() as session: repo.return_report(session,report.id,user["id"],note.strip())
                    st.rerun()


def _consensus(user: dict) -> None:
    with session_scope() as session: matches=repo.list_matches(session,limit=100)
    if not matches: st.info("No hay partidos."); return
    match_id=st.selectbox("Partido",[m.id for m in matches],format_func=lambda mid:next(f"{m.match_date.strftime('%d/%m/%Y')} · {m.home_team.name} - {m.away_team.name}" for m in matches if m.id==mid))
    with session_scope() as session:
        consensus=repo.match_consensus(session,match_id); consolidation=repo.get_or_create_consolidation(session,match_id,user["id"]); existing={e.player_id:e for e in repo.list_consolidated_evaluations(session,consolidation.id)}
    if not consensus: st.info("Se necesitan informes aprobados."); return
    frame=[]
    for r in consensus:
        saved=existing.get(r["player_id"]); label="Alto" if r["sample_size"]>=3 and r["dispersion"]<=.75 else "Medio" if r["sample_size"]>=2 and r["dispersion"]<=1.25 else "Bajo"
        frame.append({"player_id":r["player_id"],"Jugador":r["player_name"],"Informes":r["sample_size"],"Media":round(r["average"],2),"Dispersión":round(r["dispersion"],2),"Consenso":label,"Nota final":saved.final_rating if saved and saved.final_rating is not None else round(r["average"],1),"Decisión final":saved.final_recommendation if saved and saved.final_recommendation else "Anotar en base de datos","Conclusión":saved.consensus_note if saved else ""})
    st.caption("Dispersión alta = opiniones más divididas. No ocultamos el desacuerdo detrás de una media.")
    with st.form(f"consensus33_{match_id}"):
        edited=st.data_editor(pd.DataFrame(frame),hide_index=True,use_container_width=True,disabled=["player_id","Jugador","Informes","Media","Dispersión","Consenso"],column_config={"player_id":None,"Nota final":st.column_config.NumberColumn(min_value=1,max_value=10,step=.1),"Decisión final":st.column_config.SelectboxColumn(options=RECOMMENDATIONS)})
        approve=st.checkbox("Aprobar consolidación"); save=st.form_submit_button("Guardar consenso",type="primary",use_container_width=True)
    if save:
        rows=[{"player_id":int(r["player_id"]),"final_rating":float(r["Nota final"]),"final_recommendation":r["Decisión final"],"consensus_note":r["Conclusión"] or None,"sample_size":int(r["Informes"]),"dispersion":float(r["Dispersión"]),"confidence_summary":r["Consenso"]} for _,r in edited.iterrows()]
        with session_scope() as session: repo.save_consolidation(session,consolidation.id,user["id"],None,None,rows,approve)
        st.rerun()


def _tools() -> None:
    st.subheader("Exportación y backup")
    if st.button("Preparar Excel analítico"):
        with measure("Exportar Excel", "admin"):
            with session_scope() as session: st.session_state["analytics_export_33"] = analytics_export_xlsx(session)
    if st.session_state.get("analytics_export_33"): st.download_button("Descargar Excel",st.session_state["analytics_export_33"],"noname_postmatch_3_3_analitica.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.warning("El backup solo se genera al pulsar el botón.")
    if st.button("Preparar backup técnico"):
        with measure("Generar backup", "admin"):
            with session_scope() as session: st.session_state["technical_backup_33"] = technical_backup_zip(session)
    if st.session_state.get("technical_backup_33"): st.download_button("Descargar backup ZIP",st.session_state["technical_backup_33"],"noname_postmatch_3_3_backup.zip","application/zip")
    st.subheader("Rendimiento de esta sesión")
    events=performance_events()
    if events:
        st.caption("Total = operación completa · DB = tiempo SQL real · Render = resto · Queries = sentencias ejecutadas.")
        st.dataframe(pd.DataFrame(events[-40:]), hide_index=True, use_container_width=True)
        summary = performance_summary()
        if summary:
            st.markdown("#### Cuellos de botella de la sesión")
            st.dataframe(pd.DataFrame(summary[:15]), hide_index=True, use_container_width=True)
        if st.button("Limpiar mediciones",use_container_width=True): clear_performance_events(); st.rerun()
    else: st.caption("Las pantallas irán registrando total, DB, render y número de consultas sin escribir eventos extra en Supabase.")


def render(user: dict) -> None:
    page_header("Dirección deportiva", "Nuestra liga convertida en decisiones: observar → decidir → solicitar ficha scout → ubicar en nuestro modelo.")
    sections=["Panorama","Jugadores","Por posiciones","Equipos","Seguimiento","Comparador","XI de la liga","Consenso","Informes","Listas"]
    if user["role"]=="admin": sections.append("Herramientas")
    section=st.selectbox("Área de Dirección Deportiva",sections,key="director_section")
    if section=="Panorama": _panorama(user)
    elif section=="Jugadores": _players(user)
    elif section=="Por posiciones": _positions()
    elif section=="Equipos": _teams()
    elif section=="Seguimiento": _followups(user)
    elif section=="Comparador": _compare()
    elif section=="XI de la liga": _best_xi(user)
    elif section=="Consenso": _consensus(user)
    elif section=="Informes": _review_reports(user)
    elif section=="Listas": _lists(user)
    else: _tools()
