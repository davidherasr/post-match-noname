from __future__ import annotations

import re
from types import SimpleNamespace
from datetime import date, datetime, time, timedelta

import streamlit as st

from core.constants import FORMATIONS, POSITIONS, ROLES
from models.entities import Competition, Team
from core.database import session_scope
from core.formations import slots_for
from core.performance import measure
from core.postmatch_validation import validate_postmatch_draft
from repositories import scouting as repo
from ui.styles import page_header


DRAFT_KEY = "postmatch_32_local_draft"
CLOUD_DRAFT_KEY = "postmatch_32_cloud_draft_id"
CLOUD_DRAFT_LIST_KEY = "postmatch_32_cloud_draft_list"
CONTEXT_KEY = "postmatch_32_context_cache"
SUPPORT_PREFIX = "postmatch_32_support_"


def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


def _invalidate_context() -> None:
    st.session_state.pop(CONTEXT_KEY, None)
    for key in list(st.session_state):
        if str(key).startswith(SUPPORT_PREFIX):
            st.session_state.pop(key, None)


def _default_season_name(today: date | None = None) -> str:
    today = today or date.today()
    start = today.year if today.month >= 7 else today.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def _new_draft(active_season_id: int | None = None) -> dict:
    return {
        "season_id": active_season_id,
        "competition_id": None,
        "new_competition": "",
        "rival_id": None,
        "new_rival": "",
        "round_name": "",
        "match_date": date.today().isoformat(),
        "own_location": "Local",
        "own_score": 0,
        "rival_score": 0,
        "own_formation": "4-3-3",
        "rival_formation": "4-3-3",
        "venue": "",
        "due_enabled": False,
        "due_date": (date.today() + timedelta(days=1)).isoformat(),
        "due_time": "20:00",
        "reporter_ids": [],
        "own_xi": [],
        "own_subs": [],
        "rival_xi": [],
        "rival_subs": [],
    }


def _draft() -> dict:
    if DRAFT_KEY not in st.session_state:
        st.session_state[DRAFT_KEY] = _new_draft()
    return st.session_state[DRAFT_KEY]


def _clear_draft() -> None:
    st.session_state.pop(DRAFT_KEY, None)
    st.session_state.pop(CLOUD_DRAFT_KEY, None)
    st.session_state.pop(CLOUD_DRAFT_LIST_KEY, None)
    st.session_state.pop("postmatch_identity_conflicts_34", None)
    st.session_state.pop("postmatch_identity_resolutions_34", None)


def _to_date(value, fallback: date | None = None) -> date:
    fallback = fallback or date.today()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return fallback


def _to_time(value, fallback: time | None = None) -> time:
    fallback = fallback or time(20, 0)
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(str(value))
    except Exception:
        return fallback


def _setup_own_team(user: dict) -> None:
    st.info("Esta instalación es para No Name. Configura el equipo propio una sola vez.")
    with st.form("noname_setup_32"):
        name = st.text_input("Nombre", value="No Name")
        short = st.text_input("Nombre corto", value="NO NAME")
        save = st.form_submit_button("Configurar No Name", type="primary", use_container_width=True)
    if save and name.strip():
        with session_scope() as session:
            team = repo.create_team(session, name.strip(), short.strip() or None, None, True, user["id"])
            repo.set_setting(session, "own_team_id", str(team.id), user["id"])
            repo.set_setting(session, "club_name", team.name, user["id"])
        _invalidate_context()
        st.success("No Name configurado.")
        st.rerun()


def _setup_season(user: dict) -> None:
    st.warning("Crea la temporada activa para empezar.")
    with st.form("season_setup_32"):
        name = st.text_input("Temporada", value=_default_season_name())
        c1, c2 = st.columns(2)
        start = c1.date_input("Inicio", value=date(date.today().year, 7, 1))
        end = c2.date_input("Fin", value=date(date.today().year + 1, 6, 30))
        save = st.form_submit_button("Crear temporada", type="primary", use_container_width=True)
    if save and name.strip():
        with session_scope() as session:
            season = repo.create_season(session, name.strip(), start, end, user["id"])
            repo.set_active_season(session, season.id, user["id"])
        _invalidate_context()
        st.success("Temporada creada.")
        st.rerun()


