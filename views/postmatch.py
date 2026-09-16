from __future__ import annotations

import re
from types import SimpleNamespace
from datetime import date, datetime, time, timedelta

import streamlit as st

from core.clock import local_today
from core.constants import FORMATIONS, POSITIONS, ROLES
from models.entities import Competition, Team
from core.database import session_scope
from core.formations import slots_for
from core.workflow_defaults import recent_match_defaults
from core.performance import measure
from core.permissions import can_admin
from core.postmatch_validation import validate_postmatch_draft
from core.schedule import require_schedule_confirmed
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
    today = today or local_today()
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
        "match_date": local_today().isoformat(),
        "kickoff_time": "",
        "own_location": "Local",
        "own_score": 0,
        "rival_score": 0,
        "own_formation": None,
        "rival_formation": None,
        "venue": "",
        "due_enabled": False,
        "due_date": (local_today() + timedelta(days=1)).isoformat(),
        "due_time": "20:00",
        "reporter_ids": [],
        "existing_match_id": None,
        "own_xi": [],
        "own_subs": [],
        "rival_xi": [],
        "rival_subs": [],
        "ui_step": "match",
    }




def _new_draft_with_recent_defaults(own_id: int, season_id: int) -> dict:
    draft = _new_draft(season_id)
    with session_scope() as session:
        draft.update(recent_match_defaults(session, own_id, season_id))
    return draft

def _draft_from_existing_match(match_id: int, own_id: int) -> dict:
    with session_scope() as session:
        match = repo.get_match(session, int(match_id))
        if not match or own_id not in {match.home_team_id, match.away_team_id}:
            raise ValueError("El partido programado no corresponde a No Name.")
        rival_id = match.away_team_id if match.home_team_id == own_id else match.home_team_id
        require_schedule_confirmed(match, action="preparar el postpartido")
        draft = _new_draft(match.season_id)
        draft.update({
            "existing_match_id": match.id,
            "competition_id": match.competition_id,
            "rival_id": rival_id,
            "round_name": match.round_name,
            "match_date": match.match_date.isoformat(),
            "kickoff_time": match.kickoff_at.strftime("%H:%M"),
            "own_location": "Local" if match.home_team_id == own_id else "Visitante",
            "venue": match.venue or "",
            "own_formation": match.home_formation if match.home_team_id == own_id else match.away_formation,
            "rival_formation": match.away_formation if match.home_team_id == own_id else match.home_formation,
        })
        # Reuse recurring staff and previous XI suggestions without replacing fixture identity.
        recent = recent_match_defaults(session, own_id, match.season_id)
        draft["reporter_ids"] = recent.get("reporter_ids", [])
        # Reuse verified participants of THIS match, never a guessed XI from
        # previous fixtures, roster order or a default formation.
        own_parts = repo.get_participations(session, match.id, own_id)
        rival_parts = repo.get_participations(session, match.id, rival_id)
        own_starters = [part for part in own_parts if part.starter]
        rival_starters = [part for part in rival_parts if part.starter]
        own_slots = slots_for(draft["own_formation"])
        rival_slots = slots_for(draft["rival_formation"])
        if len(own_starters) == 11:
            draft["own_xi"] = _prefill_own_starters(own_starters, own_slots)
            draft["own_xi_source"] = "Titulares ya registrados en este mismo partido"
            draft["own_xi_formation"] = draft["own_formation"]
        if len(rival_starters) == 11:
            draft["rival_xi"] = _prefill_rival_starters(rival_starters, rival_slots)
            draft["rival_xi_source"] = "Titulares ya registrados en este mismo partido"
            draft["rival_xi_formation"] = draft["rival_formation"]
        return draft



def _lineup_slots(formation: str | None):
    """Known formation slots or anonymous XI: never fabricate tactical positions."""
    return slots_for(formation) or [
        _ns(code="Otro", label=f"Titular {index}") for index in range(1, 12)
    ]


