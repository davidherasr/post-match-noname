"""Explainable DD attention feed: evidence, sample size and provenance, never transfer decisions."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from statistics import mean
from sqlalchemy import select
from sqlalchemy.orm import Session
from models.entities import (Match, MatchOpinion, MatchOpinionPlayer, Player, PlayerEvaluation,
                             PlayerObservationResponse, PlayerObservationRequest, PlayerSeasonDecision, Report,
                             UnidentifiedPlayerSignal, User)
from repositories.data_governance import official_match_clause
from repositories.players import get_own_team


def _coverage(matches: int, reporters: int, events: int) -> str:
    if events <= 1 or matches <= 1 or reporters <= 1:
        return "Inicial"
    if matches < 3 or reporters < 2:
        return "Limitada"
    if matches < 5 or reporters < 3:
        return "Razonable"
    return "Amplia"


def attention_feed(session: Session, season_id: int) -> list[dict]:
    official = select(Match.id).where(Match.season_id == season_id, official_match_clause())
    own = get_own_team(session)
    own_id = own.id if own else None
    events: dict[tuple[int, int], list[dict]] = defaultdict(list)
    authors = {u.id: u.full_name for u in session.scalars(select(User)).all()}
    names = {p.id: p.display_name or p.full_name for p in session.scalars(select(Player).where(Player.merged_into_id.is_(None))).all()}
    decisions = {d.player_id: d.status for d in session.scalars(select(PlayerSeasonDecision)
                 .where(PlayerSeasonDecision.season_id == season_id)).all()}

    def push(pid, team, match, uid, rating, rank, signal, text, kind, eid, date, *, resolved=False):
        if not (rating is not None or rank is not None or signal or text):
            return
        if pid is None:
            return
        events[(pid, team)].append({"player_id": pid, "team_id": team, "match_id": match,
            "author_id": uid, "author": authors.get(uid, "Informador"),
            "rating": float(rating) if rating is not None else None,
            "rank": rank, "signal": bool(signal), "note": text,
            "kind": kind, "evidence_id": eid, "date": date, "from_unidentified": resolved})

    for e, report in session.execute(select(PlayerEvaluation, Report)
        .join(Report, Report.id == PlayerEvaluation.report_id)
        .where(Report.match_id.in_(official), Report.status.in_(["incorporated", "approved", "final"]))):
        push(e.player_id, e.team_id, report.match_id, report.reporter_id,
             e.general_rating, e.highlight_rank, e.attention_signal or e.standout,
             e.short_note, "own_report", e.id, e.updated_at)
    for row, opinion in session.execute(select(MatchOpinionPlayer, MatchOpinion)
        .join(MatchOpinion, MatchOpinion.id == MatchOpinionPlayer.opinion_id)
        .where(MatchOpinion.match_id.in_(official))):
        push(row.player_id, row.team_id, opinion.match_id, opinion.user_id,
             row.rating, row.highlight_rank, row.attention_signal, row.note,
             "neutral", row.id, row.updated_at)
    pending_unknown = []
    for row in session.scalars(select(UnidentifiedPlayerSignal).where(UnidentifiedPlayerSignal.match_id.in_(official))).all():
        if row.source == "own_report" and not session.scalar(select(Report.id).where(
                Report.match_id == row.match_id, Report.reporter_id == row.user_id,
                Report.status.in_(["incorporated", "approved", "final"]))):
            continue  # A sporting draft is not delivered evidence.
        if row.resolved_player_id is not None:
            push(row.resolved_player_id, row.team_id, row.match_id, row.user_id,
                 row.rating, row.highlight_rank, row.attention_signal, row.note,
                 "resolved_unknown", row.id, row.updated_at, resolved=True)
        else:
            pending_unknown.append(row)
    out = []
    for (pid, team_id), records in events.items():
        # Each author / match / team / player must be counted once even if an
        # old anonymous signal was later linked to a named evaluation.
        by_context = defaultdict(list)
        for e in records:
            by_context[(e["match_id"], e["author_id"])].append(e)
        dedup = []
        for group in by_context.values():
            group.sort(key=lambda e: (e["from_unidentified"], e["rating"] is None))
            dedup.append(group[0])
        matches = {e["match_id"] for e in dedup}
        distinct_authors = {e["author_id"] for e in dedup}
        scores = [e["rating"] for e in dedup if e["rating"] is not None]
        high_matches = {e["match_id"] for e in dedup if e["rating"] is not None and e["rating"] >= 8}
        highlights = sum(e["rank"] is not None for e in dedup)
        top_ones = sum(e["rank"] == 1 for e in dedup)
        disagreements = []
        for mid in matches:
            seen = [e for e in dedup if e["match_id"] == mid and e["rating"] is not None]
            if len(seen) >= 2 and max(e["rating"] for e in seen) - min(e["rating"] for e in seen) >= 2.0:
                disagreements.append({"match_id": mid, "ratings": [(e["author"], e["rating"]) for e in seen]})
        reasons = []
        if len(high_matches) >= 2:
            reasons.append("Nota ≥8 en dos o más partidos")
        elif len(high_matches) == 1:
            reasons.append("Primera nota ≥8, muestra todavía inicial" if len(matches) == 1 else "Nota ≥8 en un partido")
        if len(distinct_authors) >= 2:
            reasons.append("Coincidencia de observadores; no implica acuerdo en la nota")
        if highlights >= 2:
            reasons.append("Top 3 repetido")
        elif highlights == 1:
            reasons.append("Primer destacado Top 3")
        if any(e["signal"] for e in dedup) and not scores and not highlights:
            reasons.append("Señal cualitativa sin nota; evidencia inicial")
        if disagreements:
            reasons.append("Discrepancia de notas ≥2 puntos en el mismo partido")
        status = decisions.get(pid)
        if status in {"Interesante", "Seguimiento", "Prioritario"}:
            reasons.append("Nueva o existente evidencia sobre selección de DD")
        if not reasons:
            continue
        out.append({"player_id": pid, "name": names.get(pid, f"Jugador {pid}"),
            "team_id": team_id, "own_team": team_id == own_id,
            "ratings": scores, "average": round(mean(scores), 2) if scores else None,
            "matches": len(matches), "authors": len(distinct_authors), "events": len(dedup),
            "high_matches": len(high_matches), "highlights": highlights, "top_ones": top_ones,
            "coverage": _coverage(len(matches), len(distinct_authors), len(dedup)),
            "reasons": reasons, "disagreements": disagreements, "status": status,
            "evidence": sorted(dedup, key=lambda e: e["date"] or datetime.min, reverse=True),
            "last_observed": max((e["date"] for e in dedup if e["date"]), default=None)})
    # Anonymous identities remain separate; never conflate different author
    # / match / shirts by guesses (two #11s need not be the same footballer).
    for row in pending_unknown:
        out.append({"player_id": None, "unknown_id": row.id,
            "name": row.label or "Jugador sin identificar", "team_id": row.team_id,
            "own_team": row.team_id == own_id,
            "matches": 1, "authors": 1, "events": 1,
            "average": row.rating, "ratings": [row.rating] if row.rating is not None else [],
            "highlights": int(row.highlight_rank is not None), "top_ones": int(row.highlight_rank == 1),
            "coverage": "Inicial", "reasons": ["Identidad pendiente de verificar"],
            "status": None, "disagreements": [], "last_observed": row.updated_at,
            "evidence": [{"kind": "unknown", "match_id": row.match_id, "author_id": row.user_id,
                         "author": authors.get(row.user_id), "rating": row.rating, "rank": row.highlight_rank,
                         "signal": row.attention_signal, "note": row.note, "evidence_id": row.id}]})
    out.sort(key=lambda row: (row.get("own_team", False),
        any("Discrepancia" in x for x in row["reasons"]),
        row["matches"], row["authors"], row["last_observed"] or datetime.min), reverse=True)
    return out


def team_knowledge(session: Session, season_id: int, team_id: int) -> dict:
    """Team file keeps observed form separate from roster identity and unconfirmed shapes."""
    matches = list(session.scalars(select(Match).where(
        Match.season_id == season_id, official_match_clause(),
        ((Match.home_team_id == team_id) | (Match.away_team_id == team_id)))
        .order_by(Match.match_date.desc())).all())
    formations = defaultdict(list)
    for m in matches:
        home = m.home_team_id == team_id
        known = m.home_formation_known if home else m.away_formation_known
        form = m.home_formation if home else m.away_formation
        if known and form:
            formations[form].append(m)
    observed = sorted(((k, len(v), max(m.match_date for m in v)) for k,v in formations.items()),
        key=lambda x: (-x[1], -x[2].toordinal()))
    signals = [row for row in attention_feed(session, season_id) if row["team_id"] == team_id]
    relevant = [s for s in signals if s["player_id"] is None or s["ratings"] or s["highlights"]]
    return {"matches": matches, "formations": observed, "signals": relevant,
        "last_observed": matches[0].match_date if matches else None}


def recent_request_responses(session: Session, season_id: int, *, limit: int = 8) -> list[dict]:
    """Return contextual replies for DD without manufacturing further evaluations."""
    responses = session.execute(select(PlayerObservationResponse, PlayerObservationRequest)
        .join(PlayerObservationRequest, PlayerObservationResponse.request_id == PlayerObservationRequest.id)
        .where(PlayerObservationRequest.season_id == int(season_id))
        .order_by(PlayerObservationResponse.created_at.desc(), PlayerObservationResponse.id.desc())
        .limit(limit)).all()
    people = {u.id: u.full_name for u in session.scalars(select(User)).all()}
    result = []
    for row, request in responses:
        player = session.get(Player, request.player_id)
        result.append({"response_id": row.id, "request_id": request.id, "player_id": request.player_id,
            "name": player.display_name or player.full_name if player else f"Jugador {request.player_id}",
            "author": people.get(row.user_id, "Informador"), "result": row.result,
            "note": row.note, "question": request.question, "match_id": row.match_id,
            "evidence_origin": ("informe" if request.origin_player_evaluation_id else
                                "neutral" if request.origin_neutral_signal_id else
                                "señal originalmente anónima" if request.origin_unidentified_signal_id else None)})
    return result
