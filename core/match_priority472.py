"""Choose routine fixtures without presenting postponements as played matches."""
from __future__ import annotations

SKIP={'aplazado','postponed','postponed_match','cancelado','cancelled','canceled'}


def eligible(match):
    status=str(getattr(match,'schedule_status','') or '').casefold().strip()
    return status not in SKIP and getattr(match,'deleted_at',None) is None


def current_fixtures(matches, today):
    """Return last scheduled past match and next future match.

    Without score or independent confirmation the result is a *calendar* anchor,
    not a claim that the fixture actually took place.
    """
    rows=[m for m in matches if eligible(m)]
    last=next((m for m in rows if m.match_date<=today),None)
    future=next((m for m in reversed(rows) if m.match_date>today),None)
    return last,future
