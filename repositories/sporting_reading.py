from __future__ import annotations

from repositories.data_governance import official_match_clause

from collections import defaultdict
from datetime import datetime, timezone
import math

from sqlalchemy import and_, delete, desc, or_, select
from sqlalchemy.orm import Session, joinedload

from models.entities import (
    FollowUp,
    Match,
    MatchOpinion,
    MatchOpinionPlayer,
    PlayerEvaluation,
    Report,
    ScoutedPlayerProfile,
    StaffSportingWeight,
    Team,
    TeamRoster,
    User,
)
from repositories.common import audit
from repositories import users as users_repo
from repositories import players as players_repo

UTC_NOW = lambda: datetime.now(timezone.utc).replace(tzinfo=None)
WEIGHT_LEVELS = {
    0.50: "Bajo",
    1.00: "Normal",
    1.25: "Alto",
    1.50: "Referencia",
}


def _clamp_rating(value: float | int | None) -> float | None:
    if value is None:
        return None
    score = float(value)
    if score <= 0:
        return None
    if score > 10:
        raise ValueError("Las notas deben estar entre 0 y 10.")
    return round(score, 1)


def _clamp_weight(value: float | int) -> float:
    score = float(value)
    if score < 0.25 or score > 2.0:
        raise ValueError("El peso debe estar entre 0,25 y 2,00.")
    return round(score, 2)


def list_sporting_staff(session: Session) -> list[User]:
    rows = users_repo.list_users(session, active_only=True)
    return [u for u in rows if users_repo.user_has_role(session, u.id, "reporter", "director")]


def get_staff_weight(session: Session, user_id: int) -> StaffSportingWeight | None:
    return session.scalar(
        select(StaffSportingWeight)
        .options(joinedload(StaffSportingWeight.user))
        .where(StaffSportingWeight.user_id == int(user_id))
    )


def weight_map(session: Session) -> dict[int, StaffSportingWeight]:
    return {
        row.user_id: row
        for row in session.scalars(
            select(StaffSportingWeight).options(joinedload(StaffSportingWeight.user))
        ).unique().all()
    }


def upsert_staff_weight(
    session: Session,
    *,
    actor_id: int,
    user_id: int,
    own_match_weight: float,
    neutral_match_weight: float,
) -> StaffSportingWeight:
    users_repo.assert_role(session, actor_id, "director")
    user = session.get(User, int(user_id))
    if not user or not user.active or user.deleted_at is not None:
        raise ValueError("Usuario no disponible.")
    item = session.scalar(select(StaffSportingWeight).where(StaffSportingWeight.user_id == int(user_id)))
    before = None
    if item is None:
        item = StaffSportingWeight(
            user_id=int(user_id),
            own_match_weight=1.0,
            neutral_match_weight=1.0,
            updated_by=int(actor_id),
            created_at=UTC_NOW(),
            updated_at=UTC_NOW(),
        )
        session.add(item)
        session.flush()
    else:
        before = {"own_match_weight": item.own_match_weight, "neutral_match_weight": item.neutral_match_weight}
    item.own_match_weight = _clamp_weight(own_match_weight)
    item.neutral_match_weight = _clamp_weight(neutral_match_weight)
    item.updated_by = int(actor_id)
    item.updated_at = UTC_NOW()
    audit(
        session, actor_id, "update_staff_sporting_weight", "staff_sporting_weight", item.id,
        before=before,
        after={"own_match_weight": item.own_match_weight, "neutral_match_weight": item.neutral_match_weight},
    )
    return item


def get_match_opinion(session: Session, match_id: int, user_id: int) -> MatchOpinion | None:
    return session.scalar(
        select(MatchOpinion)
        .options(joinedload(MatchOpinion.user), joinedload(MatchOpinion.match))
        .where(MatchOpinion.match_id == int(match_id), MatchOpinion.user_id == int(user_id))
    )


def opinion_players(session: Session, opinion_id: int) -> list[MatchOpinionPlayer]:
    return list(session.scalars(
        select(MatchOpinionPlayer)
        .options(joinedload(MatchOpinionPlayer.player), joinedload(MatchOpinionPlayer.team))
        .where(MatchOpinionPlayer.opinion_id == int(opinion_id))
        .order_by(MatchOpinionPlayer.team_id, MatchOpinionPlayer.player_id)
    ).unique().all())


