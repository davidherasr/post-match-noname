from __future__ import annotations

from sqlalchemy.orm import Session

from reports.payload import build_report_payload, report_filename
from reports.summary_pdf import generate_summary_pdf
from reports.full_pdf import generate_full_pdf


def generate_report_pdf(session: Session, report_id: int, *, version: int | None = None, mode: str = "full") -> bytes:
    if mode not in {"executive", "full"}:
        raise ValueError("Modo PDF no válido.")
    payload = build_report_payload(session, report_id, version=version)
    current_version = version or payload["report"].version
    if mode == "executive":
        return generate_summary_pdf(payload, current_version=current_version)
    return generate_full_pdf(payload, current_version=current_version)

__all__ = ["build_report_payload", "report_filename", "generate_report_pdf"]
