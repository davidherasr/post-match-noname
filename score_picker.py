"""Exact, accessible 0–10 rating choices for daily match reports.

Zero is a sentinel for 'not evaluated', never a sporting rating. Decimal scores
saved by older releases remain selectable without silently rounding them.
"""
from __future__ import annotations


def rating_choices(current: float | None = None) -> tuple[list[str], str]:
    value = float(current or 0.0)
    if not 0.0 <= value <= 10.0:
        raise ValueError("La nota debe estar entre 0 y 10.")
    options = ["Sin evaluar"] + [str(number) for number in range(1, 11)]
    if value > 0 and not value.is_integer():
        old_label = f"{value:g}".replace(".", ",")
        options.insert(1 + int(value), old_label)
        return options, old_label
    return options, ("Sin evaluar" if value == 0 else str(int(value)))


def rating_from_choice(choice: str | None) -> float:
    if not choice or choice == "Sin evaluar":
        return 0.0
    value = float(choice.replace(",", "."))
    if not 0.0 < value <= 10.0:
        raise ValueError("Selecciona una nota válida de 1 a 10.")
    return value