def _load_context():
    cached = st.session_state.get(CONTEXT_KEY)
    if cached:
        return cached
    with session_scope() as session:
        own_obj = repo.get_own_team(session)
        active_obj = repo.get_active_season(session)
        season_objs = repo.list_seasons(session, active_only=True)
        competition_objs = repo.list_competitions(session, active_only=True)
        team_objs = [t for t in repo.list_teams(session, active_only=True) if not t.is_own_team]
        user_objs = [u for u in repo.list_users(session, active_only=True) if u.role in {"reporter", "admin", "director"}]
    own = _ns(id=own_obj.id, name=own_obj.name) if own_obj else None
    active = _ns(id=active_obj.id, name=active_obj.name) if active_obj else None
    seasons = [_ns(id=x.id, name=x.name) for x in season_objs]
    competitions = [_ns(id=x.id, name=x.name) for x in competition_objs]
    teams = [_ns(id=x.id, name=x.name) for x in team_objs]
    users = [_ns(id=x.id, full_name=x.full_name, role=x.role) for x in user_objs]
    cached = (own, active, seasons, competitions, teams, users)
    st.session_state[CONTEXT_KEY] = cached
    return cached


def _header(user: dict, own, active, seasons, competitions, teams, users) -> None:
    d = _draft()
    if d.get("season_id") is None and active:
        d["season_id"] = active.id
    if not d.get("round_name"):
        with session_scope() as session:
            count = len(repo.list_matches(session, season_id=active.id if active else None, limit=500))
        d["round_name"] = f"Jornada {count + 1}"
    st.markdown("### 1 · Partido")
    st.caption("Preparar estos datos no escribe en Supabase. Solo se guardará cuando tú decidas.")
    season_ids = [s.id for s in seasons]
    comp_ids = [None] + [c.id for c in competitions]
    team_ids = [None] + [t.id for t in teams]
    user_ids = [u.id for u in users]
    with st.form("postmatch_32_header", border=True):
        a, b, c = st.columns(3)
        season_id = a.selectbox("Temporada", season_ids, index=season_ids.index(d["season_id"]) if d.get("season_id") in season_ids else 0, format_func=lambda sid: next(s.name for s in seasons if s.id == sid))
        competition_id = b.selectbox("Competición", comp_ids, index=comp_ids.index(d.get("competition_id")) if d.get("competition_id") in comp_ids else 0, format_func=lambda cid: "＋ Nueva" if cid is None else next(x.name for x in competitions if x.id == cid))
        rival_id = c.selectbox("Rival", team_ids, index=team_ids.index(d.get("rival_id")) if d.get("rival_id") in team_ids else 0, format_func=lambda tid: "＋ Nuevo rival" if tid is None else next(x.name for x in teams if x.id == tid))
        x, y = st.columns(2)
        new_competition = x.text_input("Nueva competición", value=d.get("new_competition", ""), disabled=competition_id is not None, placeholder="Liga")
        new_rival = y.text_input("Nuevo rival", value=d.get("new_rival", ""), disabled=rival_id is not None, placeholder="Nombre del equipo")

        a, b, c = st.columns([1.2, 1, 1])
        round_name = a.text_input("Jornada / partido", value=d.get("round_name", ""))
        match_date = b.date_input("Fecha", value=_to_date(d.get("match_date")))
        own_location = c.radio("No Name", ["Local", "Visitante"], horizontal=True, index=0 if d.get("own_location") == "Local" else 1)
        a, b = st.columns(2)
        own_score = a.number_input(f"Goles {own.name}", 0, 30, int(d.get("own_score", 0)))
        rival_score = b.number_input("Goles rival", 0, 30, int(d.get("rival_score", 0)))
        a, b = st.columns(2)
        own_formation = a.selectbox("Sistema No Name", FORMATIONS, index=FORMATIONS.index(d.get("own_formation")) if d.get("own_formation") in FORMATIONS else 0)
        rival_formation = b.selectbox("Sistema rival", FORMATIONS, index=FORMATIONS.index(d.get("rival_formation")) if d.get("rival_formation") in FORMATIONS else 0)
        venue = st.text_input("Campo / ubicación (opcional)", value=d.get("venue", ""))
        reporter_ids = st.multiselect("Informadores", user_ids, default=[uid for uid in d.get("reporter_ids", []) if uid in user_ids], format_func=lambda uid: next(f"{u.full_name} · {ROLES.get(u.role, u.role)}" for u in users if u.id == uid))
        due_enabled = st.checkbox("Fecha límite", value=bool(d.get("due_enabled", False)))
        p, q = st.columns(2)
        due_date = p.date_input("Día límite", value=_to_date(d.get("due_date"), match_date + timedelta(days=1)), disabled=not due_enabled)
        due_time = q.time_input("Hora límite", value=_to_time(d.get("due_time")), disabled=not due_enabled)
        prepare = st.form_submit_button("Preparar alineaciones", type="primary", use_container_width=True)
    if prepare:
        if competition_id is None and not new_competition.strip():
            st.error("Selecciona o escribe una competición.")
            return
        if rival_id is None and not new_rival.strip():
            st.error("Selecciona o escribe el rival.")
            return
        d.update({
            "season_id": season_id,
            "competition_id": competition_id,
            "new_competition": new_competition.strip(),
            "rival_id": rival_id,
            "new_rival": new_rival.strip(),
            "round_name": round_name.strip(),
            "match_date": match_date.isoformat(),
            "own_location": own_location,
            "own_score": int(own_score),
            "rival_score": int(rival_score),
            "own_formation": own_formation,
            "rival_formation": rival_formation,
            "venue": venue.strip(),
            "reporter_ids": reporter_ids,
            "due_enabled": due_enabled,
            "due_date": due_date.isoformat(),
            "due_time": due_time.isoformat(timespec="minutes"),
        })
        # Regenerate only if the tactical structure changed.
        if d.get("own_xi_formation") != own_formation:
            d["own_xi"] = []
            d["own_subs"] = []
            d["own_xi_formation"] = own_formation
        if d.get("rival_xi_formation") != rival_formation:
            d["rival_xi"] = []
            d["rival_subs"] = []
            d["rival_xi_formation"] = rival_formation
        st.success("Estructura preparada. A partir de aquí solo eliges nombres y cambios.")
        st.rerun()