def save_neutral_opinion(
    session: Session,
    *,
    match_id: int,
    user_id: int,
    home_team_rating: float | None,
    away_team_rating: float | None,
    summary: str | None,
    player_rows: list[dict] | None = None,
) -> MatchOpinion:
    if not users_repo.user_has_role(session, int(user_id), "reporter"):
        raise PermissionError("Solo un usuario con rol Informador puede guardar una lectura de partido.")
    match = session.get(Match, int(match_id))
    if not match or match.deleted_at or match.is_test or match.status == "archived" or match.home_team.is_test or match.away_team.is_test or match.home_team.archived_at or match.away_team.archived_at:
        raise ValueError("Partido inexistente o excluido de la actividad oficial.")
    own = players_repo.get_own_team(session)
    if own and own.id in {match.home_team_id, match.away_team_id}:
        raise ValueError("Los partidos de No Name usan el flujo de postpartido, no la lectura neutral.")

    item = get_match_opinion(session, match.id, int(user_id))
    if item is None:
        item = MatchOpinion(match_id=match.id, user_id=int(user_id), created_at=UTC_NOW(), updated_at=UTC_NOW())
        session.add(item)
        session.flush()
    item.home_team_rating = _clamp_rating(home_team_rating)
    item.away_team_rating = _clamp_rating(away_team_rating)
    item.summary = (summary or "").strip() or None
    item.updated_at = UTC_NOW()

    session.execute(delete(MatchOpinionPlayer).where(MatchOpinionPlayer.opinion_id == item.id))
    allowed_team_ids = {match.home_team_id, match.away_team_id}
    seen: set[int] = set()
    for row in player_rows or []:
        player_id = int(row.get("player_id") or 0)
        team_id = int(row.get("team_id") or 0)
        if not player_id or player_id in seen or team_id not in allowed_team_ids:
            continue
        seen.add(player_id)
        session.add(MatchOpinionPlayer(
            opinion_id=item.id,
            player_id=player_id,
            team_id=team_id,
            rating=_clamp_rating(row.get("rating")),
            note=(row.get("note") or "").strip() or None,
            created_at=UTC_NOW(),
            updated_at=UTC_NOW(),
        ))
    session.flush()
    audit(session, user_id, "save_neutral_match_opinion", "match_opinion", item.id, detail=f"match={match.id}; players={len(seen)}")
    return item


def _weighted(values: list[tuple[float, float]]) -> float | None:
    clean = [(float(v), float(w)) for v, w in values if v is not None and w > 0]
    if not clean:
        return None
    denominator = sum(w for _, w in clean)
    if denominator <= 0:
        return None
    return sum(v * w for v, w in clean) / denominator


