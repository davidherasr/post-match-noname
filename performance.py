from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter

import streamlit as st

_MAX_EVENTS = 120
_ACTIVE_MEASURES: ContextVar[tuple[dict, ...]] = ContextVar("pm_active_measures", default=())
_ENGINE_HOOKED: set[int] = set()


def _events() -> list[dict]:
    try:
        return st.session_state.setdefault("pm_perf_events", [])
    except Exception:
        return []


def register_engine_performance(engine) -> None:
    """Attach lightweight SQL timing hooks once per SQLAlchemy engine."""
    engine_id = id(engine)
    if engine_id in _ENGINE_HOOKED:
        return
    from sqlalchemy import event

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(_conn, _cursor, _statement, _parameters, context, _executemany):
        context._pm_query_started_at = perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(_conn, _cursor, _statement, _parameters, context, _executemany):
        started = getattr(context, "_pm_query_started_at", None)
        if started is None:
            return
        elapsed_ms = (perf_counter() - started) * 1000.0
        for counter in _ACTIVE_MEASURES.get():
            counter["db_ms"] += elapsed_ms
            counter["queries"] += 1

    _ENGINE_HOOKED.add(engine_id)


@contextmanager
def measure(label: str, category: str = "app"):
    """Measure total, database and non-database time for one operation.

    SQL executed through the application engine is counted automatically. Events live
    only in Streamlit session state; diagnostics never add writes to PostgreSQL.
    """
    counter = {"db_ms": 0.0, "queries": 0}
    stack = _ACTIVE_MEASURES.get()
    token = _ACTIVE_MEASURES.set(stack + (counter,))
    start = perf_counter()
    try:
        yield
    finally:
        total_ms = (perf_counter() - start) * 1000.0
        _ACTIVE_MEASURES.reset(token)
        db_ms = min(total_ms, float(counter["db_ms"]))
        event_row = {
            "label": label,
            "category": category,
            "total_ms": round(total_ms, 1),
            "db_ms": round(db_ms, 1),
            "render_ms": round(max(0.0, total_ms - db_ms), 1),
            "queries": int(counter["queries"]),
            # Backwards-compatible field used by older UI/tests.
            "ms": round(total_ms, 1),
        }
        events = _events()
        if events is not None:
            events.append(event_row)
            if len(events) > _MAX_EVENTS:
                del events[:-_MAX_EVENTS]


def performance_events() -> list[dict]:
    return list(_events())


def performance_summary() -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}
    for row in performance_events():
        key = (str(row.get("category", "app")), str(row.get("label", "-")))
        item = grouped.setdefault(key, {"category": key[0], "label": key[1], "runs": 0, "total_ms": 0.0, "db_ms": 0.0, "render_ms": 0.0, "queries": 0})
        item["runs"] += 1
        item["total_ms"] += float(row.get("total_ms", row.get("ms", 0.0)) or 0.0)
        item["db_ms"] += float(row.get("db_ms", 0.0) or 0.0)
        item["render_ms"] += float(row.get("render_ms", 0.0) or 0.0)
        item["queries"] += int(row.get("queries", 0) or 0)
    result = []
    for item in grouped.values():
        runs = max(1, item["runs"])
        result.append({
            "category": item["category"], "label": item["label"], "runs": item["runs"],
            "avg_total_ms": round(item["total_ms"] / runs, 1),
            "avg_db_ms": round(item["db_ms"] / runs, 1),
            "avg_render_ms": round(item["render_ms"] / runs, 1),
            "avg_queries": round(item["queries"] / runs, 1),
            "max_signal": round(item["total_ms"], 1),
        })
    result.sort(key=lambda r: (r["avg_total_ms"], r["avg_queries"]), reverse=True)
    return result


def clear_performance_events() -> None:
    try:
        st.session_state["pm_perf_events"] = []
    except Exception:
        pass
