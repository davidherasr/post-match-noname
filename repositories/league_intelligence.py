from __future__ import annotations

import math
from collections import Counter
from datetime import date

from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.orm import Session

from models.entities import FollowUp, LeaguePlayerProfile, Match, Participation, Player, PlayerEvaluation, Report, Team
from repositories import scouting as base_repo


def observed_position_counts(session: Session, player_id: int, *, season_id: int | None = None) -> list[dict]:
    stmt = (
        select(
            func.coalesce(Participation.position, Player.primary_position).label("position"),
            func.count(PlayerEvaluation.id).label("observations"),
            func.avg(PlayerEvaluation.general_rating).label("average"),
            func.max(Match.match_date).label("last_observed"),
        )
        .select_from(PlayerEvaluation)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(Player, PlayerEvaluation.player_id == Player.id)
        .outerjoin(Participation, PlayerEvaluation.participation_id == Participation.id)
        .where(PlayerEvaluation.player_id == int(player_id), *base_repo._valid_rival_evaluation_predicates())
    )
    if season_id:
        stmt = stmt.where(Match.season_id == int(season_id))
    stmt = stmt.group_by(func.coalesce(Participation.position, Player.primary_position)).order_by(desc(func.count(PlayerEvaluation.id)), desc(func.avg(PlayerEvaluation.general_rating)))
    return [dict(r) for r in session.execute(stmt).mappings().all()]


def ranking_for_observed_position(session: Session, position: str, *, season_id: int | None = None, min_observations: int = 1, limit: int = 100) -> list[dict]:
    # base_repo.player_rankings already filters by Participation.position; this helper
    # also stamps the requested observed position to avoid using an arbitrary MAX().
    rows = base_repo.player_rankings(session, min_observations=min_observations, position=position, season_id=season_id, limit=limit)
    for row in rows:
        row["observed_position"] = position
        row["primary_position"] = position
    return rows


def confidence_score(observations: int, reporter_count: int, dispersion: float, last_observed: date | None = None) -> dict:
    """Explainable 0-100 confidence score for our own observation sample."""
    observations = max(0, int(observations or 0))
    reporter_count = max(0, int(reporter_count or 0))
    dispersion = max(0.0, float(dispersion or 0.0))

    sample_score = 0 if observations == 0 else 8 if observations == 1 else 20 if observations == 2 else 30 if observations == 3 else 36 if observations == 4 else 40
    reporter_score = 0 if reporter_count == 0 else 5 if reporter_count == 1 else 12 if reporter_count == 2 else 17 if reporter_count == 3 else 20
    if dispersion <= 0.35:
        consensus_score, consensus_label = 25, "Muy alto"
    elif dispersion <= 0.75:
        consensus_score, consensus_label = 21, "Alto"
    elif dispersion <= 1.25:
        consensus_score, consensus_label = 15, "Medio"
    elif dispersion <= 1.75:
        consensus_score, consensus_label = 8, "Bajo"
    else:
        consensus_score, consensus_label = 2, "Muy bajo"

    recency_score = 0
    recency_label = "Sin fecha"
    days_since = None
    if last_observed is not None:
        observed_date = last_observed.date() if hasattr(last_observed, "date") and not isinstance(last_observed, date) else last_observed
        days_since = max(0, (date.today() - observed_date).days)
        if days_since <= 21:
            recency_score, recency_label = 15, "Muy reciente"
        elif days_since <= 45:
            recency_score, recency_label = 12, "Reciente"
        elif days_since <= 90:
            recency_score, recency_label = 8, "Aceptable"
        elif days_since <= 180:
            recency_score, recency_label = 4, "Antigua"
        else:
            recency_score, recency_label = 0, "Muy antigua"

    score = int(min(100, sample_score + reporter_score + consensus_score + recency_score))
    label = "Alta" if score >= 75 else "Media" if score >= 50 else "Baja"
    return {
        "score": score, "label": label, "sample": observations, "reporters": reporter_count, "dispersion": dispersion,
        "consensus": consensus_label, "recency": recency_label, "days_since": days_since,
        "components": {
            "Muestra": {"score": sample_score, "max": 40, "detail": f"{observations} observaciones"},
            "Informadores": {"score": reporter_score, "max": 20, "detail": f"{reporter_count} informadores"},
            "Consenso": {"score": consensus_score, "max": 25, "detail": consensus_label},
            "Recencia": {"score": recency_score, "max": 15, "detail": recency_label},
        },
    }


