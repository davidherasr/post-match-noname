from __future__ import annotations

import json
import re
from datetime import date as _date
from types import SimpleNamespace as _NS

from sqlalchemy.orm import Session
from repositories import scouting as repo

def _slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    return clean.strip("_") or "equipo"

def _namespace(value):
    if isinstance(value, dict):
        return _NS(**{k: _namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_namespace(v) for v in value]
    return value

def _snapshot_report_payload(session: Session, report_id: int, version: int) -> dict:
    item = repo.get_report_version(session, report_id, version)
    if not item:
        raise ValueError(f"No existe la versión V{version} del informe.")
    raw = json.loads(item.snapshot_json)
    match_raw = raw["match"]
    match_date = match_raw.get("match_date")
    if isinstance(match_date, str):
        try:
            match_raw["match_date"] = _date.fromisoformat(match_date[:10])
        except ValueError:
            pass
    home_team = _namespace(match_raw["home_team"])
    away_team = _namespace(match_raw["away_team"])
    match_raw.setdefault("home_team_id", home_team.id)
    match_raw.setdefault("away_team_id", away_team.id)
    match = _namespace({**match_raw, "home_team": home_team, "away_team": away_team, "competition": {"name": match_raw["competition"]}, "season": {"name": match_raw["season"]}})
    report_raw = raw["report"]
    reporter = _namespace(raw["reporter"])
    own_team = home_team if int(report_raw["own_team_id"]) == int(home_team.id) else away_team
    rival_team = home_team if int(report_raw["rival_team_id"]) == int(home_team.id) else away_team
    report = _namespace({**report_raw, "reporter": reporter, "match": match, "own_team": own_team, "rival_team": rival_team})
    players = {}
    participations = []
    for p in raw.get("participations", []):
        player = _NS(
            id=p["player_id"], full_name=p["player_name"], display_name=p["player_name"],
            primary_position=p.get("position"), photo_b64=p.get("photo_b64"), photo_mime=p.get("photo_mime"),
        )
        players[p["player_id"]] = player
        participations.append(_NS(**{**p, "player": player, "player_id": p["player_id"]}))
    evaluations = {}
    for e in raw.get("evaluations", []):
        player = players.get(e["player_id"]) or _NS(id=e["player_id"], full_name=e["player_name"], display_name=e["player_name"], primary_position=None)
        evaluations[e["player_id"]] = _NS(**{**e, "player": player})
    own, rival = [], []
    for part in participations:
        row = {"participation": part, "evaluation": evaluations.get(part.player_id)}
        if int(part.team_id) == int(report.rival_team_id):
            rival.append(row)
        elif int(part.team_id) == int(report.own_team_id):
            own.append(row)
    evaluated = [r for r in rival if r["evaluation"] and r["evaluation"].observation_status == "evaluated" and r["evaluation"].general_rating is not None]
    evaluated.sort(key=lambda r: r["evaluation"].general_rating or 0, reverse=True)
    noteworthy = [r for r in evaluated if r["evaluation"].standout or (r["evaluation"].recommendation or "") in {"Seguimiento recomendado", "Jugador interesante", "Prioridad de seguimiento"}]
    standout = next((r for r in rival if r["participation"].player_id == report.standout_player_id), None)
    return {
        "report": report, "match": match, "own_players": own, "rival_players": rival,
        "evaluated_players": evaluated, "noteworthy_players": noteworthy, "standout_row": standout,
        "settings": raw.get("settings", {}), "snapshot_version": item,
    }

def build_report_payload(session: Session, report_id: int, version: int | None = None) -> dict:
    if version is not None:
        return _snapshot_report_payload(session, report_id, version)
    report = repo.get_report(session, report_id)
    if not report:
        raise ValueError("Informe no encontrado.")
    match = report.match
    participations = repo.get_participations(session, match.id)
    evaluations = {ev.player_id: ev for ev in repo.list_evaluations(session, report.id)}
    own, rival = [], []
    for part in participations:
        row = {"participation": part, "evaluation": evaluations.get(part.player_id)}
        if part.team_id == report.rival_team_id:
            rival.append(row)
        elif part.team_id == report.own_team_id:
            own.append(row)
    evaluated = [r for r in rival if r["evaluation"] and r["evaluation"].observation_status == "evaluated" and r["evaluation"].general_rating is not None]
    evaluated.sort(key=lambda r: r["evaluation"].general_rating or 0, reverse=True)
    noteworthy = [r for r in evaluated if r["evaluation"].standout or (r["evaluation"].recommendation or "") in {"Seguimiento recomendado", "Jugador interesante", "Prioridad de seguimiento"}]
    standout = next((r for r in rival if r["participation"].player_id == report.standout_player_id), None)
    return {
        "report": report, "match": match, "own_players": own, "rival_players": rival,
        "evaluated_players": evaluated, "noteworthy_players": noteworthy, "standout_row": standout,
        "settings": repo.get_all_settings(session), "consensus": repo.match_consensus(session, match.id),
    }

def report_filename(session: Session, report_id: int, version: int | None = None, mode: str = "full") -> str:
    payload = build_report_payload(session, report_id, version=version)
    match, report = payload["match"], payload["report"]
    date_str = match.match_date.strftime("%Y-%m-%d") if hasattr(match.match_date, "strftime") else str(match.match_date)[:10]
    return f"NoName_Informe_{date_str}_{_slug(match.home_team.name)}_vs_{_slug(match.away_team.name)}_V{version or report.version}_{mode}.pdf"