def _bulk_add_own_roster(user: dict, own_id: int, season_id: int) -> None:
    with st.expander("Añadir jugadores a la plantilla de No Name", expanded=False):
        st.caption("Una línea: `Nombre;POS;Dorsal`. Se procesa todo en una sola sesión.")
        with st.form("own_roster_bulk_32"):
            text = st.text_area("Pegar jugadores", placeholder="Mario;DC;9\nPablo;DFC;4", height=130)
            save = st.form_submit_button("Añadir plantilla", use_container_width=True)
        if save:
            parsed = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                p = [x.strip() for x in line.split(";")]
                parsed.append((p[0], p[1].upper() if len(p) > 1 and p[1] else "Otro", int(p[2]) if len(p) > 2 and p[2].isdigit() else None))
            if not parsed:
                st.warning("No se han detectado jugadores.")
                return
            with session_scope() as session:
                for name, position, shirt in parsed:
                    player = repo.find_or_create_player(session, name, primary_position=position if position in POSITIONS else "Otro", actor_id=user["id"])
                    repo.assign_player_to_roster(session, own_id, season_id, player.id, shirt, user["id"])
            _invalidate_context()
            st.success(f"{len(parsed)} jugadores procesados.")
            st.rerun()


def _own_support(own_id: int, season_id: int, match_date: date):
    key = f"{SUPPORT_PREFIX}own_{own_id}_{season_id}_{match_date.isoformat()}"
    cached = st.session_state.get(key)
    if cached:
        return cached
    with session_scope() as session:
        roster_objs = repo.get_roster(session, own_id, season_id)
        previous_obj = repo.previous_match_with_team(session, own_id, before_date=match_date)
        previous_parts_obj = repo.get_participations(session, previous_obj.id, own_id) if previous_obj else []
    roster = [_ns(
        player_id=x.player_id, shirt_number=x.shirt_number,
        player=_ns(id=x.player.id, display_name=x.player.display_name, full_name=x.player.full_name, primary_position=x.player.primary_position),
    ) for x in roster_objs]
    previous = _ns(id=previous_obj.id, match_date=previous_obj.match_date) if previous_obj else None
    previous_parts = [_ns(
        player_id=x.player_id, starter=x.starter, position=x.position, shirt_number=x.shirt_number,
        player=_ns(id=x.player.id, display_name=x.player.display_name, full_name=x.player.full_name, primary_position=x.player.primary_position),
    ) for x in previous_parts_obj]
    cached = (roster, previous, previous_parts)
    st.session_state[key] = cached
    return cached


def _rival_previous_support(own_id: int, rival_id: int, match_date: date):
    key = f"{SUPPORT_PREFIX}rival_{own_id}_{rival_id}_{match_date.isoformat()}"
    cached = st.session_state.get(key)
    if cached is not None:
        return cached
    with session_scope() as session:
        prev = repo.previous_match_with_team(session, own_id, before_date=match_date, opponent_id=rival_id)
        parts_obj = repo.get_participations(session, prev.id, rival_id) if prev else []
    parts = [_ns(
        player_id=x.player_id, starter=x.starter, position=x.position, shirt_number=x.shirt_number,
        player=_ns(id=x.player.id, display_name=x.player.display_name, full_name=x.player.full_name, primary_position=x.player.primary_position),
    ) for x in parts_obj]
    st.session_state[key] = parts
    return parts


