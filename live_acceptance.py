from __future__ import annotations

"""Run the critical workflow against the configured DATABASE_URL and roll it back.

Usage in Codespaces/terminal after deployment secrets are available:
    python scripts/live_acceptance.py --admin-email you@example.com

No sports test data is persisted: the workflow runs inside a SAVEPOINT that is rolled back.
"""

import argparse
import json

from sqlalchemy import select

from core.database import get_session_factory, init_db
from models.entities import User
from services.health_service import database_probe, live_acceptance_rollback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-email", required=True)
    args = parser.parse_args()
    init_db()
    session = get_session_factory()()
    try:
        admin = session.scalar(select(User).where(User.email == args.admin_email.strip().lower(), User.active.is_(True)))
        if not admin or admin.role != "admin":
            raise SystemExit("No se ha encontrado un administrador activo con ese correo.")
        print(json.dumps({"database_probe": database_probe(session)}, ensure_ascii=False, default=str, indent=2))
        print(json.dumps({"workflow": live_acceptance_rollback(session, admin.id)}, ensure_ascii=False, default=str, indent=2))
        session.rollback()
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
