from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.entities import Player, TeamRoster


def quality_issues(session: Session, limit: int = 200) -> list[dict]:
    issues: list[dict] = []
    duplicate_names = session.execute(
        select(Player.normalized_name, func.count(Player.id)).where(Player.active.is_(True), Player.merged_into_id.is_(None)).group_by(Player.normalized_name).having(func.count(Player.id) > 1)
    ).all()
    for normalized, count in duplicate_names:
        players = list(session.scalars(select(Player).where(Player.normalized_name == normalized, Player.active.is_(True))).all())
        issues.append({"type":"Posible duplicado", "severity":"Alta", "entity":"Jugador", "detail":" / ".join(f"{p.id} · {p.full_name}" for p in players[:5]), "count":count})
    no_pos = list(session.scalars(select(Player).where(Player.active.is_(True), (Player.primary_position.is_(None) | (Player.primary_position == ""))).limit(80)).all())
    for p in no_pos:
        issues.append({"type":"Sin posición", "severity":"Media", "entity":"Jugador", "detail":f"{p.id} · {p.full_name}", "count":1})
    # Active players with no active roster link are useful to inspect because they may be a stale or incomplete rival identity.
    active_roster_ids = set(session.scalars(select(TeamRoster.player_id).where(TeamRoster.active.is_(True))).all())
    unlinked = list(session.scalars(select(Player).where(Player.active.is_(True), Player.merged_into_id.is_(None)).limit(1000)).all())
    for p in unlinked:
        if p.id not in active_roster_ids:
            issues.append({"type":"Sin equipo/plantilla", "severity":"Baja", "entity":"Jugador", "detail":f"{p.id} · {p.full_name}", "count":1})
            if len(issues) >= limit:
                break
    # Duplicate shirt numbers inside one active roster.
    roster_rows = list(session.scalars(select(TeamRoster).where(TeamRoster.active.is_(True), TeamRoster.shirt_number.is_not(None))).all())
    grouped = defaultdict(list)
    for r in roster_rows:
        grouped[(r.team_id, r.season_id, r.shirt_number)].append(r)
    for (team_id, season_id, shirt), rows in grouped.items():
        if len(rows) > 1:
            issues.append({"type":"Dorsal repetido", "severity":"Media", "entity":"Plantilla", "detail":f"Equipo {team_id} · temporada {season_id} · #{shirt} · jugadores {', '.join(str(r.player_id) for r in rows)}", "count":len(rows)})
    order = {"Alta":0,"Media":1,"Baja":2}
    issues.sort(key=lambda x:(order.get(x["severity"],9),x["type"],x["detail"]))
    return issues[:limit]
