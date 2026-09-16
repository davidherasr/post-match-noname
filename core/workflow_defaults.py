from __future__ import annotations

from core.constants import FORMATIONS
from repositories import scouting as repo


def recent_match_defaults(session, own_id: int, season_id: int) -> dict:
    """Return repetitive postmatch setup from the latest match in the active season.

    Only routine fields are carried forward: competition, No Name formation and
    reporter assignment. Rival, result, date and venue are deliberately left blank.
    """
    matches = [
        m
        for m in repo.list_matches(session, season_id=season_id, limit=20)
        if m.home_team_id == own_id or m.away_team_id == own_id
    ]
    if not matches:
        return {}
    latest = matches[0]
    own_formation = latest.home_formation if latest.home_team_id == own_id else latest.away_formation
    assignments = repo.list_assignments(session, match_id=latest.id)
    reporter_ids = [int(a.user_id) for a in assignments if a.status not in {"waived", "declined"}]
    return {
        "competition_id": int(latest.competition_id),
        "own_formation": own_formation if own_formation in FORMATIONS else "4-3-3",
        "reporter_ids": reporter_ids,
        "defaults_source_match_id": int(latest.id),
        "defaults_source_round": latest.round_name,
    }
