from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

APP_NAME = "No Name PostMatch"
APP_VERSION = "4.1.2"
BASE_DIR = Path(__file__).resolve().parents[1]


def _streamlit_secret(name: str) -> Any | None:
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        return None
    return None


def env(name: str, default: Any = None) -> Any:
    value = _streamlit_secret(name)
    return value if value is not None else os.getenv(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name, str(default))
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def normalized_database_url() -> str:
    """Return a SQLAlchemy-safe URL without changing the target database.

    Production deployments historically supplied a plain Supabase PostgreSQL URL.
    For Supabase hosts we enforce TLS and a finite connection timeout.  Parsing and
    re-rendering through SQLAlchemy also safely preserves percent-escaped passwords.
    """
    raw = str(env("DATABASE_URL", "")).strip()
    if not raw:
        return f"sqlite:///{BASE_DIR / 'postmatch_scout.db'}"
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]

    if raw.startswith("postgresql://") or raw.startswith("postgresql+"):
        try:
            url = make_url(raw)
            query = dict(url.query)
            host = (url.host or "").lower()
            if "supabase" in host:
                query.setdefault("sslmode", "require")
            query.setdefault("connect_timeout", "10")
            raw = url.set(query=query).render_as_string(hide_password=False)
        except Exception:
            # Validation below will produce a clear startup message if malformed.
            pass
    return raw


@dataclass(frozen=True)
class Settings:
    database_url: str = normalized_database_url()
    demo_mode: bool = env_bool("DEMO_MODE", not bool(str(env("DATABASE_URL", "")).strip()))
    bootstrap_admin_email: str = str(env("BOOTSTRAP_ADMIN_EMAIL", "admin@postmatch.local"))
    bootstrap_admin_password: str = str(env("BOOTSTRAP_ADMIN_PASSWORD", "DemoAdmin2026!"))
    bootstrap_admin_name: str = str(env("BOOTSTRAP_ADMIN_NAME", "Administrador"))
    supabase_url: str = str(env("SUPABASE_URL", ""))
    supabase_service_role_key: str = str(env("SUPABASE_SERVICE_ROLE_KEY", ""))
    supabase_bucket: str = str(env("SUPABASE_BUCKET", "postmatch-reports"))
    local_storage_dir: Path = Path(str(env("LOCAL_STORAGE_DIR", BASE_DIR / "storage")))
    login_max_attempts: int = int(env("LOGIN_MAX_ATTEMPTS", 5))
    login_lock_minutes: int = int(env("LOGIN_LOCK_MINUTES", 15))
    require_report_approval: bool = env_bool("REQUIRE_REPORT_APPROVAL", True)
    run_migrations: bool = env_bool("RUN_MIGRATIONS", True)


settings = Settings()


def database_target() -> dict[str, str | int | bool | None]:
    """Return non-secret connection metadata for diagnostics."""
    try:
        url = make_url(settings.database_url)
        host = url.host
        return {
            "driver": url.drivername,
            "host": host,
            "port": url.port,
            "database": url.database,
            "is_supabase": bool(host and "supabase" in host.lower()),
            "is_direct_supabase": bool(host and host.lower().startswith("db.") and host.lower().endswith(".supabase.co")),
        }
    except Exception:
        return {"driver": "desconocido", "host": None, "port": None, "database": None, "is_supabase": False, "is_direct_supabase": False}


def validate_production_settings() -> None:
    if settings.demo_mode:
        return
    raw_db = str(env("DATABASE_URL", "")).strip()
    if not raw_db:
        raise RuntimeError("Falta DATABASE_URL en los Secrets de Streamlit Cloud.")
    try:
        url = make_url(settings.database_url)
    except Exception as exc:
        raise RuntimeError("DATABASE_URL no tiene un formato PostgreSQL válido.") from exc
    if not url.host or not url.database:
        raise RuntimeError("DATABASE_URL está incompleta: falta host o base de datos.")
    if any(token in raw_db for token in ("PROJECT_REF", "PASSWORD", "REGION")):
        raise RuntimeError("DATABASE_URL todavía contiene valores de ejemplo (PROJECT_REF/PASSWORD/REGION).")
    if not str(env("BOOTSTRAP_ADMIN_PASSWORD", "")).strip():
        raise RuntimeError("Define BOOTSTRAP_ADMIN_PASSWORD antes del primer despliegue.")
    if settings.bootstrap_admin_password in {"Admin123!", "DemoAdmin2026!"}:
        raise RuntimeError("La contraseña administrativa predeterminada no está permitida en producción.")
