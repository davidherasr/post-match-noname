from __future__ import annotations

import time
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from core.config import BASE_DIR, database_target, settings, validate_production_settings
from models import Base


class DatabaseUnavailableError(RuntimeError):
    """Raised when the configured database cannot be reached safely."""

    def __init__(self, message: str, *, original: Exception | None = None):
        super().__init__(message)
        self.original = original
        self.target = database_target()


class DatabaseSchemaError(RuntimeError):
    """Raised when Alembic revision and physical database schema disagree."""

    def __init__(self, message: str, *, missing: dict[str, list[str]] | None = None):
        super().__init__(message)
        self.missing = missing or {}


# Minimum physical schema required before any 4.x workspace is rendered.
# Keeping this contract explicit prevents an ORM SELECT from being the first
# place where a stale Supabase schema is discovered.
_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "matches": {
        "window_start", "window_end", "kickoff_at", "schedule_status", "fixture_type",
        "video_available", "video_reference", "home_formation_known",
        "away_formation_known", "study_notes",
    },
    "player_season_decisions": {"current_level", "potential_score", "criteria_json"},
    "scout_observations": {"observation_level", "model_role_id", "legacy_review_id"},
}


def validate_schema_contract(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    missing: dict[str, list[str]] = {}
    for table, required in _REQUIRED_COLUMNS.items():
        if table not in tables:
            missing[table] = ["<tabla completa>"]
            continue
        present = {column["name"] for column in inspector.get_columns(table)}
        absent = sorted(required - present)
        if absent:
            missing[table] = absent
    if missing:
        detail = "; ".join(f"{table}: {', '.join(cols)}" for table, cols in missing.items())
        raise DatabaseSchemaError(
            "La revisión Alembic y el esquema físico de la base de datos no coinciden. "
            f"Faltan elementos requeridos ({detail}).",
            missing=missing,
        )


@lru_cache(maxsize=1)
def get_engine():
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=900,
        pool_timeout=15,
        future=True,
        connect_args=connect_args,
    )
    from core.performance import register_engine_performance
    register_engine_performance(engine)
    if settings.database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    return engine


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, class_=Session)


def _connect_with_retry(attempts: int = 3, delay_seconds: float = 1.0):
    last: Exception | None = None
    engine = get_engine()
    for attempt in range(1, attempts + 1):
        try:
            connection = engine.connect()
            connection.execute(text("SELECT 1"))
            return connection
        except OperationalError as exc:
            last = exc
            if attempt < attempts:
                time.sleep(delay_seconds * attempt)
    target = database_target()
    host = target.get("host") or "host desconocido"
    raise DatabaseUnavailableError(
        f"No se puede conectar con la base de datos configurada ({host}).",
        original=last,
    ) from last


@lru_cache(maxsize=1)
def init_db() -> None:
    validate_production_settings()
    alembic_ini = Path(BASE_DIR) / "alembic.ini"

    if settings.run_migrations and alembic_ini.exists():
        connection = None
        try:
            # Reuse the same tested connection in Alembic. This avoids opening a
            # second PostgreSQL connection during cold starts and makes Supabase
            # pooler deployments considerably more reliable.
            connection = _connect_with_retry()
            from alembic import command
            from alembic.config import Config

            cfg = Config(str(alembic_ini))
            cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            # Critical 4.0.3 guard: Alembic's version table alone is not enough.
            # Verify the actual physical columns before any ORM workspace runs.
            validate_schema_contract(connection)
            return
        except (DatabaseUnavailableError, DatabaseSchemaError):
            raise
        except OperationalError as exc:
            target = database_target()
            host = target.get("host") or "host desconocido"
            raise DatabaseUnavailableError(
                f"La conexión con PostgreSQL se perdió al preparar la base de datos ({host}).",
                original=exc,
            ) from exc
        except Exception:
            if not settings.demo_mode:
                raise
        finally:
            if connection is not None:
                connection.close()

    # Local demo/testing fallback only. Production with migrations disabled is
    # read/validate-only: create_all must never silently mutate a real database.
    if settings.demo_mode:
        try:
            Base.metadata.create_all(bind=get_engine())
            with get_engine().connect() as connection:
                validate_schema_contract(connection)
            return
        except OperationalError as exc:
            target = database_target()
            raise DatabaseUnavailableError(
                f"No se puede inicializar la base de datos ({target.get('host') or 'host desconocido'}).",
                original=exc,
            ) from exc

    connection = _connect_with_retry()
    try:
        validate_schema_contract(connection)
    finally:
        connection.close()


@contextmanager
def session_scope():
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
