from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import or_, select
from models.entities import Match
from repositories.data_governance import official_match_clause, official_team_clause
from sqlalchemy.orm import Session, joinedload

from models.entities import (
    GameModelRole, Player, PlayerSeasonDecision, ScoutObservation, ScoutedPlayerProfile,
    Team, TeamRoster,
)
from repositories import advanced_scouting as advanced_repo
from repositories import league_intelligence as league_repo
from repositories import planning as planning_repo
from repositories import scouting as base_repo
from repositories.data_governance import official_match_clause


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
    # 3.8 stores the model role explicitly. attributes_json remains readable only
    # for observations created before the migration.
    if getattr(observation, "model_role_id", None):
        return int(observation.model_role_id)
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
            .join(Team, Team.id == TeamRoster.team_id)
            .where(TeamRoster.player_id == int(player_id), TeamRoster.season_id == int(season_id), TeamRoster.active.is_(True), official_team_clause())
            .order_by(TeamRoster.updated_at.desc())
        )
        if roster:
            return roster.team
    if history:
        return history[0]["team"]
    # Never show a player's current club as their historical club when the
    # selected season has no documented roster or match evidence.
    if season_id:
        return None
    roster = session.scalar(
        select(TeamRoster).options(joinedload(TeamRoster.team))
        .join(Team, Team.id == TeamRoster.team_id)
        .where(TeamRoster.player_id == int(player_id), TeamRoster.active.is_(True), official_team_clause())
        .order_by(TeamRoster.updated_at.desc())
    )
    return roster.team if roster else None


def _postmatch_metrics(history: list[dict]) -> dict:
    rows = [h for h in history if h["evaluation"].general_rating is not None and float(h["evaluation"].general_rating) > 0 and h["evaluation"].observation_status == "evaluated"]
    ratings = [float(h["evaluation"].general_rating) for h in rows]
    avg = _mean(ratings)
    dispersion = None
    if len(ratings) > 1 and len({h["reporter"].id for h in rows}) > 1:
        dispersion = math.sqrt(sum((x - avg) ** 2 for x in ratings) / len(ratings))
    reporters = len({h["reporter"].id for h in rows})
    last = max((h["match"].match_date for h in rows), default=None)
    confidence = league_repo.confidence_score(len(rows), reporters, float(dispersion or 0), last)
    return {
        "average": avg,
        "observations": len(rows),
        "reporters": reporters,
        "dispersion": round(float(dispersion), 2) if dispersion is not None else None,
        "standouts": sum(1 for h in rows if h["evaluation"].standout),
        "last_observed": last,
        "confidence": confidence,
    }


def _timeline(history: list[dict], observations: list[ScoutObservation]) -> list[dict]:
    """One visible event per player/match/author, with a single authoritative grade.

    Legacy duplicate rows are preserved in the database for audited DD review;
    they are not multiplied in the PDF or player chronology.
    """
    rows: list[dict] = []
    grouped: dict[tuple, list[ScoutObservation]] = defaultdict(list)
    for obs in observations:
        if obs.status == "submitted":
            key = (obs.match_id, obs.reviewer_id) if obs.match_id is not None else ("standalone", obs.id)
            grouped[key].append(obs)

    def best(items: list[ScoutObservation], evaluation_id: int | None = None) -> ScoutObservation:
        # A linked and documented observation is the preferred enrichment.
        return max(items, key=lambda o: (
            bool(evaluation_id and o.player_evaluation_id == evaluation_id),
            bool(o.player_evaluation_id),
            sum(bool(v) for v in (o.summary, o.strengths, o.weaknesses, o.recommendation)),
            o.updated_at or o.created_at,
        ))

    for item in history:
        ev = item["evaluation"]
        if ev.general_rating is None or float(ev.general_rating) <= 0 or ev.observation_status != "evaluated":
            continue
        match = item["match"]
        key = (match.id, item["reporter"].id)
        supplements = grouped.pop(key, [])
        supplement = best(supplements, ev.id) if supplements else None
        notes = [str(ev.short_note or "").strip()]
        if supplement and supplement.summary and supplement.summary.strip() not in notes:
            notes.append(supplement.summary.strip())
        rows.append({
            "date": match.match_date,
            "source": "Postpartido + seguimiento" if supplement else "Postpartido",
            "rating": float(ev.general_rating),
            "position": (item["participation"].position if item.get("participation") else None) or (supplement.observed_position if supplement else None),
            "match": f"{match.home_team.name} - {match.away_team.name}",
            "observer": item["reporter"].full_name,
            "note": "\n".join(note for note in notes if note),
        })
    for group in grouped.values():
        obs = best(group)
        rows.append({
            "date": obs.observed_at.date() if hasattr(obs.observed_at, "date") else obs.observed_at,
            "source": "Seguimiento individual" if obs.source_type == "specific" else ("Apunte rápido histórico" if obs.source_type == "match_scan" else "Observación individual"),
            "rating": float(obs.general_rating) if obs.general_rating is not None else None,
            "position": obs.observed_position,
            "match": "-" if not obs.match else f"{obs.match.home_team.name} - {obs.match.away_team.name}",
            "observer": obs.reviewer.full_name,
            "note": obs.summary or "",
        })
    rows.sort(key=lambda x: (x["date"] or date.min, x["source"]))
    return rows