def _suggest_own_xi(roster, formation: str, previous_parts=None) -> list[dict]:
    slots = slots_for(formation)
    if not slots:
        return []
    previous_parts = previous_parts or []
    previous_starters = [p for p in previous_parts if p.starter]
    previous_by_pos: dict[str, list[int]] = {}
    for p in previous_starters:
        previous_by_pos.setdefault(p.position or p.player.primary_position or "Otro", []).append(p.player_id)
    roster_by_id = {r.player_id: r for r in roster}
    used: set[int] = set()
    result = []
    for slot in slots:
        candidate = None
        for pid in previous_by_pos.get(slot.code, []):
            if pid in roster_by_id and pid not in used:
                candidate = pid
                break
        if candidate is None:
            for item in roster:
                if item.player_id in used:
                    continue
                if (item.player.primary_position or "Otro") == slot.code:
                    candidate = item.player_id
                    break
        if candidate is not None:
            used.add(candidate)
        result.append({"player_id": candidate, "position": slot.code, "role": slot.label})
    return result


def _own_lineup(user: dict, own, d: dict) -> None:
    if not d.get("season_id") or not d.get("rival_id") and not d.get("new_rival"):
        return
    st.markdown("### 2 · No Name")
    roster, previous, previous_parts = _own_support(own.id, int(d["season_id"]), _to_date(d.get("match_date")))
    _bulk_add_own_roster(user, own.id, int(d["season_id"]))
    if not roster:
        st.warning("Añade la plantilla de No Name una vez; después se reutiliza toda la temporada.")
        return
    labels = {r.player_id: f"{r.player.display_name or r.player.full_name}{f' · #{r.shirt_number}' if r.shirt_number is not None else ''}" for r in roster}
    ids = list(labels)
    if not d.get("own_xi"):
        d["own_xi"] = _suggest_own_xi(roster, d.get("own_formation", "4-3-3"), previous_parts)
        d["own_xi_source"] = "Último XI" if previous_parts else "Posición principal"
    slots = slots_for(d.get("own_formation"))
    if not slots:
        st.warning("La formación personalizada requiere usar Base de datos/Partidos en esta versión.")
        return
    st.caption(f"XI propuesto automáticamente · {d.get('own_xi_source','Plantilla')}. Solo corrige los nombres que cambien.")
    with st.form("own_xi_32", border=True):
        selected_rows = []
        current = d.get("own_xi", [])
        for idx, slot in enumerate(slots):
            a, b = st.columns([1.4, 3])
            a.markdown(f"**{slot.label}**")
            a.caption(slot.code)
            current_pid = current[idx].get("player_id") if idx < len(current) else None
            opts = [None] + ids
            pid = b.selectbox(f"Jugador {slot.label}", opts, index=opts.index(current_pid) if current_pid in opts else 0, format_func=lambda x: "Seleccionar..." if x is None else labels[x], key=f"own_slot_32_{idx}", label_visibility="collapsed")
            selected_rows.append({"player_id": pid, "position": slot.code, "role": slot.label})
        save = st.form_submit_button("Guardar XI en el borrador", type="primary", use_container_width=True)
    if save:
        chosen = [x["player_id"] for x in selected_rows if x["player_id"] is not None]
        if len(chosen) != 11 or len(set(chosen)) != 11:
            st.error("Selecciona 11 jugadores distintos.")
        else:
            d["own_xi"] = selected_rows
            st.success("XI preparado localmente. No se ha escrito en Supabase.")

    if len([x for x in d.get("own_xi", []) if x.get("player_id")]) == 11:
        xi_ids = [x["player_id"] for x in d["own_xi"]]
        bench_ids = [pid for pid in ids if pid not in xi_ids]
        st.markdown("#### Cambios")
        st.caption("Escribe el cambio como lo piensas: minuto · sale · entra. Los minutos se calculan solos.")
        existing = d.get("own_subs", [])
        with st.form("own_subs_32", border=True):
            subs = []
            for i in range(6):
                row = existing[i] if i < len(existing) else {}
                c1, c2, c3 = st.columns([1, 2, 2])
                minute = c1.number_input(f"Min {i+1}", 0, 130, int(row.get("minute", 0)), key=f"own_sub_min_{i}")
                out_opts = [None] + xi_ids
                in_opts = [None] + bench_ids
                out_id = c2.selectbox(f"Sale {i+1}", out_opts, index=out_opts.index(row.get("out_id")) if row.get("out_id") in out_opts else 0, format_func=lambda x: "—" if x is None else labels[x], key=f"own_sub_out_{i}")
                in_id = c3.selectbox(f"Entra {i+1}", in_opts, index=in_opts.index(row.get("in_id")) if row.get("in_id") in in_opts else 0, format_func=lambda x: "—" if x is None else labels[x], key=f"own_sub_in_{i}")
                if minute and out_id and in_id:
                    subs.append({"minute": int(minute), "out_id": int(out_id), "in_id": int(in_id)})
            save_subs = st.form_submit_button("Guardar cambios en el borrador", use_container_width=True)
        if save_subs:
            if len({x["out_id"] for x in subs}) != len(subs) or len({x["in_id"] for x in subs}) != len(subs):
                st.error("No repitas un jugador en dos cambios.")
            else:
                d["own_subs"] = subs
                st.success("Cambios preparados localmente.")