def _dispersion(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    return math.sqrt(sum((x - avg) ** 2 for x in values) / len(values))


def neutral_match_reading(session: Session, match_id: int) -> dict:
    opinions = list(session.scalars(
        select(MatchOpinion)
        .options(joinedload(MatchOpinion.user), joinedload(MatchOpinion.match).joinedload(Match.home_team), joinedload(MatchOpinion.match).joinedload(Match.away_team))
        .where(MatchOpinion.match_id == int(match_id), MatchOpinion.match_id.in_(select(Match.id).where(official_match_clause())))
        .order_by(MatchOpinion.updated_at)
    ).unique().all())
    weights = weight_map(session)
    player_rows = []
    if opinions:
        ids = [o.id for o in opinions]
        player_rows = list(session.scalars(
            select(MatchOpinionPlayer)
            .options(joinedload(MatchOpinionPlayer.player), joinedload(MatchOpinionPlayer.team), joinedload(MatchOpinionPlayer.opinion).joinedload(MatchOpinion.user))
            .where(MatchOpinionPlayer.opinion_id.in_(ids))
        ).unique().all())

    def w_for(uid: int) -> float:
        row = weights.get(uid)
        return float(row.neutral_match_weight if row else 1.0)

    home_pairs = [(o.home_team_rating, w_for(o.user_id)) for o in opinions if o.home_team_rating is not None]
    away_pairs = [(o.away_team_rating, w_for(o.user_id)) for o in opinions if o.away_team_rating is not None]
    grouped: dict[int, dict] = {}
    for row in player_rows:
        bucket = grouped.setdefault(row.player_id, {
            "player": row.player,
            "team": row.team,
            "mentions": 0,
            "weighted": [],
            "ratings": [],
            "notes": [],
            "users": [],
        })
        bucket["mentions"] += 1
        bucket["users"].append(row.opinion.user.full_name)
        if row.note:
            bucket["notes"].append(row.note)
        if row.rating is not None:
            bucket["ratings"].append(float(row.rating))
            bucket["weighted"].append((float(row.rating), w_for(row.opinion.user_id)))
    players = []
    for bucket in grouped.values():
        players.append({
            **{k: v for k, v in bucket.items() if k not in {"weighted", "ratings"}},
            "weighted_rating": _weighted(bucket["weighted"]),
            "dispersion": _dispersion(bucket["ratings"]),
        })
    players.sort(key=lambda r: (r["mentions"], r["weighted_rating"] or 0), reverse=True)
    return {
        "opinions": opinions,
        "home_weighted": _weighted(home_pairs),
        "away_weighted": _weighted(away_pairs),
        "home_dispersion": _dispersion([float(o.home_team_rating) for o in opinions if o.home_team_rating is not None]),
        "away_dispersion": _dispersion([float(o.away_team_rating) for o in opinions if o.away_team_rating is not None]),
        "players": players,
        "weights": weights,
    }


def own_match_reading(session: Session, match_id: int) -> dict:
    match = session.get(Match, int(match_id))
    if not match or match.deleted_at or match.is_test or match.status == "archived" or match.home_team.is_test or match.away_team.is_test or match.home_team.archived_at or match.away_team.archived_at:
        raise ValueError("Partido inexistente o excluido de la actividad oficial.")
    own = players_repo.get_own_team(session)
    if not own or own.id not in {match.home_team_id, match.away_team_id}:
        raise ValueError("Este partido no corresponde a No Name.")
    reports = list(session.scalars(
        select(Report)
        .options(joinedload(Report.reporter), joinedload(Report.rival_team), joinedload(Report.own_team))
        .where(Report.match_id == match.id, Report.status.in_(["approved", "final", "incorporated"]))
        .order_by(Report.updated_at)
    ).unique().all())
    weights = weight_map(session)

    def w_for(uid: int) -> float:
        row = weights.get(uid)
        return float(row.own_match_weight if row else 1.0)

    own_pairs = [(r.own_team_rating, w_for(r.reporter_id)) for r in reports if r.own_team_rating is not None]
    rival_pairs = [(r.rival_team_rating, w_for(r.reporter_id)) for r in reports if r.rival_team_rating is not None]

    evals = []
    if reports:
        report_ids = [r.id for r in reports]
        evals = list(session.scalars(
            select(PlayerEvaluation)
            .options(joinedload(PlayerEvaluation.player), joinedload(PlayerEvaluation.report).joinedload(Report.reporter), joinedload(PlayerEvaluation.team))
            .where(
                PlayerEvaluation.report_id.in_(report_ids),
                PlayerEvaluation.observation_status == "evaluated",
                PlayerEvaluation.general_rating.is_not(None),
            )
        ).unique().all())
    grouped: dict[int, dict] = {}
    for ev in evals:
        bucket = grouped.setdefault(ev.player_id, {
            "player": ev.player,
            "team": ev.team,
            "scope": ev.evaluation_scope,
            "weighted": [],
            "ratings": [],
            "notes": [],
            "reporters": set(),
        })
        value = float(ev.general_rating)
        bucket["weighted"].append((value, w_for(ev.report.reporter_id)))
        bucket["ratings"].append(value)
        bucket["reporters"].add(ev.report.reporter.full_name)
        if ev.short_note:
            bucket["notes"].append(ev.short_note)
    players = []
    for bucket in grouped.values():
        players.append({
            "player": bucket["player"],
            "team": bucket["team"],
            "scope": bucket["scope"],
            "weighted_rating": _weighted(bucket["weighted"]),
            "dispersion": _dispersion(bucket["ratings"]),
            "reporter_count": len(bucket["reporters"]),
            "reporters": sorted(bucket["reporters"]),
            "notes": bucket["notes"],
        })
    players.sort(key=lambda r: (r["scope"] != "own", -(r["weighted_rating"] or 0)))
    return {
        "reports": reports,
        "own_weighted": _weighted(own_pairs),
        "rival_weighted": _weighted(rival_pairs),
        "own_dispersion": _dispersion([float(r.own_team_rating) for r in reports if r.own_team_rating is not None]),
        "rival_dispersion": _dispersion([float(r.rival_team_rating) for r in reports if r.rival_team_rating is not None]),
        "players": players,
        "weights": weights,
    }



def recent_sporting_matches(session: Session, season_id: int, limit: int = 8) -> dict:
    """Recent DD reading cards, explicitly separated between No Name and neutral matches."""
    own = players_repo.get_own_team(session)
    own_matches: list[dict] = []
    neutral_matches: list[dict] = []
    if own:
        rows = list(session.scalars(
            select(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team), joinedload(Match.competition))
            .where(
                Match.season_id == int(season_id),
                official_match_clause(),
                or_(Match.home_team_id == own.id, Match.away_team_id == own.id),
            )
            .order_by(desc(Match.match_date), desc(Match.id))
            .limit(int(limit))
        ).unique().all())
        for match in rows:
            reading = own_match_reading(session, match.id)
            own_matches.append({"match": match, "reading": reading})

    neutral_rows = list(session.scalars(
        select(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team), joinedload(Match.competition))
        .join(MatchOpinion, MatchOpinion.match_id == Match.id)
        .where(
            Match.season_id == int(season_id),
            official_match_clause(),
            *(
                [Match.home_team_id != own.id, Match.away_team_id != own.id]
                if own else []
            ),
        )
        .distinct()
        .order_by(desc(Match.match_date), desc(Match.id))
        .limit(int(limit))
    ).unique().all())
    for match in neutral_rows:
        reading = neutral_match_reading(session, match.id)
        neutral_matches.append({"match": match, "reading": reading})
    return {"own": own_matches, "neutral": neutral_matches}


