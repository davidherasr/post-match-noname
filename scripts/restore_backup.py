from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import Date, DateTime, delete, func, inspect as sa_inspect, select

from core.database import init_db, session_scope
from models.entities import (
    AppSetting, AuditLog, Competition, ConsolidatedPlayerEvaluation, ConsolidatedReport,
    Document, FollowUp, FollowUpHistory, LoginAttempt, Match, Participation, Player,
    PlayerAlias, PlayerEvaluation, PlayerMergeLog, Report, ReportAssignment, ReportVersion,
    Season, Team, TeamRoster, User,
)

MODELS = [
    User, LoginAttempt, Season, Competition, Team, Player, PlayerAlias, PlayerMergeLog,
    TeamRoster, Match, Participation, ReportAssignment, Report, PlayerEvaluation,
    ReportVersion, Document, FollowUp, FollowUpHistory, ConsolidatedReport,
    ConsolidatedPlayerEvaluation, AppSetting, AuditLog,
]


def convert_row(model, row: dict) -> dict:
    columns = {c.key: c for c in sa_inspect(model).columns}
    converted = {}
    for key, value in row.items():
        if key not in columns or value is None:
            converted[key] = value
            continue
        column_type = columns[key].type
        if isinstance(column_type, DateTime) and isinstance(value, str):
            converted[key] = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        elif isinstance(column_type, Date) and isinstance(value, str):
            converted[key] = date.fromisoformat(value[:10])
        else:
            converted[key] = value
    return converted


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaurar una copia técnica de PostMatch Scout 2.0")
    parser.add_argument("file", type=Path, help="ZIP generado desde Administración")
    parser.add_argument("--replace", action="store_true", help="Vaciar las tablas antes de restaurar")
    args = parser.parse_args()
    if not args.file.exists():
        raise SystemExit("El archivo no existe.")
    with zipfile.ZipFile(args.file) as archive:
        payload = json.loads(archive.read("backup.json"))
    if payload.get("format") != "postmatch-scout-backup-v2":
        raise SystemExit("Formato de backup no reconocido.")
    init_db()
    with session_scope() as session:
        existing = int(session.scalar(select(func.count(User.id))) or 0)
        if existing and not args.replace:
            raise SystemExit("La base contiene datos. Usa --replace solo después de crear una copia de seguridad.")
        if args.replace:
            for model in reversed(MODELS):
                session.execute(delete(model))
            session.flush()
        tables = payload.get("tables", {})
        for model in MODELS:
            for row in tables.get(model.__tablename__, []):
                session.add(model(**convert_row(model, row)))
            session.flush()
    print("Restauración completada. Reinicia la aplicación y valida usuarios, informes y documentos.")


if __name__ == "__main__":
    main()
