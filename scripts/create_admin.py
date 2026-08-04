from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse

from core.database import init_db, session_scope
from repositories import scouting as repo


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear administrador de PostMatch Scout")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    init_db()
    with session_scope() as session:
        user = repo.create_user(session, args.name, args.email, args.password, role="admin")
    print(f"Administrador creado: {user.email}")


if __name__ == "__main__":
    main()