def _order_verified_starters(parts, slots):
    """Use match order, not a made-up positional mapping."""
    ordered = sorted(parts, key=lambda x: (x.order_index, x.id))
    if not slots:
        return ordered
    # Only use position-derived ordering when every slot has an unambiguous
    # documented position; otherwise preserve the recorded order.
    by_code = {}
    for part in ordered:
        by_code.setdefault(part.position, []).append(part)
    if all(len(by_code.get(slot.code, [])) == sum(1 for sl in slots if sl.code == slot.code) for slot in slots):
        return [by_code[slot.code].pop(0) for slot in slots]
    return ordered


def _prefill_own_starters(starters, slots):
    ordered = _order_verified_starters(starters, slots)
    return [{'player_id': part.player_id, 'position':part.position or 'Otro',
             'role': slots[index].label if index < len(slots) else f'Titular {index+1}'}
            for index, part in enumerate(ordered)]


def _prefill_rival_starters(starters, slots):
    ordered = _order_verified_starters(starters, slots)
    return [{'name': part.player.full_name, 'shirt_number': part.shirt_number,
             'position':part.position or 'Otro',
             'role':slots[index].label if index < len(slots) else f'Titular {index+1}'}
            for index, part in enumerate(ordered)]

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
    fallback = fallback or local_today()
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
    st.warning("No hay un equipo propio válido. Selecciona el registro REAL existente desde Administración → Club → Equipo propio. No se crea un duplicado automáticamente.")
    if st.button("Abrir Administración", key="own_setup_admin_423"):
        from core.navigation import request_navigation
        st.session_state["admin_section_423"] = "Club"
        request_navigation("Administración")
        st.rerun()


