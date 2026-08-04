from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_NAME = "PostMatch Scout"
APP_VERSION = "2.0"
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
    raw = str(env("DATABASE_URL", "")).strip()
    if not raw:
        return f"sqlite:///{BASE_DIR / 'postmatch_scout.db'}"
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
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


def validate_production_settings() -> None:
    if settings.demo_mode:
        return
    if not str(env("BOOTSTRAP_ADMIN_PASSWORD", "")).strip():
        raise RuntimeError("Define BOOTSTRAP_ADMIN_PASSWORD antes del primer despliegue.")
    if settings.bootstrap_admin_password in {"Admin123!", "DemoAdmin2026!"}:
        raise RuntimeError("La contraseña administrativa predeterminada no está permitida en producción.")