def _parse_quick_rival(text: str, formation: str) -> list[dict]:
    slots = slots_for(formation)
    rows = []
    for idx, raw in enumerate([x.strip() for x in text.splitlines() if x.strip()]):
        shirt = None
        name = raw
        pos = slots[idx].code if idx < len(slots) else "Otro"
        parts = [x.strip() for x in raw.split(";")]
        if len(parts) >= 2:
            if parts[0].isdigit():
                shirt = int(parts[0]); name = parts[1]
                if len(parts) > 2 and parts[2].upper() in POSITIONS:
                    pos = parts[2].upper()
            else:
                name = parts[0]
                if parts[1].upper() in POSITIONS:
                    pos = parts[1].upper()
                if len(parts) > 2 and parts[2].isdigit():
                    shirt = int(parts[2])
        else:
            match = re.match(r"^\s*(\d{1,2})[\.\-\s]+(.+)$", raw)
            if match:
                shirt = int(match.group(1)); name = match.group(2).strip()
        rows.append({"name": name, "shirt_number": shirt, "position": pos, "role": slots[idx].label if idx < len(slots) else "Jugador"})
    return rows


def _rival_lineup(own, d: dict) -> None:
    if not d.get("rival_id") and not d.get("new_rival"):
        return
    st.markdown("### 3 · Rival")
    formation = d.get("rival_formation", "4-3-3")
    slots = slots_for(formation)
    if not slots:
        st.warning("Usa una formación estándar para la carga rápida rival.")
        return
    previous_parts = []
    if d.get("rival_id"):
        previous_parts = _rival_previous_support(own.id, int(d["rival_id"]), _to_date(d.get("match_date")))
        if previous_parts and not d.get("rival_xi"):
            starters = [p for p in previous_parts if p.starter]
            by_pos = {}
            for p in starters:
                by_pos.setdefault(p.position or p.player.primary_position or "Otro", []).append(p)
            used = set(); generated = []
            for slot in slots:
                candidate = next((p for p in by_pos.get(slot.code, []) if p.player_id not in used), None)
                if candidate:
                    used.add(candidate.player_id)
                    generated.append({"name": candidate.player.full_name, "shirt_number": candidate.shirt_number, "position": slot.code, "role": slot.label})
                else:
                    generated.append({"name": "", "shirt_number": None, "position": slot.code, "role": slot.label})
            d["rival_xi"] = generated
            d["rival_xi_source"] = "Última alineación conocida"
    if previous_parts:
        st.caption(f"Rival precargado · {d.get('rival_xi_source','Última alineación conocida')}. Corrige solo las diferencias.")

    with st.expander("Pegado rápido", expanded=False):
        st.caption("Pega `1 Bote`, una lista de nombres o `1;Bote;POR`. Se asignan por orden a la formación.")
        with st.form("rival_paste_32"):
            pasted = st.text_area("Alineación pegada", height=140)
            apply = st.form_submit_button("Aplicar al XI", use_container_width=True)
        if apply:
            parsed = _parse_quick_rival(pasted, formation)
            if parsed:
                base = [{"name":"", "shirt_number":None, "position":s.code, "role":s.label} for s in slots]
                for i, row in enumerate(parsed[:11]):
                    base[i].update(row)
                d["rival_xi"] = base
                st.session_state.pop("postmatch_identity_conflicts_34", None)
                st.session_state.pop("postmatch_identity_resolutions_34", None)
                st.rerun()

    current = d.get("rival_xi") or [{"name":"", "shirt_number":None, "position":s.code, "role":s.label} for s in slots]
    with st.form("rival_xi_32", border=True):
        rows = []
        for idx, slot in enumerate(slots):
            row = current[idx] if idx < len(current) else {}
            a, b, c = st.columns([1.4, 3, 1])
            a.markdown(f"**{slot.label}**"); a.caption(slot.code)
            name = b.text_input(f"Nombre {idx+1}", value=row.get("name", ""), label_visibility="collapsed", placeholder="Nombre")
            shirt = c.number_input(f"Dorsal {idx+1}", 0, 99, value=row.get("shirt_number"), step=1, label_visibility="collapsed")
            rows.append({"name": name.strip(), "shirt_number": int(shirt) if shirt is not None else None, "position": slot.code, "role": slot.label})
        save = st.form_submit_button("Guardar XI rival en el borrador", type="primary", use_container_width=True)
    if save:
        if len([r for r in rows if r["name"]]) != 11:
            st.error("Completa los 11 titulares del rival.")
        else:
            d["rival_xi"] = rows
            st.session_state.pop("postmatch_identity_conflicts_34", None)
            st.session_state.pop("postmatch_identity_resolutions_34", None)
            st.success("XI rival preparado localmente.")

    if len([r for r in d.get("rival_xi", []) if r.get("name")]) == 11:
        names = [r["name"] for r in d["rival_xi"]]
        existing = d.get("rival_subs", [])
        st.markdown("#### Cambios rivales")
        with st.form("rival_subs_32", border=True):
            subs = []
            for i in range(6):
                row = existing[i] if i < len(existing) else {}
                c1, c2, c3, c4 = st.columns([1,2,2,1])
                minute = c1.number_input(f"Min R{i+1}", 0, 130, int(row.get("minute", 0)), key=f"rsub_min_{i}")
                opts = [None] + names
                out_name = c2.selectbox(f"Sale R{i+1}", opts, index=opts.index(row.get("out_name")) if row.get("out_name") in opts else 0, key=f"rsub_out_{i}", format_func=lambda x: "—" if x is None else x)
                in_name = c3.text_input(f"Entra R{i+1}", value=row.get("in_name", ""), key=f"rsub_in_{i}", placeholder="Nombre")
                shirt = c4.number_input(f"# R{i+1}", 0, 99, value=row.get("shirt_number"), step=1, key=f"rsub_shirt_{i}")
                if minute and out_name and in_name.strip():
                    subs.append({"minute":int(minute),"out_name":out_name,"in_name":in_name.strip(),"shirt_number":int(shirt) if shirt is not None else None})
            save_subs = st.form_submit_button("Guardar cambios rivales en el borrador", use_container_width=True)
        if save_subs:
            d["rival_subs"] = subs
            st.session_state.pop("postmatch_identity_conflicts_34", None)
            st.session_state.pop("postmatch_identity_resolutions_34", None)
            st.success("Cambios rivales preparados localmente.")