def robust_trends(session: Session, *, season_id: int | None = None, min_observations: int = 4, limit: int = 20) -> list[dict]:
    stmt = (
        select(PlayerEvaluation.player_id, Player.full_name, PlayerEvaluation.general_rating, Match.match_date)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(Player, PlayerEvaluation.player_id == Player.id)
        .where(*base_repo._valid_rival_evaluation_predicates())
        .order_by(PlayerEvaluation.player_id, Match.match_date, PlayerEvaluation.id)
    )
    if season_id:
        stmt = stmt.where(Match.season_id == int(season_id))
    grouped: dict[int, dict] = {}
    for pid, name, rating, observed_at in session.execute(stmt).all():
        grouped.setdefault(int(pid), {"player_id": int(pid), "full_name": name, "values": []})["values"].append((observed_at, float(rating)))
    result = []
    required = max(4, int(min_observations or 4))
    for row in grouped.values():
        values = row["values"]
        if len(values) < required:
            continue
        # Two non-overlapping windows. With 4-5 observations use two; with 6+ use three.
        window = 3 if len(values) >= 6 else 2
        early_values = [v for _, v in values[:window]]
        recent_values = [v for _, v in values[-window:]]
        early = sum(early_values) / len(early_values)
        recent = sum(recent_values) / len(recent_values)
        mean = sum(v for _, v in values) / len(values)
        variance = sum((v - mean) ** 2 for _, v in values) / len(values)
        dispersion = math.sqrt(max(0.0, variance))
        delta = recent - early
        direction = "En subida" if delta >= 0.45 else "En bajada" if delta <= -0.45 else "Estable"
        reliability = "Alta" if len(values) >= 6 and dispersion <= 1.0 else "Media" if len(values) >= 4 else "Baja"
        result.append({
            "player_id": row["player_id"], "full_name": row["full_name"], "observations": len(values),
            "window": window, "early_average": early, "recent_average": recent, "delta": delta,
            "dispersion": dispersion, "last_observed": values[-1][0], "direction": direction, "trend_reliability": reliability,
        })
    result.sort(key=lambda x: (abs(x["delta"]), x["observations"]), reverse=True)
    return result[: int(limit)]


def enhanced_decision_queue(session: Session, *, season_id: int | None = None, limit: int = 25) -> list[dict]:
    rows = base_repo.player_rankings(session, min_observations=1, season_id=season_id, limit=500)
    profiles = {p.player_id: p for p in base_repo.list_league_profiles(session)}
    teams = base_repo.latest_player_team_map(session, [int(r["player_id"]) for r in rows])
    followups = {f.player_id: f for f in base_repo.list_follow_ups(session)}
    today = date.today()
    result = []
    for row in rows:
        pid = int(row["player_id"])
        profile = profiles.get(pid)
        followup = followups.get(pid)
        decision = profile.decision_status if profile else "Base"
        conf = confidence_score(row["observations"], row["reporter_count"], row["rating_dispersion"], row.get("last_observed"))
        reasons = []
        urgency = 0
        if followup and followup.status not in {"Descartado", "Cerrado"} and followup.next_review_date and followup.next_review_date < today:
            reasons.append(f"seguimiento vencido {((today-followup.next_review_date).days)} días")
            urgency += 4
        if followup and followup.priority == 1 and row.get("last_observed"):
            last = row["last_observed"]
            if (today - last).days >= 35:
                reasons.append(f"prioritario sin observar {(today-last).days} días")
                urgency += 3
        if row["standouts"] >= 3:
            reasons.append(f"{row['standouts']} destacados repetidos")
            urgency += 3
        elif row["standouts"] >= 2:
            reasons.append(f"{row['standouts']} destacados")
            urgency += 2
        if row["avg_general"] >= 8.0:
            reasons.append(f"media {row['avg_general']:.1f}")
            urgency += 2
        if row["observations"] >= 3 and decision == "Base":
            reasons.append("3+ observaciones sin decisión")
            urgency += 3
        if row["reporter_count"] >= 2 and row["rating_dispersion"] >= 1.25:
            reasons.append("opiniones divididas")
            urgency += 2
        if not reasons:
            continue
        result.append({**row, **teams.get(pid, {}), "decision_status": decision, "confidence": conf["label"], "confidence_score": conf["score"], "reasons": reasons, "urgency": urgency})
    result.sort(key=lambda x: (x["urgency"], x["decision_status"] == "Base", x["confidence_score"], x["avg_general"]), reverse=True)
    return result[: int(limit)]


