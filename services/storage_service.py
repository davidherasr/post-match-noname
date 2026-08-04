from __future__ import annotations

import hashlib
from pathlib import Path

from core.config import settings


def _client():
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    from supabase import create_client
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def save_pdf(report_id: int, version: int, content: bytes, document_type: str = "full") -> dict[str, object | None]:
    checksum = hashlib.sha256(content).hexdigest()
    filename = f"informe_{report_id}_v{version}_{document_type}.pdf"
    reports_dir = settings.local_storage_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    local_path = reports_dir / filename
    local_path.write_bytes(content)

    result: dict[str, object | None] = {
        "storage_bucket": None,
        "storage_path": None,
        "local_path": str(local_path),
        "checksum": checksum,
        "size_bytes": len(content),
        "storage_status": "local_only",
        "error_message": None,
    }
    client = _client()
    if not client:
        return result
    remote_path = f"reports/{report_id}/v{version}/{filename}"
    try:
        try:
            client.storage.create_bucket(settings.supabase_bucket, options={"public": False})
        except Exception:
            pass
        client.storage.from_(settings.supabase_bucket).upload(
            remote_path,
            content,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        result.update({
            "storage_bucket": settings.supabase_bucket,
            "storage_path": remote_path,
            "storage_status": "stored_remote",
        })
    except Exception as exc:
        result.update({"storage_status": "remote_failed", "error_message": str(exc)})
    return result


def signed_download_url(bucket: str, storage_path: str, expires_in: int = 900) -> str | None:
    client = _client()
    if not client:
        return None
    signed = client.storage.from_(bucket).create_signed_url(storage_path, expires_in)
    return signed.get("signedURL") or signed.get("signedUrl")


def load_document_bytes(*, bucket: str | None, storage_path: str | None, local_path: str | None) -> bytes:
    if bucket and storage_path:
        client = _client()
        if client:
            return client.storage.from_(bucket).download(storage_path)
    if local_path and Path(local_path).exists():
        return Path(local_path).read_bytes()
    raise FileNotFoundError("El documento no está disponible en Storage ni en el almacenamiento local.")


def retry_remote_storage(report_id: int, version: int, document_type: str, *, local_path: str | None) -> dict[str, object | None]:
    """Retry a failed upload using the immutable local copy."""
    if not local_path or not Path(local_path).exists():
        raise FileNotFoundError("No existe una copia local para reintentar la subida.")
    return save_pdf(report_id, version, Path(local_path).read_bytes(), document_type=document_type)