def _own_rows_for_publish(roster, d: dict) -> list[dict]:
    by_id = {r.player_id: r for r in roster}
    xi = [dict(x) for x in d.get("own_xi", [])]
    if len([x for x in xi if x.get("player_id")]) != 11:
        raise ValueError("Completa el XI de No Name.")
    rows = {}
    for x in xi:
        pid = int(x["player_id"])
        item = by_id[pid]
        rows[pid] = {"selected":True,"player_id":pid,"shirt_number":item.shirt_number,"starter":True,"position":x["position"],"minute_in":0,"minute_out":90,"captain":False}
    for sub in sorted(d.get("own_subs", []), key=lambda x: x["minute"]):
        out_id, in_id, minute = int(sub["out_id"]), int(sub["in_id"]), int(sub["minute"])
        if out_id not in rows:
            continue
        rows[out_id]["minute_out"] = minute
        position = rows[out_id]["position"]
        item = by_id[in_id]
        rows[in_id] = {"selected":True,"player_id":in_id,"shirt_number":item.shirt_number,"starter":False,"position":position,"minute_in":minute,"minute_out":90,"captain":False}
    return list(rows.values())


def _rival_rows_for_publish(d: dict) -> list[dict]:
    xi = [dict(x) for x in d.get("rival_xi", []) if x.get("name")]
    if len(xi) != 11:
        raise ValueError("Completa el XI rival.")
    rows = [{"name":x["name"],"shirt_number":x.get("shirt_number"),"position":x["position"],"starter":True,"minute_in":0,"minute_out":90,"captain":False} for x in xi]
    by_name = {x["name"]: x for x in rows}
    for sub in sorted(d.get("rival_subs", []), key=lambda x: x["minute"]):
        outgoing = by_name.get(sub["out_name"])
        if not outgoing:
            continue
        minute = int(sub["minute"]); outgoing["minute_out"] = minute
        incoming = {"name":sub["in_name"],"shirt_number":sub.get("shirt_number"),"position":outgoing["position"],"starter":False,"minute_in":minute,"minute_out":90,"captain":False}
        rows.append(incoming); by_name[incoming["name"]] = incoming
    return rows


