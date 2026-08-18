from __future__ import annotations


def is_schedule_confirmed(match) -> bool:
    """True only when the fixture has a definitive date *and* kickoff time.

    The federation calendar may provide a reference Sunday for a round, but that
    date is operationally provisional until Administration confirms the actual
    kickoff.
    """
    return bool(match and getattr(match, "schedule_status", None) == "confirmed" and getattr(match, "kickoff_at", None))


def require_schedule_confirmed(match, *, action: str = "continuar") -> None:
    if not is_schedule_confirmed(match):
        raise ValueError(
            f"No se puede {action}: este partido todavía tiene fecha orientativa y horario pendiente. "
            "Administración debe confirmar la fecha y la hora definitivas en Calendario."
        )