def _setup_season(user: dict) -> None:
    st.warning("Crea la temporada activa para empezar.")
    with st.form("season_setup_32"):
        name = st.text_input("Temporada", value=_default_season_name())
        c1, c2 = st.columns(2)
        start = c1.date_input("Inicio", value=date(local_today().year, 7, 1))
        end = c2.date_input("Fin", value=date(local_today().year + 1, 6, 30))
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
        team_objs = [t for t in repo.list_teams(session, active_only=True) if not t.is_own_team and not t.is_test and t.archived_at is None]
        user_objs = [u for u in repo.list_users(session, active_only=True) if repo.user_has_role(session, u.id, "reporter")]
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
    user_ids = [u.id for u in users]

    # Normal 3.9 flow: the calendar already owns fixture identity. The user only
    # completes what happened; season/competition/rival/date/kickoff are read-only.
    if d.get("existing_match_id"):
        rival = next((t for t in teams if t.id == d.get("rival_id")), None)
        comp = next((c for c in competitions if c.id == d.get("competition_id")), None)
        season = next((x for x in seasons if x.id == d.get("season_id")), None)
        own_first = d.get("own_location") == "Local"
        home_name = own.name if own_first else (rival.name if rival else "Rival")
        away_name = (rival.name if rival else "Rival") if own_first else own.name
        st.markdown(f"**{d.get('round_name') or 'Partido'} · {comp.name if comp else 'Competición'}**")
        st.caption(
            f"{_to_date(d.get('match_date')).strftime('%d/%m/%Y')} · {d.get('kickoff_time')} · "
            f"{season.name if season else 'Temporada'}"
        )
        st.markdown(f"### {home_name} — {away_name}")
        with st.form("postmatch_38_context_header", border=True):
            a, b = st.columns(2)
            own_score = a.number_input(f"Goles {own.name}", 0, 30, int(d.get("own_score", 0)))
            rival_score = b.number_input(f"Goles {rival.name if rival else 'rival'}", 0, 30, int(d.get("rival_score", 0)))
            a, b = st.columns(2)
            formation_options = [None, *FORMATIONS]
            formation_label = lambda name: name or "Desconocida (no inventar)"
            own_formation = a.selectbox("Sistema No Name", formation_options, index=formation_options.index(d.get("own_formation")) if d.get("own_formation") in formation_options else 0, format_func=formation_label)
            rival_formation = b.selectbox("Sistema rival", formation_options, index=formation_options.index(d.get("rival_formation")) if d.get("rival_formation") in formation_options else 0, format_func=formation_label)
            reporter_ids = st.multiselect(
                "Informadores", user_ids,
                default=[uid for uid in d.get("reporter_ids", []) if uid in user_ids],
                format_func=lambda uid: next(f"{u.full_name} · {ROLES.get(u.role, u.role)}" for u in users if u.id == uid),
            )
            with st.expander("Datos opcionales"):
                venue = st.text_input("Campo / ubicación", value=d.get("venue", ""))
                due_enabled = st.checkbox("Fecha límite para informes", value=bool(d.get("due_enabled", False)))
                pcol, qcol = st.columns(2)
                base_date = _to_date(d.get("match_date"))
                due_date = pcol.date_input("Día límite", value=_to_date(d.get("due_date"), base_date + timedelta(days=1)), disabled=not due_enabled)
                due_time = qcol.time_input("Hora límite", value=_to_time(d.get("due_time")), disabled=not due_enabled)
            prepare = st.form_submit_button("CONTINUAR", type="primary", use_container_width=True)
        if prepare:
            d.update({
                "own_score": int(own_score), "rival_score": int(rival_score),
                "own_formation": own_formation, "rival_formation": rival_formation,
                "reporter_ids": reporter_ids, "venue": venue.strip(),
                "due_enabled": due_enabled, "due_date": due_date.isoformat(),
                "due_time": due_time.isoformat(timespec="minutes"), "ui_step": "own",
            })
            if d.get("own_xi_formation") != own_formation:
                d["own_xi"] = []; d["own_subs"] = []; d["own_xi_formation"] = own_formation
            if d.get("rival_xi_formation") != rival_formation:
                d["rival_xi"] = []; d["rival_subs"] = []; d["rival_xi_formation"] = rival_formation
            st.rerun()
        return

    # Exceptional admin flow for a fixture that genuinely does not exist in the
    # imported calendar. It remains available, but it is no longer navigation.
    st.info("Alta excepcional de partido. El flujo habitual empieza en Jornada.")
    season_ids = [s.id for s in seasons]
    comp_ids = [None] + [c.id for c in competitions]
    team_ids = [None] + [t.id for t in teams]
    with st.form("postmatch_38_exception_header", border=True):
        a, b, c = st.columns(3)
        season_id = a.selectbox("Temporada", season_ids, index=season_ids.index(d["season_id"]) if d.get("season_id") in season_ids else 0, format_func=lambda sid: next(x.name for x in seasons if x.id == sid))
        competition_id = b.selectbox("Competición", comp_ids, index=comp_ids.index(d.get("competition_id")) if d.get("competition_id") in comp_ids else 0, format_func=lambda cid: "＋ Nueva" if cid is None else next(x.name for x in competitions if x.id == cid))
        rival_id = c.selectbox("Rival", team_ids, index=team_ids.index(d.get("rival_id")) if d.get("rival_id") in team_ids else 0, format_func=lambda tid: "＋ Nuevo rival" if tid is None else next(x.name for x in teams if x.id == tid))
        x, y = st.columns(2)
        new_competition = x.text_input("Nueva competición", value=d.get("new_competition", ""), disabled=competition_id is not None)
        new_rival = y.text_input("Nuevo rival", value=d.get("new_rival", ""), disabled=rival_id is not None)
        a, b, c, e = st.columns([1.2, 1, .8, 1])
        round_name = a.text_input("Jornada / partido", value=d.get("round_name", ""))
        match_date = b.date_input("Fecha definitiva", value=_to_date(d.get("match_date")))
        kickoff_text = c.text_input("Hora", value=str(d.get("kickoff_time") or ""), placeholder="HH:MM", help="No se propone ninguna hora: debe ser la hora real confirmada.")
        own_location = e.radio("No Name", ["Local", "Visitante"], horizontal=True, index=0 if d.get("own_location") == "Local" else 1)
        a, b = st.columns(2)
        own_score = a.number_input(f"Goles {own.name}", 0, 30, int(d.get("own_score", 0)))
        rival_score = b.number_input("Goles rival", 0, 30, int(d.get("rival_score", 0)))
        a, b = st.columns(2)
        formation_options = [None, *FORMATIONS]
        formation_label = lambda name: name or "Desconocida (no inventar)"
        own_formation = a.selectbox("Sistema No Name", formation_options, index=formation_options.index(d.get("own_formation")) if d.get("own_formation") in formation_options else 0, format_func=formation_label)
        rival_formation = b.selectbox("Sistema rival", formation_options, index=formation_options.index(d.get("rival_formation")) if d.get("rival_formation") in formation_options else 0, format_func=formation_label)
        reporter_ids = st.multiselect("Informadores", user_ids, default=[uid for uid in d.get("reporter_ids", []) if uid in user_ids], format_func=lambda uid: next(f"{u.full_name} · {ROLES.get(u.role, u.role)}" for u in users if u.id == uid))
        prepare = st.form_submit_button("CONTINUAR", type="primary", use_container_width=True)
    if prepare:
        if competition_id is None and not new_competition.strip():
            st.error("Selecciona o escribe una competición."); return
        if rival_id is None and not new_rival.strip():
            st.error("Selecciona o escribe el rival."); return
        try:
            parsed_kickoff = time.fromisoformat(kickoff_text.strip())
        except Exception:
            st.error("Indica la hora real confirmada en formato HH:MM."); return
        d.update({
            "season_id": season_id, "competition_id": competition_id, "new_competition": new_competition.strip(),
            "rival_id": rival_id, "new_rival": new_rival.strip(), "round_name": round_name.strip(),
            "match_date": match_date.isoformat(), "kickoff_time": parsed_kickoff.isoformat(timespec="minutes"),
            "own_location": own_location, "own_score": int(own_score), "rival_score": int(rival_score),
            "own_formation": own_formation, "rival_formation": rival_formation, "reporter_ids": reporter_ids,
            "due_enabled": False, "ui_step": "own",
        })
        if d.get("own_xi_formation") != own_formation:
            d["own_xi"] = []; d["own_subs"] = []; d["own_xi_formation"] = own_formation
        if d.get("rival_xi_formation") != rival_formation:
            d["rival_xi"] = []; d["rival_subs"] = []; d["rival_xi_formation"] = rival_formation
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
    slots = _lineup_slots(d.get("own_formation"))
    if d.get('own_xi_source'):
        st.info(f"XI recuperado: {d['own_xi_source']}. Revisa y guarda para confirmar.")
    else:
        st.info("Completa los once titulares del partido. No se copian automáticamente los del último encuentro. Si desconoces la formación, el XI se registra sin posición táctica inventada.")
    with st.form("own_xi_32", border=True):
        selected_rows = []
        current = d.get("own_xi", [])
        for idx, slot in enumerate(slots):
            a, b = st.columns([1.4, 3])
            a.markdown(f"**{slot.label}**")
            a.caption(slot.code)
            current_pid = current[idx].get("player_id") if idx < len(current) else None
            opts = [None] + ids
            pid = b.selectbox(f"Jugador {slot.label}", opts, index=opts.index(current_pid) if current_pid in opts else 0, format_func=lambda x: "Seleccionar..." if x is None else labels[x], key=f"own_slot_423_{d.get('existing_match_id')}_{d.get('own_formation')}_{idx}", label_visibility="collapsed")
            retained = current[idx].get('position') if idx < len(current) and current[idx].get('player_id') == pid else None
            selected_rows.append({"player_id": pid, "position": retained or slot.code if slot.code == 'Otro' else slot.code, "role": slot.label})
        save = st.form_submit_button("Guardar XI en el borrador", type="primary", use_container_width=True)
    if save:
        chosen = [x["player_id"] for x in selected_rows if x["player_id"] is not None]
        if len(chosen) != 11 or len(set(chosen)) != 11:
            st.error("Selecciona 11 jugadores distintos.")
        else:
            d["own_xi"] = selected_rows
            st.success("XI preparado. Puedes continuar al siguiente paso cuando esté correcto.")

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
                c1, c2, c3, c4 = st.columns([1, 2, 2, 1.2])
                minute = c1.number_input(f"Min {i+1}", 0, 130, int(row.get("minute", 0)), key=f"own_sub_min_{i}")
                out_opts = [None] + xi_ids
                in_opts = [None] + bench_ids
                out_id = c2.selectbox(f"Sale {i+1}", out_opts, index=out_opts.index(row.get("out_id")) if row.get("out_id") in out_opts else 0, format_func=lambda x: "—" if x is None else labels[x], key=f"own_sub_out_{i}")
                in_id = c3.selectbox(f"Entra {i+1}", in_opts, index=in_opts.index(row.get("in_id")) if row.get("in_id") in in_opts else 0, format_func=lambda x: "—" if x is None else labels[x], key=f"own_sub_in_{i}")
                inherited = next((x.get("position") for x in d.get("own_xi", []) if x.get("player_id") == out_id), "Otro")
                pos_default = row.get("position") or inherited
                position = c4.selectbox(f"Pos {i+1}", POSITIONS, index=POSITIONS.index(pos_default) if pos_default in POSITIONS else len(POSITIONS)-1, key=f"own_sub_pos_{i}", help="Se hereda la posición del jugador que sale, pero puedes corregirla si cambia la estructura.")
                if minute and out_id and in_id:
                    subs.append({"minute": int(minute), "out_id": int(out_id), "in_id": int(in_id), "position": position})
            save_subs = st.form_submit_button("Guardar cambios en el borrador", use_container_width=True)
        if save_subs:
            if len({x["out_id"] for x in subs}) != len(subs) or len({x["in_id"] for x in subs}) != len(subs):
                st.error("No repitas un jugador en dos cambios.")
            else:
                d["own_subs"] = subs
                st.success("Cambios preparados localmente.")


