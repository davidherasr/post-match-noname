from __future__ import annotations

import base64
import math
from collections import defaultdict

import pandas as pd
import streamlit as st

from core.utils import safe_html


def _fmt(value, digits: int = 1) -> str:
    return "-" if value is None else f"{float(value):.{digits}f}"


def _photo_html(player) -> str:
    if player.photo_b64:
        mime = safe_html(player.photo_mime or "image/jpeg")
        return f'<img class="pm360-avatar" src="data:{mime};base64,{player.photo_b64}" alt="Foto de {safe_html(player.display_name or player.full_name)}">'
    initials = "".join(part[:1] for part in (player.display_name or player.full_name).split()[:2]).upper() or "NN"
    return f'<div class="pm360-avatar pm360-avatar-fallback">{safe_html(initials)}</div>'


def _team_name(payload: dict) -> str:
    return payload["team"].name if payload.get("team") else "Equipo no confirmado"


def render_header(payload: dict) -> None:
    player = payload["player"]
    role = payload.get("role")
    post = payload["postmatch"]
    confidence = post["confidence"]
    meta = [player.primary_position or "Sin posición", _team_name(payload)]
    if payload.get("age") is not None:
        meta.append(f"{payload['age']} años")
    role_text = f"{role.position} · {role.name}" if role else (payload.get("profile").model_role if payload.get("profile") and payload["profile"].model_role else "Rol No Name por definir")
    st.markdown(
        f"""
        <div class="pm360-hero">
          <div class="pm360-ident">
            {_photo_html(player)}
            <div>
              <div class="pm360-kicker">Player Report 360</div>
              <div class="pm360-name">{safe_html(player.display_name or player.full_name)}</div>
              <div class="pm360-meta">{safe_html(' · '.join(meta))}</div>
              <div class="pm360-role">{safe_html(role_text)}</div>
            </div>
          </div>
          <div class="pm360-kpis">
            <div class="pm360-kpi"><span>Rendimiento</span><strong>{_fmt(post['average'])}</strong><small>{post['observations']} postpartidos</small></div>
            <div class="pm360-kpi"><span>Encaje No Name</span><strong>{_fmt(payload.get('fit_score'))}</strong><small>{safe_html(role.name if role else 'sin rol')}</small></div>
            <div class="pm360-kpi"><span>Confianza</span><strong>{confidence['score']}/100</strong><small>{safe_html(confidence['label'])}</small></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _radar_svg(criteria: list[dict], size: int = 370) -> str | None:
    rows = [r for r in criteria if r.get("score") is not None]
    if len(rows) < 3:
        return None
    # Keep the radar readable. The table below still shows every criterion.
    rows = rows[:10]
    cx = cy = size / 2
    radius = size * .29
    levels = 5
    points_count = len(rows)
    parts = [f'<svg viewBox="0 0 {size} {size}" class="pm360-radar" role="img" aria-label="Radar de criterios del Modelo No Name">']
    for level in range(1, levels + 1):
        r = radius * level / levels
        pts = []
        for i in range(points_count):
            a = -math.pi / 2 + 2 * math.pi * i / points_count
            pts.append(f"{cx + r*math.cos(a):.1f},{cy + r*math.sin(a):.1f}")
        parts.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#D8DEE8" stroke-width="1"/>')
    value_pts = []
    for i, row in enumerate(rows):
        a = -math.pi / 2 + 2 * math.pi * i / points_count
        x2, y2 = cx + radius * math.cos(a), cy + radius * math.sin(a)
        parts.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#E5E7EB" stroke-width="1"/>')
        value_r = radius * max(0, min(10, float(row["score"]))) / 10
        value_pts.append(f"{cx + value_r*math.cos(a):.1f},{cy + value_r*math.sin(a):.1f}")
        label_r = radius * 1.27
        lx, ly = cx + label_r * math.cos(a), cy + label_r * math.sin(a)
        anchor = "middle" if abs(math.cos(a)) < .25 else ("start" if math.cos(a) > 0 else "end")
        label = safe_html(row["name"][:22])
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" dominant-baseline="middle" font-size="11" fill="#596273">{label}</text>')
    parts.append(f'<polygon points="{" ".join(value_pts)}" fill="rgba(37,99,235,.22)" stroke="#2563EB" stroke-width="2.2"/>')
    parts.append('</svg>')
    return "".join(parts)


def render_summary(payload: dict) -> None:
    st.markdown("### Resumen ejecutivo")
    summary = payload.get("summary") or "Todavía no hay una conclusión consolidada del Scout o de Dirección Deportiva."
    st.markdown(f'<div class="pm360-note"><div class="pm360-note-title">Conclusión</div>{safe_html(summary)}</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### Fortalezas")
        if payload["strengths"]:
            for text in payload["strengths"]:
                st.markdown(f"- {text}")
        else:
            st.caption("Sin fortalezas consolidadas todavía.")
    with c2:
        st.markdown("#### Dudas / riesgos")
        if payload["weaknesses"]:
            for text in payload["weaknesses"]:
                st.markdown(f"- {text}")
        else:
            st.caption("Sin riesgos registrados.")
    with c3:
        st.markdown("#### Recomendación")
        st.metric("Decisión / recomendación", payload.get("recommendation") or "Sin decidir")
        st.caption(f"Scouting específico: {payload['evidence']['specific_observations']} · Fuerza de evidencia: {payload['evidence']['specific_strength']}")

    st.markdown("### Perfil observado")
    cols = st.columns(4)
    for idx, (label, value) in enumerate(payload["block_scores"].items()):
        cols[idx].metric(label, _fmt(value))
    c1, c2, c3 = st.columns(3)
    c1.metric("Nivel actual", _fmt(payload.get("current_level")))
    c2.metric("Proyección", _fmt(payload.get("potential_score")))
    c3.metric("Media Scout", _fmt(payload.get("scout_average")))


def render_model(payload: dict) -> None:
    role = payload.get("role")
    st.markdown("### Encaje en el Modelo No Name")
    if not role:
        st.info("Dirección Deportiva todavía no ha ubicado a este jugador en un rol configurado del Modelo No Name.")
        return
    st.caption(f"Rol analizado: {role.position} · {role.name}. {role.description or ''}")
    radar = _radar_svg(payload["criteria"])
    left, right = st.columns([1.05, 1])
    with left:
        if radar:
            st.markdown(radar, unsafe_allow_html=True)
        else:
            st.info("Se necesitan al menos 3 criterios puntuados para construir el radar. No se inventan valores vacíos.")
    with right:
        st.markdown("#### Criterios clave")
        rows = payload["criteria"]
        if not rows:
            st.caption("Este rol todavía no tiene criterios configurados.")
        for row in rows:
            score = row.get("score")
            score_text = "Sin valorar" if score is None else f"{score:.1f}/10"
            weight = "★" * int(row.get("weight") or 1)
            st.markdown(f'<div class="pm360-criterion"><span><b>{safe_html(row["name"])}</b><small>{safe_html(row["category"])} · {weight}</small></span><strong>{score_text}</strong></div>', unsafe_allow_html=True)

    st.markdown("#### Posiciones observadas")
    if payload["positions"]:
        st.dataframe(pd.DataFrame([{"Posición": r["position"], "Observaciones": r["observations"]} for r in payload["positions"]]), hide_index=True, use_container_width=True)
    else:
        st.caption("Sin posiciones observadas suficientes.")


def render_evolution(payload: dict) -> None:
    st.markdown("### Evolución de nuestras observaciones")
    timeline = payload["timeline"]
    if not timeline:
        st.info("Todavía no hay valoraciones con nota para construir una evolución.")
        return
    chart = pd.DataFrame([{"Fecha": x["date"], "Nota": x["rating"]} for x in timeline]).set_index("Fecha")
    st.line_chart(chart, y="Nota", height=250)
    st.dataframe(pd.DataFrame([{
        "Fecha": x["date"], "Fuente": x["source"], "Partido": x["match"], "POS": x["position"] or "-",
        "Nota": x["rating"], "Observador": x["observer"], "Apunte": x["note"],
    } for x in reversed(timeline)]), hide_index=True, use_container_width=True)


def render_observations(payload: dict) -> None:
    st.markdown("### Evidencia y observaciones")
    post = payload["postmatch"]
    ev = payload["evidence"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Postpartidos", post["observations"])
    c2.metric("Scouting específico", ev["specific_observations"])
    c3.metric("Scouts distintos", ev["specific_scouts"])
    c4.metric("Destacados", post["standouts"])
    conf = post["confidence"]
    st.markdown("#### Por qué confiamos en la muestra")
    st.dataframe(pd.DataFrame([{"Componente": name, "Puntos": f"{item['score']}/{item['max']}", "Detalle": item["detail"]} for name, item in conf["components"].items()]), hide_index=True, use_container_width=True)
    if payload["observations"]:
        st.markdown("#### Scouting específico")
        st.dataframe(pd.DataFrame([{
            "Fecha": o.observed_at.date(), "Scout": o.reviewer.full_name,
            "Partido": "-" if not o.match else f"{o.match.home_team.name} - {o.match.away_team.name}",
            "Tipo": o.source_type, "POS": o.observed_position or "-", "Nota": o.general_rating,
            "Encaje": o.model_fit_score, "Recomendación": o.recommendation or "", "Resumen": o.summary or "",
        } for o in payload["observations"]]), hide_index=True, use_container_width=True)


def _comparison_table(rows: list[dict], criteria: list[dict], title: str) -> None:
    st.markdown(f"#### {title}")
    if not rows:
        st.caption("No hay perfiles comparables con datos suficientes en este rol.")
        return
    frame = []
    criteria_ids = [r["id"] for r in criteria[:6]]
    criteria_names = {r["id"]: r["name"] for r in criteria}
    for row in rows:
        out = {"Jugador": row["name"], "Encaje": row["fit"], "Nivel": row["current_level"], "Proyección": row["potential"], "Estado": row["status"]}
        if row.get("similarity") is not None:
            out["Similitud"] = f"{row['similarity']}%"
        for cid in criteria_ids:
            if cid in row.get("criteria_scores", {}):
                out[criteria_names[cid]] = row["criteria_scores"][cid]
        frame.append(out)
    st.dataframe(pd.DataFrame(frame), hide_index=True, use_container_width=True)


def render_comparison(payload: dict) -> None:
    st.markdown("### Comparación contextual")
    st.caption("Solo se comparan perfiles reales de nuestra base vinculados al mismo rol. La similitud se calcula con criterios puntuados y, cuando falta esa información, con el encaje DD.")
    _comparison_table(payload["own_comparison"], payload["criteria"], "Nuestra plantilla")
    _comparison_table(payload["comparables"], payload["criteria"], "Perfiles similares de nuestra liga")


def render_data(payload: dict) -> None:
    player = payload["player"]
    st.markdown("### Datos disponibles")
    rows = [
        ("Nombre", player.display_name or player.full_name),
        ("Equipo observado", _team_name(payload)),
        ("Posición principal", player.primary_position or "-"),
        ("Fecha de nacimiento", player.date_of_birth.strftime("%d/%m/%Y") if player.date_of_birth else "-"),
        ("Edad", payload.get("age") if payload.get("age") is not None else "-"),
        ("Pie", player.preferred_foot or "-"),
        ("Nacionalidad", player.nationality or "-"),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Dato", "Valor"]), hide_index=True, use_container_width=True)
    st.caption("La ficha muestra únicamente datos existentes en No Name PostMatch. No completa altura, mercado, estadísticas o comparables externos de forma automática.")


def render_monthly_profile(payload: dict) -> None:
    """Compact Wyscout-inspired trend using only real No Name ratings."""
    st.markdown("### Rendimiento mensual · últimos 12 meses")
    rows = payload.get("monthly_ratings") or []
    if not rows or not any(row.get("rating") is not None for row in rows):
        st.caption("Todavía no hay suficientes valoraciones postpartido para mostrar una tendencia mensual.")
        return
    frame = pd.DataFrame([
        {"Mes": row["label"], "Rating": row.get("rating"), "Observaciones": row.get("observations", 0)}
        for row in rows
    ])
    st.bar_chart(frame.set_index("Mes")[["Rating"]], height=230)
    line = " · ".join(
        f"{row['label']}: {'—' if row.get('rating') is None else f'{row['rating']:.1f}'}"
        for row in rows
    )
    st.caption(line)


def render_season_profile(payload: dict) -> None:
    st.markdown("### Resumen por temporada")
    rows = payload.get("season_summary") or []
    if not rows:
        st.caption("Sin temporadas observadas con información suficiente.")
        return
    st.dataframe(pd.DataFrame([{
        "Temporada": row["season"],
        "Equipo observado": row.get("team") or "-",
        "Postpartidos": row.get("postmatch", 0),
        "Scout": row.get("scout", 0),
        "Rating medio": row.get("average"),
    } for row in rows]), hide_index=True, use_container_width=True)


def render_decision_block(payload: dict, next_action=None) -> None:
    st.markdown("### Dirección Deportiva")
    decision = payload.get("decision")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Estado", decision.status if decision else "Sin decisión")
        if decision:
            st.caption(f"Prioridad {decision.priority} · actualizado {decision.updated_at.strftime('%d/%m/%Y') if decision.updated_at else '-'}")
    with c2:
        if next_action:
            match = next_action.match
            when = match.kickoff_at.strftime("%d/%m/%Y · %H:%M") if match.kickoff_at else f"{match.match_date.strftime('%d/%m/%Y')} · horario pendiente"
            st.markdown(f"**Próxima acción:** {safe_html(next_action.title)}")
            st.caption(f"{match.home_team.name} - {match.away_team.name} · {when} · Responsable: {next_action.assignee.full_name}")
        else:
            st.caption("No hay una próxima acción programada.")


def render_vertical_profile(payload: dict, *, next_action=None) -> None:
    """3.8 executive player page: important information first, dossier behind it."""
    render_header(payload)
    render_summary(payload)
    render_model(payload)
    render_monthly_profile(payload)
    render_season_profile(payload)
    render_decision_block(payload, next_action=next_action)
