from __future__ import annotations

import json
import math
from collections import Counter
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from models.entities import (
    GameModelRole, Player, PlayerSeasonDecision, ScoutObservation, ScoutedPlayerProfile,
    Team, TeamRoster,
)
from repositories import advanced_scouting as advanced_repo
from repositories import league_intelligence as league_repo
from repositories import planning as planning_repo
from repositories import scouting as base_repo


def _mean(values):
    vals = [float(v) for v in values if v is not None and float(v) > 0]
    return round(sum(vals) / len(vals), 2) if vals else None


def _json_scores(value: str | None) -> dict[int, float]:
    if not value:
        return {}
    try:
        raw = json.loads(value)
    except Exception:
        return {}
    result: dict[int, float] = {}
    if isinstance(raw, dict):
        for key, val in raw.items():
            if str(key) == "model_role_id":
                continue
            try:
                number = float(val)
                if number > 0:
                    result[int(key)] = number
            except (TypeError, ValueError):
                continue
    return result


def _observation_role_id(observation: ScoutObservation) -> int | None:
    if not observation.attributes_json:
        return None
    try:
        raw = json.loads(observation.attributes_json)
        value = raw.get("model_role_id") if isinstance(raw, dict) else None
        return int(value) if value else None
    except Exception:
        return None


def _aggregate_criteria(observations: list[ScoutObservation], role_id: int | None) -> dict[int, float]:
    buckets: dict[int, list[float]] = {}
    for observation in observations:
        if observation.status != "submitted":
            continue
        obs_role_id = _observation_role_id(observation)
        if role_id and obs_role_id and int(obs_role_id) != int(role_id):
            continue
        for criterion_id, score in _json_scores(observation.attributes_json).items():
            buckets.setdefault(criterion_id, []).append(float(score))
    return {criterion_id: round(sum(vals) / len(vals), 2) for criterion_id, vals in buckets.items() if vals}


def _text_points(rows: list[ScoutObservation], field: str, limit: int = 5) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for row in rows:
        text = str(getattr(row, field, "") or "").strip()
        if not text:
            continue
        chunks = [x.strip(" -•\t") for line in text.splitlines() for x in line.split(";")]
        for chunk in chunks:
            if len(chunk) < 3:
                continue
            key = chunk.casefold()
            if key not in seen:
                seen.add(key)
                result.append(chunk)
            if len(result) >= limit:
                return result
    return result