def _parse_quick_rival(text: str, formation: str | None) -> list[dict]:
    slots = _lineup_slots(formation)
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
    formation = d.get("rival_formation")
    slots = _lineup_slots(formation)
    previous_parts = []
    if d.get("rival_id"):
        previous_parts = _rival_previous_support(own.id, int(d["rival_id"]), _to_date(d.get("match_date")))
    if d.get('rival_xi_source'):
        st.info(f"XI recuperado: {d['rival_xi_source']}. Revisa y guarda para confirmar.")
    else:
        st.info("Registra los once titulares reales del rival; el XI de una jornada anterior no se aplica por defecto.")

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
            name = b.text_input(f"Nombre {idx+1}", value=row.get("name", ""), label_visibility="collapsed", placeholder="Nombre", key=f"rival_xi_name_423_{d.get('existing_match_id')}_{formation}_{idx}")
            shirt = c.number_input(f"Dorsal {idx+1}", 0, 99, value=row.get("shirt_number"), step=1, label_visibility="collapsed", key=f"rival_xi_shirt_423_{d.get('existing_match_id')}_{formation}_{idx}")
            retained = row.get('position') if row.get('name') == name.strip() else None
            rows.append({"name": name.strip(), "shirt_number": int(shirt) if shirt is not None else None, "position": (retained or slot.code) if slot.code == 'Otro' else slot.code, "role": slot.label})
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
                c1, c2, c3, c4, c5 = st.columns([1,2,2,1,1.2])
                minute = c1.number_input(f"Min R{i+1}", 0, 130, int(row.get("minute", 0)), key=f"rsub_min_{i}")
                opts = [None] + names
                out_name = c2.selectbox(f"Sale R{i+1}", opts, index=opts.index(row.get("out_name")) if row.get("out_name") in opts else 0, key=f"rsub_out_{i}", format_func=lambda x: "—" if x is None else x)
                in_name = c3.text_input(f"Entra R{i+1}", value=row.get("in_name", ""), key=f"rsub_in_{i}", placeholder="Nombre")
                shirt = c4.number_input(f"# R{i+1}", 0, 99, value=row.get("shirt_number"), step=1, key=f"rsub_shirt_{i}")
                inherited = next((x.get("position") for x in d.get("rival_xi", []) if x.get("name") == out_name), "Otro")
                pos_default = row.get("position") or inherited
                position = c5.selectbox(f"Pos R{i+1}", POSITIONS, index=POSITIONS.index(pos_default) if pos_default in POSITIONS else len(POSITIONS)-1, key=f"rsub_pos_{i}")
                if minute and out_name and in_name.strip():
                    subs.append({"minute":int(minute),"out_name":out_name,"in_name":in_name.strip(),"shirt_number":int(shirt) if shirt is not None else None,"position":position})
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
        position = sub.get("position") or rows[out_id]["position"]
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
        incoming = {"name":sub["in_name"],"shirt_number":sub.get("shirt_number"),"position":sub.get("position") or outgoing["position"],"starter":False,"minute_in":minute,"minute_out":90,"captain":False}
        rows.append(incoming); by_name[incoming["name"]] = incoming
    return rows


