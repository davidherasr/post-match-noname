from __future__ import annotations

from dataclasses import dataclass


AUTO_STANDOUT_THRESHOLD = 8.0


@dataclass(frozen=True)
class SimpleEvaluationState:
    observation_status: str
    general_rating: float | None
    pdf_include: bool
    standout: bool


def derive_simple_evaluation_state(
    rating: float | int | None,
    *,
    pdf_include: bool = True,
    standout: bool = False,
    pdf_manually_changed: bool = False,
    standout_manually_changed: bool = False,
    threshold: float = AUTO_STANDOUT_THRESHOLD,
) -> SimpleEvaluationState:
    """Apply the lightweight report rules used by the player cards.

    A zero score means that the player has not been evaluated. Any positive
    score creates a valid observation. PDF inclusion is enabled automatically
    unless the user has explicitly changed it. A score of 8 or more is marked
    as standout automatically unless the user has explicitly overridden it.
    """
    score = float(rating or 0.0)
    if score <= 0:
        return SimpleEvaluationState(
            observation_status="not_observed",
            general_rating=None,
            pdf_include=bool(pdf_include),
            standout=False if not standout_manually_changed else bool(standout),
        )

    return SimpleEvaluationState(
        observation_status="evaluated",
        general_rating=score,
        pdf_include=bool(pdf_include) if pdf_manually_changed else True,
        standout=bool(standout) if standout_manually_changed else score >= threshold,
    )
