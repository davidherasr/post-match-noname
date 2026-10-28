"""Offer known squad members without inventing an appearance in a match."""
from __future__ import annotations
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from models.entities import TeamRoster


def optional_player_choices(session: Session, *, season_id: int, team_id: int,
                            confirmed: list) -> tuple[list, bool]:
    """Confirmed participations take priority; otherwise show seasonal roster as UNCONFIRMED.

    Synthetic choices exist only in memory. Their participation_id is None,
    they do not create a Participation or imply that a squad player played.
    """
    if confirmed:
        return list(confirmed), False
    roster = session.scalars(select(TeamRoster).options(joinedload(TeamRoster.player))
        .where(TeamRoster.season_id == season_id, TeamRoster.team_id == team_id,
               TeamRoster.active.is_(True))
        .order_by(TeamRoster.shirt_number, TeamRoster.player_id).limit(120)).all()
    choices = [SimpleNamespace(id=None, player_id=r.player_id, team_id=team_id,
                 shirt_number=r.shirt_number, player=r.player, starter=None,
                 from_roster=True) for r in roster if r.player and r.player.merged_into_id is None]
    return choices, bool(choices)