def _save_cloud_draft(user: dict, d: dict) -> None:
    title = f"{d.get('round_name') or 'Postpartido'} · {d.get('new_rival') or d.get('rival_id') or 'Rival'}"
    with session_scope() as session:
        item = repo.save_postmatch_draft(session, actor_id=user["id"], payload=d, draft_id=st.session_state.get(CLOUD_DRAFT_KEY), season_id=d.get("season_id"), title=title)
    st.session_state[CLOUD_DRAFT_KEY] = item.id
    st.session_state.pop(CLOUD_DRAFT_LIST_KEY, None)
    st.success("Borrador guardado en la nube en una sola escritura.")


def _validate_draft_for_publish(d: dict) -> tuple[list[str], list[str]]:
    return validate_postmatch_draft(d)


def _identity_resolution_panel() -> dict[str, int]:
    conflicts = st.session_state.get("postmatch_identity_conflicts_34") or []
    if not conflicts:
        return st.session_state.get("postmatch_identity_resolutions_34", {}) or {}
    st.warning("He encontrado nombres que podrían corresponder a más de un jugador. Confírmalos antes de publicar; nunca los fusionaremos por intuición.")
    resolutions: dict[str, int] = dict(st.session_state.get("postmatch_identity_resolutions_34", {}) or {})
    with st.container(border=True):
        st.markdown("#### Identidades dudosas")
        for conflict in conflicts:
            normalized = conflict["normalized"]
            options = [-1] + [int(c["id"]) for c in conflict["candidates"]]
            labels = {-1: f"Crear nuevo registro para {conflict['name']} en este rival"}
            for candidate in conflict["candidates"]:
                details = []
                if candidate.get("date_of_birth"):
                    details.append(f"nac. {candidate['date_of_birth']}")
                if candidate.get("primary_position"):
                    details.append(candidate["primary_position"])
                if candidate.get("contexts"):
                    details.append(" / ".join(candidate["contexts"][:2]))
                labels[int(candidate["id"])] = f"{candidate.get('display_name') or candidate['full_name']}" + (" · " + " · ".join(details) if details else "")
            current = resolutions.get(normalized, -1)
            selected = st.selectbox(
                conflict["name"], options, index=options.index(current) if current in options else 0,
                format_func=lambda value, labels=labels: labels[value], key=f"identity34_{normalized}",
            )
            resolutions[normalized] = int(selected)
    st.session_state["postmatch_identity_resolutions_34"] = resolutions
    return resolutions

