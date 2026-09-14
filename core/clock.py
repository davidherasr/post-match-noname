from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

# No Name operates in Spain. Streamlit Cloud runs in UTC, so football-day
# decisions must not depend on the server timezone.
APP_TIMEZONE = ZoneInfo("Europe/Madrid")


def local_now() -> datetime:
    """Current timezone-aware date/time for the club's operational day."""
    return datetime.now(APP_TIMEZONE)


def local_today() -> date:
    return local_now().date()
