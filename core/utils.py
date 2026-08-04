from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from html import escape
from typing import Any


def normalize_name(value: str) -> str:
    """Unicode-safe normalization used for matching, never for display."""
    text = unicodedata.normalize("NFKD", (value or "").strip().casefold())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w\s-]+", " ", text, flags=re.UNICODE)
    text = text.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def safe_html(value: object | None) -> str:
    return escape("" if value is None else str(value), quote=True)


def json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def rating_label(value: float | None) -> str:
    if value is None:
        return "Sin muestra"
    if value >= 8.5:
        return "Excelente"
    if value >= 7.5:
        return "Muy destacado"
    if value >= 6.5:
        return "Buen partido"
    if value >= 5.5:
        return "Correcto"
    if value >= 4.5:
        return "Discreto"
    return "Bajo"
