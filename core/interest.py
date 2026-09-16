"""Separate explicit sporting selections from automatically detected candidates.

A staff mention is evidence, not a DD decision.  Keep the shortlist small and
always disclose the sample behind the optional >=8 discovery filter.
"""
from __future__ import annotations

SELECTED_STATUSES = frozenset({"Interesante", "Seguimiento", "Prioritario"})


def explicitly_selected(*, decision_status: str | None = None,
                        has_open_request: bool = False,
                        has_formal_tracking: bool = False) -> bool:
    return bool(decision_status in SELECTED_STATUSES or has_open_request or has_formal_tracking)


def qualifies_for_discovery(signal: dict | None, *, minimum_rating: float = 8.0,
                            minimum_matches: int = 2) -> bool:
    """Discovery is a filter, NEVER an automatic DD decision or recruitment order."""
    if not signal:
        return False
    rating = signal.get("weighted_rating")
    return (rating is not None and float(rating) >= minimum_rating
            and int(signal.get("match_count") or 0) >= minimum_matches)