def consensus_label(dispersion: float | None, count: int | None = None) -> str:
    """Human-readable agreement band for staff ratings.

    Dispersion is the population standard deviation of the raw ratings. We keep
    the thresholds intentionally simple so DD gets a sporting signal instead of
    having to interpret a statistical value on every screen.
    """
    n = int(count or 0)
    if dispersion is None or n < 2:
        return "Sin contraste"
    value = float(dispersion)
    if value <= 0.45:
        return "Consenso muy alto"
    if value <= 0.80:
        return "Consenso alto"
    if value <= 1.25:
        return "Opiniones divididas"
    return "Discrepancia alta"


def trend_label(delta: float | None) -> str:
    if delta is None:
        return "—"
    if delta >= 0.75:
        return f"↑ +{delta:.1f}"
    if delta <= -0.75:
        return f"↓ {delta:.1f}"
    return f"→ {delta:+.1f}"


def _match_weighted_history(events: list[dict]) -> tuple[list[dict], float | None]:
    by_match: dict[int, list[dict]] = defaultdict(list)
    for event in events:
        by_match[int(event["match"].id)].append(event)
    history: list[dict] = []
    for rows in by_match.values():
        match = rows[0]["match"]
        pairs = [(row.get("rating"), row.get("weight", 1.0)) for row in rows if row.get("rating") is not None]
        score = _weighted(pairs)
        history.append({
            "match": match,
            "score": score,
            "mentions": len(rows),
            "dispersion": _dispersion([float(row["rating"]) for row in rows if row.get("rating") is not None]),
        })
    history.sort(key=lambda row: (row["match"].match_date, row["match"].id))
    rated = [row for row in history if row["score"] is not None]
    delta = None
    if len(rated) >= 2:
        delta = float(rated[-1]["score"]) - float(rated[0]["score"] )
    return history, delta


