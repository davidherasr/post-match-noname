"""Comprobación SOLO LECTURA del esquema PostgreSQL o de un listado exportado.

Ejemplos:
  python scripts/diagnosticar_esquema_4511.py --export docs/ESQUEMA_PUBLIC_RECIBIDO_2026_10_28.txt
  DATABASE_URL='...' python scripts/diagnosticar_esquema_4511.py --live

--live no llama a init_db, create_all ni Alembic. No muestra contraseñas.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.schema_diagnostics import describe_public_schema, parse_public_manifest


def _read_live() -> tuple[dict[str, set[str]], list[str]]:
    from sqlalchemy import create_engine, inspect, text
    from core.config import database_target, settings
    if not settings.database_url.startswith("postgresql"):
        raise RuntimeError("--live solo admite PostgreSQL; configura DATABASE_URL con Session pooler.")
    engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={})
    try:
        with engine.connect() as conn:
            # Inspector metadata and Alembic HEAD only; no migration or DDL.
            inspector = inspect(conn)
            names = inspector.get_table_names(schema="public")
            actual = {name: {row["name"] for row in inspector.get_columns(name, schema="public")}
                      for name in names}
            revisions = []
            if "alembic_version" in actual:
                revisions = [str(row) for row in conn.execute(
                    text("SELECT version_num FROM public.alembic_version")
                ).scalars().all()]
            return actual, revisions
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--export', type=Path, help='Listado de tablas y columnas de public')
    choice.add_argument('--live', action='store_true', help='Comprobación PostgreSQL SOLO LECTURA')
    args = parser.parse_args()
    if args.live:
        actual, versions = _read_live()
    else:
        actual = parse_public_manifest(args.export.read_text(encoding='utf-8'))
        versions = None
    result = describe_public_schema(actual)
    result['alembic_version'] = versions  # None = no figura en el listado, no es revision vacía
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result['schema_matches_orm'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