def team_intelligence(session: Session, team_id: int, *, season_id: int | None = None) -> dict:
    rankings = base_repo.player_rankings(session, min_observations=1, season_id=season_id, team_id=int(team_id), limit=200)
    profiles = {p.player_id: p for p in base_repo.list_league_profiles(session)}
    followed = {f.player_id: f for f in base_repo.list_follow_ups(session)}
    own = base_repo.get_own_team(session)
    latest_match = base_repo.previous_match_with_team(session, own.id, opponent_id=int(team_id)) if own else None
    latest_lineup = base_repo.get_participations(session, latest_match.id, int(team_id)) if latest_match else []
    players = []
    for row in rankings:
        pid = int(row["player_id"])
        profile = profiles.get(pid)
        follow = followed.get(pid)
        conf = confidence_score(row["observations"], row["reporter_count"], row["rating_dispersion"], row.get("last_observed"))
        players.append({**row, "decision_status": profile.decision_status if profile else "Base", "priority": profile.priority if profile else 3, "followup_status": follow.status if follow else None, "confidence_score": conf["score"]})
    players.sort(key=lambda x: (x["decision_status"] == "Prioritario", x["decision_status"] == "Seguimiento", x["standouts"], x["avg_general"]), reverse=True)
    most_observed = sorted(players, key=lambda x: (x["observations"], x["avg_general"]), reverse=True)[:8]
    interest = [p for p in players if p["decision_status"] in {"Interesante", "Seguimiento", "Prioritario"} or p["standouts"] >= 1][:10]
    known_xi = []
    for part in sorted(latest_lineup, key=lambda p: (not p.starter, p.position or "", p.id)):
        if not part.starter:
            continue
        known_xi.append({
            "player_id": part.player_id, "full_name": part.player.display_name or part.player.full_name,
            "position": part.position or part.player.primary_position or "Otro", "shirt_number": part.shirt_number,
        })
    return {
        "team": session.get(Team, int(team_id)), "players": players, "interest": interest, "most_observed": most_observed, "known_xi": known_xi,
        "known": len(players), "standouts": sum(1 for p in players if p["standouts"]),
        "followups": sum(1 for p in players if p["followup_status"]),
        "priority": sum(1 for p in players if p["decision_status"] == "Prioritario"),
        "latest_match": latest_match,
    }


def position_candidate_pool(session: Session, *, season_id: int | None = None, min_observations: int = 1) -> list[dict]:
    """One SQL aggregate for every player+observed-position pair used by XI/rankings."""
    pos = func.coalesce(Participation.position, Player.primary_position)
    rating = PlayerEvaluation.general_rating
    stmt = (
        select(
            Player.id.label("player_id"), Player.full_name, pos.label("observed_position"),
            func.count(PlayerEvaluation.id).label("observations"),
            func.avg(rating).label("avg_general"), func.avg(rating * rating).label("avg_sq"),
            func.count(func.distinct(Report.reporter_id)).label("reporter_count"),
            func.sum(case((PlayerEvaluation.standout.is_(True), 1), else_=0)).label("standouts"),
            func.max(Match.match_date).label("last_observed"),
        )
        .select_from(PlayerEvaluation)
        .join(Report, PlayerEvaluation.report_id == Report.id)
        .join(Match, Report.match_id == Match.id)
        .join(Player, PlayerEvaluation.player_id == Player.id)
        .outerjoin(Participation, PlayerEvaluation.participation_id == Participation.id)
        .where(*base_repo._valid_rival_evaluation_predicates())
    )
    if season_id:
        stmt = stmt.where(Match.season_id == int(season_id))
    stmt = stmt.group_by(Player.id, Player.full_name, pos).having(func.count(PlayerEvaluation.id) >= int(min_observations))
    rows = []
    for r in session.execute(stmt).mappings().all():
        avg = float(r["avg_general"] or 0)
        variance = max(0.0, float(r["avg_sq"] or avg * avg) - avg * avg)
        conf = confidence_score(int(r["observations"] or 0), int(r["reporter_count"] or 0), math.sqrt(variance), r["last_observed"])
        rows.append({
            "player_id": int(r["player_id"]), "full_name": r["full_name"], "observed_position": r["observed_position"] or "Otro",
            "observations": int(r["observations"] or 0), "avg_general": avg, "rating_dispersion": math.sqrt(variance),
            "reporter_count": int(r["reporter_count"] or 0), "standouts": int(r["standouts"] or 0), "last_observed": r["last_observed"],
            "confidence_score": conf["score"], "confidence": conf["label"],
        })
    return rows