def league_intelligence(session: Session, season_id: int) -> dict:
    """Cross-match sporting intelligence for Dirección Deportiva.

    It combines two kinds of *signals* without turning them into tracking by
    themselves: highlighted players in neutral matches and rival-player ratings
    from No Name postmatches. Team readings follow the same split.
    """
    season_id = int(season_id)
    own = players_repo.get_own_team(session)
    own_id = own.id if own else None
    weights = weight_map(session)

    def neutral_weight(uid: int) -> float:
        row = weights.get(int(uid))
        return float(row.neutral_match_weight if row else 1.0)

    def own_weight(uid: int) -> float:
        row = weights.get(int(uid))
        return float(row.own_match_weight if row else 1.0)

    neutral_opinions = list(session.scalars(
        select(MatchOpinion)
        .options(
            joinedload(MatchOpinion.user),
            joinedload(MatchOpinion.match).joinedload(Match.home_team),
            joinedload(MatchOpinion.match).joinedload(Match.away_team),
        )
        .join(Match, MatchOpinion.match_id == Match.id)
        .where(
            Match.season_id == season_id,
            official_match_clause(),
            *(
                [Match.home_team_id != own_id, Match.away_team_id != own_id]
                if own_id else []
            ),
        )
        .order_by(Match.match_date, Match.id, MatchOpinion.id)
    ).unique().all())
    neutral_ids = [row.id for row in neutral_opinions]
    neutral_players = list(session.scalars(
        select(MatchOpinionPlayer)
        .options(
            joinedload(MatchOpinionPlayer.player),
            joinedload(MatchOpinionPlayer.team),
            joinedload(MatchOpinionPlayer.opinion).joinedload(MatchOpinion.user),
            joinedload(MatchOpinionPlayer.opinion).joinedload(MatchOpinion.match).joinedload(Match.home_team),
            joinedload(MatchOpinionPlayer.opinion).joinedload(MatchOpinion.match).joinedload(Match.away_team),
        )
        .where(MatchOpinionPlayer.opinion_id.in_(neutral_ids or [-1]))
    ).unique().all())

    own_reports = list(session.scalars(
        select(Report)
        .options(
            joinedload(Report.reporter), joinedload(Report.rival_team), joinedload(Report.own_team),
            joinedload(Report.match).joinedload(Match.home_team),
            joinedload(Report.match).joinedload(Match.away_team),
        )
        .join(Match, Report.match_id == Match.id)
        .where(
            Match.season_id == season_id, official_match_clause(),
            Report.status.in_(["approved", "final", "incorporated"]),
            *(
                [or_(Match.home_team_id == own_id, Match.away_team_id == own_id)]
                if own_id else []
            ),
        )
        .order_by(Match.match_date, Match.id, Report.id)
    ).unique().all())
    report_ids = [row.id for row in own_reports]
    rival_evals = list(session.scalars(
        select(PlayerEvaluation)
        .options(
            joinedload(PlayerEvaluation.player), joinedload(PlayerEvaluation.team),
            joinedload(PlayerEvaluation.report).joinedload(Report.reporter),
            joinedload(PlayerEvaluation.report).joinedload(Report.match).joinedload(Match.home_team),
            joinedload(PlayerEvaluation.report).joinedload(Report.match).joinedload(Match.away_team),
        )
        .where(
            PlayerEvaluation.report_id.in_(report_ids or [-1]),
            PlayerEvaluation.evaluation_scope == "rival",
            PlayerEvaluation.observation_status == "evaluated",
        )
    ).unique().all())

    player_buckets: dict[int, dict] = {}

    def add_player_event(*, player, team, match, user, rating, weight, note, source: str) -> None:
        if own_id and int(team.id) == int(own_id):
            return
        bucket = player_buckets.setdefault(player.id, {
            "player": player, "teams": {}, "events": [], "users": set(), "notes": [],
        })
        bucket["teams"][team.id] = team
        bucket["users"].add(user.full_name)
        if note:
            bucket["notes"].append(str(note).strip())
        bucket["events"].append({
            "match": match, "user": user, "rating": float(rating) if rating is not None else None,
            "weight": float(weight), "note": note, "source": source, "team": team,
        })

    for row in neutral_players:
        add_player_event(
            player=row.player, team=row.team, match=row.opinion.match, user=row.opinion.user,
            rating=row.rating, weight=neutral_weight(row.opinion.user_id), note=row.note, source="neutral",
        )
    for row in rival_evals:
        add_player_event(
            player=row.player, team=row.team, match=row.report.match, user=row.report.reporter,
            rating=row.general_rating, weight=own_weight(row.report.reporter_id), note=row.short_note, source="postmatch_rival",
        )

    player_ids = list(player_buckets)
    profiles = {
        row.player_id: row
        for row in session.scalars(
            select(ScoutedPlayerProfile).where(ScoutedPlayerProfile.player_id.in_(player_ids or [-1]))
        ).all()
    }
    players: list[dict] = []
    for bucket in player_buckets.values():
        events = bucket["events"]
        history, trend = _match_weighted_history(events)
        weighted = _weighted([(e["rating"], e["weight"]) for e in events if e["rating"] is not None])
        rated_values = [float(e["rating"]) for e in events if e["rating"] is not None]
        latest = max(events, key=lambda e: (e["match"].match_date, e["match"].id))
        profile = profiles.get(bucket["player"].id)
        players.append({
            "player": bucket["player"],
            "team": latest["team"],
            "teams": list(bucket["teams"].values()),
            "mentions": len(events),
            "match_count": len({e["match"].id for e in events}),
            "staff_count": len(bucket["users"]),
            "staff": sorted(bucket["users"]),
            "weighted_rating": weighted,
            "dispersion": _dispersion(rated_values),
            "consensus": consensus_label(_dispersion(rated_values), len(rated_values)),
            "history": history,
            "trend": trend,
            "latest_date": latest["match"].match_date,
            "notes": [n for n in bucket["notes"] if n][:5],
            "neutral_mentions": sum(1 for e in events if e["source"] == "neutral"),
            "postmatch_mentions": sum(1 for e in events if e["source"] == "postmatch_rival"),
            "tracking": profile,
        })
    players.sort(key=lambda row: (row["match_count"], row["mentions"], row["weighted_rating"] or 0, row["latest_date"]), reverse=True)

    team_buckets: dict[int, dict] = {}

    def add_team_event(*, team, match, user, rating, weight, source: str) -> None:
        if team is None or rating is None or (own_id and int(team.id) == int(own_id)):
            return
        bucket = team_buckets.setdefault(team.id, {"team": team, "events": [], "users": set()})
        bucket["users"].add(user.full_name)
        bucket["events"].append({
            "match": match, "user": user, "rating": float(rating), "weight": float(weight), "source": source,
        })

    for opinion in neutral_opinions:
        match = opinion.match
        # Old bad data is ignored defensively: a neutral opinion must not be used for No Name.
        if own_id and own_id in {match.home_team_id, match.away_team_id}:
            continue
        add_team_event(team=match.home_team, match=match, user=opinion.user, rating=opinion.home_team_rating, weight=neutral_weight(opinion.user_id), source="neutral")
        add_team_event(team=match.away_team, match=match, user=opinion.user, rating=opinion.away_team_rating, weight=neutral_weight(opinion.user_id), source="neutral")
    for report in own_reports:
        add_team_event(team=report.rival_team, match=report.match, user=report.reporter, rating=report.rival_team_rating, weight=own_weight(report.reporter_id), source="postmatch_rival")

    teams: list[dict] = []
    for bucket in team_buckets.values():
        events = bucket["events"]
        history, trend = _match_weighted_history(events)
        values = [float(e["rating"]) for e in events]
        latest = max(events, key=lambda e: (e["match"].match_date, e["match"].id))
        teams.append({
            "team": bucket["team"],
            "opinions": len(events),
            "match_count": len({e["match"].id for e in events}),
            "staff_count": len(bucket["users"]),
            "weighted_rating": _weighted([(e["rating"], e["weight"]) for e in events]),
            "dispersion": _dispersion(values),
            "consensus": consensus_label(_dispersion(values), len(values)),
            "history": history,
            "trend": trend,
            "latest_date": latest["match"].match_date,
        })
    teams.sort(key=lambda row: (row["match_count"], row["opinions"], row["weighted_rating"] or 0, row["latest_date"]), reverse=True)

    # Build disagreement cards at match level. This is more useful than a global
    # dispersion because DD can open the exact match that produced the split.
    disagreement_groups: dict[tuple, dict] = {}

    def add_disagreement_event(kind: str, entity_id: int, entity_name: str, match, user_name: str, rating: float | None) -> None:
        if rating is None:
            return
        key = (kind, int(entity_id), int(match.id))
        bucket = disagreement_groups.setdefault(key, {
            "kind": kind, "entity_id": int(entity_id), "entity_name": entity_name, "match": match, "ratings": [],
        })
        bucket["ratings"].append((str(user_name), float(rating)))

    for opinion in neutral_opinions:
        match = opinion.match
        if own_id and own_id in {match.home_team_id, match.away_team_id}:
            continue
        add_disagreement_event("Equipo", match.home_team_id, match.home_team.name, match, opinion.user.full_name, opinion.home_team_rating)
        add_disagreement_event("Equipo", match.away_team_id, match.away_team.name, match, opinion.user.full_name, opinion.away_team_rating)
    for report in own_reports:
        add_disagreement_event("No Name", report.own_team_id, report.own_team.name, report.match, report.reporter.full_name, report.own_team_rating)
        add_disagreement_event("Rival", report.rival_team_id, report.rival_team.name, report.match, report.reporter.full_name, report.rival_team_rating)
    for bucket in player_buckets.values():
        for event in bucket["events"]:
            add_disagreement_event("Jugador", bucket["player"].id, bucket["player"].display_name or bucket["player"].full_name, event["match"], event["user"].full_name, event["rating"])

    disagreements: list[dict] = []
    for bucket in disagreement_groups.values():
        ratings = bucket["ratings"]
        values = [score for _, score in ratings]
        dispersion = _dispersion(values)
        if dispersion is None:
            continue
        low = min(ratings, key=lambda x: x[1])
        high = max(ratings, key=lambda x: x[1])
        disagreements.append({
            **bucket,
            "dispersion": dispersion,
            "consensus": consensus_label(dispersion, len(values)),
            "low": low, "high": high,
            "count": len(values),
        })
    disagreements.sort(key=lambda row: (row["dispersion"], row["count"], row["match"].match_date), reverse=True)

    return {
        "players": players,
        "teams": teams,
        "disagreements": disagreements,
        "repeated_players": sum(1 for row in players if row["match_count"] >= 2),
        "high_disagreements": sum(1 for row in disagreements if row["dispersion"] > 1.25),
    }