def _save_cloud_draft(user: dict, d: dict) -> None:
    title = f"{d.get('round_name') or 'Postpartido'} · {d.get('new_rival') or d.get('rival_id') or 'Rival'}"
    with session_scope() as session:
        item = repo.save_postmatch_draft(session, actor_id=user["id"], payload=d, draft_id=st.session_state.get(CLOUD_DRAFT_KEY), season_id=d.get("season_id"), title=title)
    st.session_state[CLOUD_DRAFT_KEY] = item.id
    st.session_state.pop(CLOUD_DRAFT_LIST_KEY, None)
    st.success("Borrador guardado.")


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
    with st.expander("Guardar para continuar después", expanded=False):
        if st.button("Guardar borrador", use_container_width=True):
            _save_cloud_draft(user, d)
    if st.button("PUBLICAR POSTPARTIDO", type="primary", use_container_width=True, disabled=bool(errors)):
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
            with st.spinner("Guardando postpartido..."):
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
                        kickoff_at = datetime.combine(_to_date(d["match_date"]), time.fromisoformat(str(d["kickoff_time"])))
                        if d.get("existing_match_id"):
                            match = repo.update_match(
                                session, int(d["existing_match_id"]), user["id"],
                                season_id=season_id, competition_id=competition.id, round_name=d["round_name"], match_date=_to_date(d["match_date"]),
                                window_start=None, window_end=None, kickoff_at=kickoff_at, schedule_status="confirmed",
                                home_team_id=home_id, away_team_id=away_id, home_score=int(home_score), away_score=int(away_score), venue=d.get("venue") or None,
                                home_formation=home_formation, away_formation=away_formation, status="published", report_due_at=due_at,
                            )
                        else:
                            match = repo.create_match(session, season_id=season_id, competition_id=competition.id, round_name=d["round_name"], match_date=_to_date(d["match_date"]), home_team_id=home_id, away_team_id=away_id, created_by=user["id"], home_score=int(home_score), away_score=int(away_score), venue=d.get("venue") or None, home_formation=home_formation, away_formation=away_formation, status="published", report_due_at=due_at, kickoff_at=kickoff_at, schedule_status="confirmed")
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


