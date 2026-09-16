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
    # Home/Jornada ORM paths load these mapped entities.  The full mapped
    # column set is checked, not only fields introduced by recent migrations.
    "matches": {
        "id", "season_id", "competition_id", "round_name", "match_date",
        "window_start", "window_end", "kickoff_at", "schedule_status", "fixture_type",
        "home_team_id", "away_team_id", "home_score", "away_score", "venue",
        "home_formation", "away_formation", "video_available", "video_reference",
        "home_formation_known", "away_formation_known", "study_notes", "status",
        "report_due_at", "revision", "deleted_at", "is_test", "archived_previous_status", "created_by", "created_at", "updated_at",
    },
    "teams": {
        "id", "name", "short_name", "country", "logo_b64", "logo_mime",
        "is_own_team", "active", "is_test", "archived_at", "created_at", "updated_at",
    },
    "competitions": {"id", "name", "country", "active", "updated_at"},
    "seasons": {"id", "name", "start_date", "end_date", "active", "updated_at"},
    "player_season_decisions": {"current_level", "potential_score", "criteria_json"},
    "scout_observations": {"observation_level", "model_role_id", "legacy_review_id"},
    "users": {"deleted_at", "can_track_players"},
    "reports": {"own_team_rating", "rival_team_rating"},
    "staff_sporting_weights": {"user_id", "own_match_weight", "neutral_match_weight"},
    "match_opinions": {"match_id", "user_id", "home_team_rating", "away_team_rating", "summary"},
    "match_opinion_players": {"opinion_id", "player_id", "team_id", "rating", "note"},
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


def _configured_alembic_heads(cfg) -> set[str]:
    """Return the migration heads shipped with this release."""
    from alembic.script import ScriptDirectory

    return {str(value) for value in ScriptDirectory.from_config(cfg).get_heads()}


def _database_alembic_heads(connection) -> set[str]:
    """Read Alembic heads without invoking the migration runner.

    This is intentionally tiny and dialect-agnostic. 4.2.2 uses it to avoid
    re-entering Alembic on every Streamlit cold start when Supabase is already
    exactly at the release head.
    """
    inspector = inspect(connection)
    if "alembic_version" not in set(inspector.get_table_names()):
        return set()
    rows = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    return {str(value) for value in rows if value}


def _schema_is_release_ready(connection) -> bool:
    try:
        validate_schema_contract(connection)
        return True
    except DatabaseSchemaError:
        return False


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
        connection = None
        try:
            connection = engine.connect()
            connection.execute(text("SELECT 1"))
            return connection
        except OperationalError as exc:
            last = exc
            if connection is not None:
                connection.close()
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

            # 4.2.2 startup hotfix: 4.2.1 had no schema migration, but still
            # entered Alembic on every Streamlit cold start. On the production
            # Supabase/Python 3.14 stack this could surface an Alembic-internal
            # KeyError even though the database was already on 0012. If the
            # stored revision exactly matches the release head, validate the
            # physical schema and continue without invoking the migration runner.
            configured_heads = _configured_alembic_heads(cfg)
            database_heads = _database_alembic_heads(connection)
            if configured_heads and database_heads == configured_heads:
                validate_schema_contract(connection)
                return

            try:
                command.upgrade(cfg, "head")
            except KeyError:
                # Defensive recovery only when Alembic actually left the DB at
                # the shipped head *and* the physical contract is complete. We
                # never swallow a KeyError for a database that is still behind.
                database_heads = _database_alembic_heads(connection)
                if not (configured_heads and database_heads == configured_heads and _schema_is_release_ready(connection)):
                    raise

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