def _publish(user: dict, own, d: dict) -> None:
    st.markdown("### 4 · Guardar y publicar")
    own_ok = len([x for x in d.get("own_xi", []) if x.get("player_id")]) == 11
    rival_ok = len([x for x in d.get("rival_xi", []) if x.get("name")]) == 11
    errors, warnings = _validate_draft_for_publish(d)
    a,b,c,dcol = st.columns(4)
    a.metric("XI No Name", "11/11" if own_ok else "Pendiente")
    b.metric("XI rival", "11/11" if rival_ok else "Pendiente")
    c.metric("Cambios propios", len(d.get("own_subs", [])))
    dcol.metric("Cambios rivales", len(d.get("rival_subs", [])))
    if errors:
        st.error(" · ".join(errors))
    if warnings:
        st.warning(" · ".join(warnings))
    identity_resolutions = _identity_resolution_panel()
    left, right = st.columns(2)
    if left.button("Guardar borrador en nube", use_container_width=True):
        _save_cloud_draft(user, d)
    if right.button("PUBLICAR POSTPARTIDO", type="primary", use_container_width=True, disabled=bool(errors)):
        try:
            rival_rows = _rival_rows_for_publish(d)
            with session_scope() as session:
                conflicts = repo.lineup_identity_conflicts(
                    session, rival_rows, team_id=int(d["rival_id"]) if d.get("rival_id") else None,
                    season_id=int(d["season_id"]) if d.get("season_id") else None,
                )
            unresolved = [c for c in conflicts if c["normalized"] not in identity_resolutions]
            if conflicts and (unresolved or not st.session_state.get("postmatch_identity_conflicts_34")):
                st.session_state["postmatch_identity_conflicts_34"] = conflicts
                st.rerun()
            with st.spinner("Guardando partido, alineaciones y asignaciones en una sola transacción..."):
                with measure("Publicar postpartido", "postmatch"):
                    with session_scope() as session:
                        season_id = int(d["season_id"])
                        competition = session.get(Competition, d.get("competition_id")) if d.get("competition_id") else None
                        if not competition:
                            competition = repo.create_competition(session, d["new_competition"], actor_id=user["id"])
                        rival = session.get(Team, d.get("rival_id")) if d.get("rival_id") else None
                        if not rival:
                            rival = repo.create_team(session, d["new_rival"], actor_id=user["id"])
                        if d["own_location"] == "Local":
                            home_id, away_id = own.id, rival.id
                            home_score, away_score = d["own_score"], d["rival_score"]
                            home_formation, away_formation = d["own_formation"], d["rival_formation"]
                        else:
                            home_id, away_id = rival.id, own.id
                            home_score, away_score = d["rival_score"], d["own_score"]
                            home_formation, away_formation = d["rival_formation"], d["own_formation"]
                        due_at = datetime.combine(_to_date(d["due_date"]), _to_time(d["due_time"])) if d.get("due_enabled") else None
                        match = repo.create_match(session, season_id=season_id, competition_id=competition.id, round_name=d["round_name"], match_date=_to_date(d["match_date"]), home_team_id=home_id, away_team_id=away_id, created_by=user["id"], home_score=int(home_score), away_score=int(away_score), venue=d.get("venue") or None, home_formation=home_formation, away_formation=away_formation, status="published", report_due_at=due_at)
                        roster = repo.get_roster(session, own.id, season_id)
                        repo.replace_participations(session, match.id, own.id, _own_rows_for_publish(roster, d), user["id"])
                        repo.save_named_lineup_fast(session, match_id=match.id, team_id=rival.id, season_id=season_id, rows=rival_rows, actor_id=user["id"], sync_roster=True, identity_resolutions=identity_resolutions)
                        if d.get("reporter_ids"):
                            repo.assign_reporters(session, match.id, d["reporter_ids"], user["id"], due_at=due_at, required=True)
                        repo.close_postmatch_draft(session, st.session_state.get(CLOUD_DRAFT_KEY), user["id"])
                        repo.audit(session, user["id"], "publish_postmatch_3_3", "match", match.id, detail=f"reporters={len(d.get('reporter_ids', []))}")
            _clear_draft()
            _invalidate_context()
            st.session_state["postmatch_33_published"] = True
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _cloud_drafts(user: dict) -> None:
    drafts = st.session_state.get(CLOUD_DRAFT_LIST_KEY)
    if drafts is None:
        with session_scope() as session:
            objects = repo.list_postmatch_drafts(session, user["id"], limit=10)
        drafts = [_ns(id=x.id, title=x.title, updated_at=x.updated_at) for x in objects]
        st.session_state[CLOUD_DRAFT_LIST_KEY] = drafts
    if not drafts:
        return
    with st.expander("Continuar borrador guardado", expanded=False):
        selected = st.selectbox("Borrador", [x.id for x in drafts], format_func=lambda did: next((x.title or f"Borrador {x.id}") for x in drafts if x.id == did))
        if st.button("Cargar borrador", use_container_width=True):
            with session_scope() as session:
                payload = repo.load_postmatch_draft(session, selected, user["id"])
            st.session_state[DRAFT_KEY] = payload
            st.session_state[CLOUD_DRAFT_KEY] = selected
            st.rerun()


def render(user: dict) -> None:
    if user["role"] != "admin":
        st.error("Solo administración puede preparar postpartidos.")
        return
    page_header("Nuevo postpartido", "Prepara casi todo en memoria y sincroniza solo al guardar o publicar.")
    if st.session_state.pop("postmatch_33_published", False):
        st.success("Postpartido publicado. Ya está disponible para los informadores.")
    own, active, seasons, competitions, teams, users = _load_context()
    if not own:
        _setup_own_team(user); return
    if not active or not seasons:
        _setup_season(user); return
    if DRAFT_KEY not in st.session_state:
        st.session_state[DRAFT_KEY] = _new_draft(active.id)
    _cloud_drafts(user)
    if st.button("Empezar un postpartido limpio", use_container_width=True):
        _clear_draft(); st.session_state[DRAFT_KEY] = _new_draft(active.id); st.rerun()
    d = _draft()
    _header(user, own, active, seasons, competitions, teams, users)
    if d.get("competition_id") is not None or d.get("new_competition"):
        _own_lineup(user, own, d)
        _rival_lineup(own, d)
        _publish(user, own, d)
