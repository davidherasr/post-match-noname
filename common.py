from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy.orm import Session

from core.utils import json_dumps
from models.entities import AuditLog

UTC_NOW = lambda: datetime.now(timezone.utc).replace(tzinfo=None)
FINAL_REPORT_STATUSES = {"approved", "final", "incorporated"}
LOCKED_REPORT_STATUSES = {"submitted", "approved", "final", "incorporated"}

def _snapshot(obj, fields: Sequence[str]) -> dict:
    return {field: getattr(obj, field, None) for field in fields}


def audit(
    session: Session,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    detail: str | None = None,
    before: object | None = None,
    after: object | None = None,
) -> None:
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
            before_json=json_dumps(before) if before is not None else None,
            after_json=json_dumps(after) if after is not None else None,
        )
    )