def _role_for_player(session: Session, profile: ScoutedPlayerProfile | None, decision: PlayerSeasonDecision | None) -> GameModelRole | None:
    # PlayerSeasonDecision is the only operational DD truth in 3.8. Legacy
    # ScoutedPlayerProfile remains available for audit/migration but cannot
    # override the current season decision.
    return decision.model_role if decision and decision.model_role else None


def _criteria_for_decision(decision: PlayerSeasonDecision | None, observations: list[ScoutObservation], role_id: int | None) -> dict[int, float]:
    if decision and decision.criteria_json:
        scores = _json_scores(decision.criteria_json)
        if scores:
            return scores
    return _aggregate_criteria(observations, role_id)



def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _shift_month(value: date, offset: int) -> date:
    total = value.year * 12 + (value.month - 1) + offset
    return date(total // 12, total % 12 + 1, 1)


def _monthly_postmatch(history: list[dict], months: int = 12) -> list[dict]:
    end = _month_start(date.today().year, date.today().month)
    starts = [_shift_month(end, -(months - 1 - i)) for i in range(months)]
    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)
    for item in history:
        ev = item["evaluation"]
        if ev.observation_status != "evaluated" or ev.general_rating is None or float(ev.general_rating) <= 0:
            continue
        d = item["match"].match_date
        buckets[(d.year, d.month)].append(float(ev.general_rating))
    labels = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
    result = []
    for start in starts:
        values = buckets.get((start.year, start.month), [])
        result.append({
            "month": start,
            "label": f"{labels[start.month-1]} {str(start.year)[2:]}",
            "rating": round(sum(values) / len(values), 2) if values else None,
            "observations": len(values),
        })
    return result


def _season_summary(session: Session, history: list[dict], observations: list[ScoutObservation]) -> list[dict]:
    buckets: dict[int, dict] = {}
    for item in history:
        match = item["match"]
        ev = item["evaluation"]
        if ev.observation_status != "evaluated" or ev.general_rating is None or float(ev.general_rating) <= 0:
            continue
        row = buckets.setdefault(match.season_id, {"ratings": [], "postmatch": 0, "scout": 0, "teams": Counter()})
        row["ratings"].append(float(ev.general_rating)); row["postmatch"] += 1
        if item.get("team"):
            row["teams"][item["team"].name] += 1
    for obs in observations:
        if obs.status != "submitted" or not obs.match:
            continue
        row = buckets.setdefault(obs.match.season_id, {"ratings": [], "postmatch": 0, "scout": 0, "teams": Counter()})
        row["scout"] += 1
    result = []
    from models.entities import Season
    for season_id, row in buckets.items():
        season = session.get(Season, int(season_id))
        team_name = row["teams"].most_common(1)[0][0] if row["teams"] else None
        result.append({
            "season_id": season_id, "season": season.name if season else str(season_id), "team": team_name,
            "postmatch": row["postmatch"], "scout": row["scout"], "average": _mean(row["ratings"]),
        })
    result.sort(key=lambda r: r["season"], reverse=True)
    return result