def _age(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _current_team(session: Session, player_id: int, season_id: int | None, history: list[dict]) -> Team | None:
    if season_id:
        roster = session.scalar(
            select(TeamRoster)
            .options(joinedload(TeamRoster.team))
            .where(TeamRoster.player_id == int(player_id), TeamRoster.season_id == int(season_id), TeamRoster.active.is_(True))
            .order_by(TeamRoster.updated_at.desc())
        )
        if roster:
            return roster.team
    if history:
        return history[0]["team"]
    roster = session.scalar(
        select(TeamRoster).options(joinedload(TeamRoster.team))
        .where(TeamRoster.player_id == int(player_id), TeamRoster.active.is_(True))
        .order_by(TeamRoster.updated_at.desc())
    )
    return roster.team if roster else None


def _postmatch_metrics(history: list[dict]) -> dict:
    rows = [h for h in history if h["evaluation"].general_rating is not None and h["evaluation"].observation_status == "evaluated"]
    ratings = [float(h["evaluation"].general_rating) for h in rows]
    avg = _mean(ratings)
    dispersion = None
    if ratings:
        dispersion = math.sqrt(sum((x - avg) ** 2 for x in ratings) / len(ratings)) if len(ratings) > 1 else 0.0
    reporters = len({h["reporter"].id for h in rows})
    last = max((h["match"].match_date for h in rows), default=None)
    confidence = league_repo.confidence_score(len(rows), reporters, float(dispersion or 0), last)
    return {
        "average": avg,
        "observations": len(rows),
        "reporters": reporters,
        "dispersion": round(float(dispersion or 0), 2) if rows else None,
        "standouts": sum(1 for h in rows if h["evaluation"].standout),
        "last_observed": last,
        "confidence": confidence,
    }


def _timeline(history: list[dict], observations: list[ScoutObservation]) -> list[dict]:
    rows: list[dict] = []
    for item in history:
        ev = item["evaluation"]
        if ev.general_rating is None or ev.observation_status != "evaluated":
            continue
        match = item["match"]
        rows.append({
            "date": match.match_date,
            "source": "Postpartido",
            "rating": float(ev.general_rating),
            "position": item["participation"].position if item.get("participation") else None,
            "match": f"{match.home_team.name} - {match.away_team.name}",
            "observer": item["reporter"].full_name,
            "note": ev.short_note or "",
        })
    for obs in observations:
        if obs.status != "submitted" or obs.general_rating is None:
            continue
        rows.append({
            "date": obs.observed_at.date() if hasattr(obs.observed_at, "date") else obs.observed_at,
            "source": "Scout específico" if obs.source_type == "specific" else ("Barrido Scout" if obs.source_type == "match_scan" else "Scout espontáneo"),
            "rating": float(obs.general_rating),
            "position": obs.observed_position,
            "match": "-" if not obs.match else f"{obs.match.home_team.name} - {obs.match.away_team.name}",
            "observer": obs.reviewer.full_name,
            "note": obs.summary or "",
        })
    rows.sort(key=lambda x: (x["date"] or date.min, x["source"]))
    return rows


def _role_for_player(session: Session, profile: ScoutedPlayerProfile | None, decision: PlayerSeasonDecision | None) -> GameModelRole | None:
    if decision and decision.model_role:
        return decision.model_role
    if not profile or not profile.model_role:
        return None
    return session.scalar(select(GameModelRole).where(GameModelRole.name == profile.model_role, GameModelRole.position == profile.model_position))


def _criteria_for_decision(decision: PlayerSeasonDecision | None, observations: list[ScoutObservation], role_id: int | None) -> dict[int, float]:
    if decision and decision.criteria_json:
        scores = _json_scores(decision.criteria_json)
        if scores:
            return scores
    return _aggregate_criteria(observations, role_id)


def _comparison_pool(session: Session, *, season_id: int | None, player_id: int, role: GameModelRole | None, target_scores: dict[int, float], target_fit: float | None) -> tuple[list[dict], list[dict]]:
    if not season_id or not role:
        return [], []
    decisions = list(session.scalars(
        select(PlayerSeasonDecision)
        .options(joinedload(PlayerSeasonDecision.player), joinedload(PlayerSeasonDecision.model_role))
        .where(PlayerSeasonDecision.season_id == int(season_id), PlayerSeasonDecision.model_role_id == role.id, PlayerSeasonDecision.player_id != int(player_id))
    ).unique().all())
    own_team = session.scalar(select(Team).where(Team.is_own_team.is_(True)))
    own_ids: set[int] = set()
    if own_team:
        own_ids = set(session.scalars(select(TeamRoster.player_id).where(
            TeamRoster.team_id == own_team.id, TeamRoster.season_id == int(season_id), TeamRoster.active.is_(True)
        )).all())

    candidate_ids = [d.player_id for d in decisions if d.player_id not in own_ids]
    profiles = {}
    observations_by_player: dict[int, list[ScoutObservation]] = {}
    if candidate_ids:
        for profile in session.scalars(select(ScoutedPlayerProfile).where(ScoutedPlayerProfile.player_id.in_(candidate_ids))).all():
            profiles[profile.player_id] = profile
        profile_ids = [p.id for p in profiles.values()]
        if profile_ids:
            obs_rows = list(session.scalars(
                select(ScoutObservation).options(joinedload(ScoutObservation.profile)).where(
                    ScoutObservation.profile_id.in_(profile_ids), ScoutObservation.status == "submitted"
                )
            ).unique().all())
            for obs in obs_rows:
                observations_by_player.setdefault(obs.profile.player_id, []).append(obs)

    def row_for(decision: PlayerSeasonDecision) -> dict:
        scores = _json_scores(decision.criteria_json)
        if not scores and decision.player_id in observations_by_player:
            scores = _aggregate_criteria(observations_by_player[decision.player_id], role.id)
        common = sorted(set(target_scores) & set(scores))
        similarity = None
        if common:
            mae = sum(abs(target_scores[c] - scores[c]) for c in common) / len(common)
            similarity = max(0, round(100 - mae * 10))
            if target_fit is not None and decision.fit_score is not None:
                fit_similarity = max(0, 100 - abs(float(target_fit) - float(decision.fit_score)) * 10)
                similarity = round(similarity * .75 + fit_similarity * .25)
        elif target_fit is not None and decision.fit_score is not None:
            similarity = max(0, round(100 - abs(float(target_fit) - float(decision.fit_score)) * 10))
        return {
            "player_id": decision.player_id,
            "name": decision.player.display_name or decision.player.full_name,
            "fit": decision.fit_score,
            "current_level": decision.current_level,
            "potential": decision.potential_score,
            "status": decision.status,
            "similarity": similarity,
            "criteria_scores": scores,
        }

    internal = [row_for(d) for d in decisions if d.player_id in own_ids]
    candidates = [row_for(d) for d in decisions if d.player_id not in own_ids]
    internal.sort(key=lambda x: (-(x["fit"] or 0), x["name"]))
    candidates.sort(key=lambda x: (-(x["similarity"] or -1), -(x["fit"] or 0), x["name"]))
    return internal[:6], candidates[:6]


def build_player_report_360(session: Session, player_id: int, *, season_id: int | None = None) -> dict:
    player = session.get(Player, int(player_id))
    if not player:
        raise ValueError("Jugador no encontrado.")
    profile = advanced_repo.get_profile(session, player.id)
    history = base_repo.player_history(session, player.id)
    observations = planning_repo.list_observations(session, player_id=player.id, limit=200)
    submitted = [o for o in observations if o.status == "submitted"]
    team = _current_team(session, player.id, season_id, history)
    metrics = _postmatch_metrics(history)
    positions = league_repo.observed_position_counts(session, player.id, season_id=season_id)
    # Add Scout-only positions without inventing ratings.
    scout_pos = Counter(o.observed_position for o in submitted if o.observed_position)
    known = {str(r["position"]): int(r["observations"]) for r in positions if r.get("position")}
    for pos, count in scout_pos.items():
        known[pos] = known.get(pos, 0) + count
    position_rows = [{"position": pos, "observations": count} for pos, count in sorted(known.items(), key=lambda x: (-x[1], x[0]))]

    decision = None
    if season_id:
        decision = session.scalar(
            select(PlayerSeasonDecision)
            .options(joinedload(PlayerSeasonDecision.model_role), joinedload(PlayerSeasonDecision.player))
            .where(PlayerSeasonDecision.season_id == int(season_id), PlayerSeasonDecision.player_id == player.id)
        )
    role = _role_for_player(session, profile, decision)
    criteria = planning_repo.list_model_criteria(session, role.id) if role else []
    criteria_scores = _criteria_for_decision(decision, submitted, role.id if role else None)
    criteria_rows = [{
        "id": c.id, "name": c.name, "category": c.category, "weight": c.weight,
        "description": c.description or "", "score": criteria_scores.get(c.id),
    } for c in criteria]

    block_scores = {
        "Técnico": _mean(o.technical_rating for o in submitted),
        "Táctico": _mean(o.tactical_rating for o in submitted),
        "Físico": _mean(o.physical_rating for o in submitted),
        "Mental": _mean(o.mental_rating for o in submitted),
    }
    scout_general = _mean(o.general_rating for o in submitted)
    latest = next((o for o in submitted if any([o.summary, o.strengths, o.weaknesses, o.recommendation])), submitted[0] if submitted else None)
    fit = (decision.fit_score if decision and decision.fit_score is not None else (profile.fit_score if profile and profile.fit_score is not None else _mean(o.model_fit_score for o in submitted)))
    current_level = (decision.current_level if decision and decision.current_level is not None else (profile.current_level if profile and profile.current_level is not None else _mean(o.current_level for o in submitted)))
    potential = (decision.potential_score if decision and decision.potential_score is not None else (profile.potential_score if profile and profile.potential_score is not None else _mean(o.potential_score for o in submitted)))
    evidence = planning_repo.scouting_evidence_summary(session, player.id, season_id=season_id)
    internal, comparables = _comparison_pool(session, season_id=season_id, player_id=player.id, role=role, target_scores=criteria_scores, target_fit=fit)
    timeline = _timeline(history, submitted)
    strengths = _text_points(submitted, "strengths")
    weaknesses = _text_points(submitted, "weaknesses")
    summary = (profile.director_summary if profile and profile.director_summary else (latest.summary if latest else None))
    recommendation = (profile.final_decision if profile and profile.final_decision else (latest.recommendation if latest else None))

    return {
        "player": player,
        "team": team,
        "age": _age(player.date_of_birth),
        "season_id": season_id,
        "profile": profile,
        "decision": decision,
        "role": role,
        "postmatch": metrics,
        "scout_average": scout_general,
        "block_scores": block_scores,
        "fit_score": fit,
        "current_level": current_level,
        "potential_score": potential,
        "criteria": criteria_rows,
        "positions": position_rows,
        "timeline": timeline,
        "observations": submitted,
        "evidence": evidence,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "summary": summary,
        "recommendation": recommendation,
        "own_comparison": internal,
        "comparables": comparables,
    }