def _go_to_publish_423() -> None:
    st.session_state[DRAFT_KEY]['ui_step'] = 'publish'


def render(user: dict) -> None:
    if not can_admin(user):
        st.error("Solo administración puede preparar postpartidos.")
        return
    page_header("Preparar partido", "Completa el partido existente del calendario y publica el postpartido.")
    if st.session_state.pop("postmatch_33_published", False):
        st.success("Postpartido publicado. Ya está disponible para los informadores.")
    own, active, seasons, competitions, teams, users = _load_context()
    if not own:
        _setup_own_team(user); return
    if not active or not seasons:
        _setup_season(user); return

    requested_draft_id = st.session_state.pop("postmatch_open_cloud_draft_id", None)
    if requested_draft_id:
        try:
            with session_scope() as session:
                payload = repo.load_postmatch_draft(session, int(requested_draft_id), user["id"])
            st.session_state[DRAFT_KEY] = payload
            st.session_state[CLOUD_DRAFT_KEY] = int(requested_draft_id)
            st.session_state.pop(CLOUD_DRAFT_LIST_KEY, None)
            st.success("Borrador recuperado.")
        except Exception as exc:
            st.warning(f"No se pudo recuperar el borrador: {exc}")

    existing_match_id = st.session_state.pop("postmatch_existing_match_id", None)
    if existing_match_id:
        try:
            _clear_draft()
            st.session_state[DRAFT_KEY] = _draft_from_existing_match(int(existing_match_id), own.id)
        except Exception as exc:
            st.warning(f"No se pudo preparar el partido programado: {exc}")

    if DRAFT_KEY not in st.session_state:
        st.info("El flujo normal empieza en Jornada → partido de No Name → Preparar partido.")
        with st.expander("Alta excepcional de un partido fuera del calendario", expanded=False):
            if st.button("Crear contexto excepcional", use_container_width=True):
                st.session_state[DRAFT_KEY] = _new_draft_with_recent_defaults(own.id, active.id)
                st.rerun()
        _cloud_drafts(user)
        return

    d = _draft()
    step = d.get("ui_step") or "match"
    step_names = {"match": "1 Partido", "own": "2 No Name", "rival": "3 Rival", "publish": "4 Publicar"}
    st.progress((list(step_names).index(step) + 1) / len(step_names), text=f"Preparación · {step_names[step]} de 4")
    st.caption("  →  ".join((f"**{label}**" if key == step else label) for key, label in step_names.items()))
    if d.get("existing_match_id"):
        st.info(f"Estás preparando el partido ya registrado (ID {d['existing_match_id']}). No se duplicará el encuentro. Publicar solo estará disponible después de completar ambos XI.")
    own_count = len({int(x['player_id']) for x in d.get('own_xi', []) if x.get('player_id')})
    rival_count = len({str(x['name']).strip().casefold() for x in d.get('rival_xi', []) if x.get('name')})
    st.caption(f"Requisitos: XI No Name {own_count}/11 · XI rival {rival_count}/11 · Informadores {len(d.get('reporter_ids', []))}.")
    if step != 'publish':
        ready, _ = _validate_draft_for_publish(d)
        st.button('4 · PUBLICAR POSTPARTIDO — completar requisitos primero' if ready else '4 · Revisar y PUBLICAR POSTPARTIDO →',
                  key='postmatch_publish_shortcut_423', type='primary', use_container_width=True,
                  disabled=bool(ready), on_click=_go_to_publish_423)
        if ready:
            st.warning('Pendiente para publicar: ' + ' · '.join(ready))
        else:
            st.success('Los requisitos mínimos están completos; abre la revisión y pulsa PUBLICAR POSTPARTIDO.')

    if step == "match":
        _header(user, own, active, seasons, competitions, teams, users)
        return

    if step == "own":
        if st.button("← Partido"):
            d["ui_step"] = "match"; st.rerun()
        _own_lineup(user, own, d)
        own_ok = len([x for x in d.get("own_xi", []) if x.get("player_id")]) == 11
        if st.button("CONTINUAR AL RIVAL", type="primary", use_container_width=True, disabled=not own_ok):
            d["ui_step"] = "rival"; st.rerun()
        return

    if step == "rival":
        if st.button("← No Name"):
            d["ui_step"] = "own"; st.rerun()
        _rival_lineup(own, d)
        rival_ok = len([x for x in d.get("rival_xi", []) if x.get("name")]) == 11
        if st.button("CONTINUAR A PUBLICAR", type="primary", use_container_width=True, disabled=not rival_ok):
            d["ui_step"] = "publish"; st.rerun()
        return

    if st.button("← Rival"):
        d["ui_step"] = "rival"; st.rerun()
    _publish(user, own, d)

