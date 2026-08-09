from __future__ import annotations

from core.config import settings
from core.database import session_scope
from repositories import scouting as repo


def bootstrap_application() -> None:
    """Create only technical bootstrap data required to enter the application.

    No teams, players, competitions, seasons, matches or reports are seeded.
    The first administrator comes exclusively from environment/Streamlit Secrets.
    """
    with session_scope() as session:
        if repo.count_users(session) == 0:
            repo.create_user(
                session,
                settings.bootstrap_admin_name,
                settings.bootstrap_admin_email,
                settings.bootstrap_admin_password,
                role="admin",
                must_change_password=not settings.demo_mode,
            )

        defaults = {
            "club_name": "NO NAME",
            "primary_color": "#B91C1C",
            "secondary_color": "#111827",
            "report_subtitle": "No Name · Informe postpartido",
            "report_confidentiality": "Documento interno y confidencial",
            "pdf_default_mode": "executive",
            "require_report_approval": "true" if settings.require_report_approval else "false",
            "edition": "noname",
        }
        for key, value in defaults.items():
            current = repo.get_setting(session, key)
            if current is None:
                repo.set_setting(session, key, value)
            elif key == "club_name" and current in {"PostMatch Scout", "PostMatch Scout · Demo"}:
                # Upgrade legacy 2.x branding without creating any sporting data.
                repo.set_setting(session, key, "NO NAME")
            elif key == "report_subtitle" and current.startswith("PostMatch Scout"):
                repo.set_setting(session, key, value)