def team_reading_history(session: Session, season_id: int, team_id: int) -> list[dict]:
    intel = league_intelligence(session, int(season_id))
    row = next((item for item in intel["teams"] if item["team"].id == int(team_id)), None)
    return list(row["history"]) if row else []

def user_can_track(session: Session, user_id: int) -> bool:
    user = session.get(User, int(user_id))
    return bool(user and user.active and user.deleted_at is None and user.can_track_players)


def start_player_tracking(session: Session, *, player_id: int, actor_id: int, note: str | None = None) -> ScoutedPlayerProfile:
    if not user_can_track(session, actor_id):
        raise PermissionError("Tu usuario no tiene permiso de seguimiento individual de jugadores.")
    player_id = int(player_id)
    own = players_repo.get_own_team(session)
    if own:
        own_roster = session.scalar(
            select(TeamRoster.id)
            .where(TeamRoster.player_id == player_id, TeamRoster.team_id == own.id, TeamRoster.active.is_(True))
            .limit(1)
        )
        if own_roster:
            raise ValueError("Los jugadores de No Name se evalúan como plantilla propia; no se abren como seguimiento de mercado.")
    profile = session.scalar(select(ScoutedPlayerProfile).where(ScoutedPlayerProfile.player_id == player_id))
    if profile is None:
        profile = ScoutedPlayerProfile(
            player_id=player_id,
            status="candidate",
            requested_by=int(actor_id),
            assigned_to=int(actor_id),
            revision=1,
            created_at=UTC_NOW(),
            updated_at=UTC_NOW(),
        )
        session.add(profile)
        session.flush()
    else:
        profile.assigned_to = int(actor_id)
        if profile.status == "archived":
            profile.status = "candidate"
        profile.updated_at = UTC_NOW()
        profile.revision = int(profile.revision or 0) + 1
    follow = session.scalar(select(FollowUp).where(FollowUp.player_id == player_id))
    if follow is None:
        follow = FollowUp(
            player_id=player_id,
            status="Pendiente de primera revisión",
            priority=2,
            note=(note or "").strip() or None,
            assigned_to=int(actor_id),
            revision=1,
            created_by=int(actor_id),
            created_at=UTC_NOW(),
            updated_at=UTC_NOW(),
        )
        session.add(follow)
    else:
        follow.status = "Seguimiento" if follow.status in {"Descartado", "Cerrado"} else follow.status
        follow.assigned_to = int(actor_id)
        if note and not follow.note:
            follow.note = note.strip()
        follow.updated_at = UTC_NOW()
        follow.revision = int(follow.revision or 0) + 1
    session.flush()
    audit(session, actor_id, "start_player_tracking", "scouted_player_profile", profile.id, detail=f"player={player_id}")
    return profile