def _comparison_pool(session: Session, *, season_id: int | None, player_id: int, role: GameModelRole | None, target_scores: dict[int, float], target_fit: float | None) -> tuple[list[dict], list[dict]]:
    if not season_id or not role:
        return [], []
    decisions = list(session.scalars(
        select(PlayerSeasonDecision)
        .options(joinedload(PlayerSeasonDecision.player), joinedload(PlayerSeasonDecision.model_role))
        .where(PlayerSeasonDecision.season_id == int(season_id), PlayerSeasonDecision.model_role_id == role.id, PlayerSeasonDecision.player_id != int(player_id))
    ).unique().all())
    from repositories.players import get_own_team
    own_team = get_own_team(session)
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
                    ScoutObservation.profile_id.in_(profile_ids), ScoutObservation.status == "submitted",
                    or_(ScoutObservation.match_id.is_(None), ScoutObservation.match_id.in_(select(Match.id).where(official_match_clause())))
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
    history = base_repo.player_history_by_scope(session, player.id, scope="all")
    if season_id:
        history = [item for item in history if item["match"].season_id == int(season_id)]
    own_history = [item for item in history if item["evaluation"].evaluation_scope == "own"
                   and item["evaluation"].team_id == item["report"].own_team_id]
    rival_history = [item for item in history if item["evaluation"].evaluation_scope == "rival"
                     and item["evaluation"].team_id == item["report"].rival_team_id]
    observations = planning_repo.list_observations(session, player_id=player.id, limit=200)
    valid_match_ids = set(session.scalars(select(Match.id).where(official_match_clause())).all())
    submitted = [o for o in observations if o.status == "submitted"
                 and (o.match_id is None or o.match_id in valid_match_ids)
                 and (not season_id or (o.match_id is not None and o.match.season_id == int(season_id)))]
    # A previous release could save the same match/player/author several times.
    # Keep all physical rows for audit, use one representative for every metric.
    deduped: dict[tuple, ScoutObservation] = {}
    for o in submitted:
        key = (o.reviewer_id, o.match_id) if o.match_id is not None else ("standalone", o.id)
        old = deduped.get(key)
        if old is None or (bool(o.player_evaluation_id), bool(o.summary), o.updated_at) > (bool(old.player_evaluation_id), bool(old.summary), old.updated_at):
            deduped[key] = o
    submitted = list(deduped.values())
    team = _current_team(session, player.id, season_id, history)
    from repositories.players import get_own_team
    own_team = get_own_team(session)
    is_own_player = bool(own_team and team and own_team.id == team.id)
    # Keep both evidence streams. The headline follows the player's documented
    # season/team; never collapse own performance into rival scouting signals.
    own_metrics = _postmatch_metrics(own_history)
    rival_metrics = _postmatch_metrics(rival_history)
    metrics = own_metrics if is_own_player else rival_metrics
    positions = league_repo.observed_position_counts(session, player.id, season_id=season_id)
    if is_own_player:
        from collections import defaultdict as _defaultdict
        position_totals = _defaultdict(int)
        for item in own_history:
            ev = item["evaluation"]
            if ev.observation_status == "evaluated" and ev.general_rating and ev.general_rating > 0:
                position = (item["participation"].position if item.get("participation") else None) or player.primary_position or "Otro"
                position_totals[position] += 1
        positions = [{"position": key, "observations": value} for key, value in position_totals.items()]
    # Add positions coming only from individual tracking without inventing ratings.
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
    fit = decision.fit_score if decision and decision.fit_score is not None else _mean(o.model_fit_score for o in submitted)
    current_level = decision.current_level if decision and decision.current_level is not None else _mean(o.current_level for o in submitted)
    potential = decision.potential_score if decision and decision.potential_score is not None else _mean(o.potential_score for o in submitted)
    evidence = planning_repo.scouting_evidence_summary(session, player.id, season_id=season_id)
    if is_own_player:
        # The generic scouting batch counts rival evaluations by design; the
        # internal player's evidence is their OWN delivered postmatch history.
        evidence.update(postmatch_observations=own_metrics["observations"],
                        postmatch_reporters=own_metrics["reporters"],
                        postmatch_last=own_metrics["last_observed"])
    internal, comparables = _comparison_pool(session, season_id=season_id, player_id=player.id, role=role, target_scores=criteria_scores, target_fit=fit)
    timeline = _timeline(history, submitted)
    strengths = _text_points(submitted, "strengths")
    weaknesses = _text_points(submitted, "weaknesses")
    summary = decision.director_note if decision and decision.director_note else (latest.summary if latest else None)
    recommendation = decision.status if decision else (latest.recommendation if latest else None)

    return {
        "player": player,
        "team": team,
        "age": _age(player.date_of_birth),
        "season_id": season_id,
        "profile": profile,
        "decision": decision,
        "role": role,
        "postmatch": metrics,
        "own_postmatch": own_metrics,
        "rival_postmatch": rival_metrics,
        "is_own_player": is_own_player,
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
        "monthly_ratings": _monthly_postmatch(history),
        "season_summary": _season_summary(session, history, submitted),
    }
