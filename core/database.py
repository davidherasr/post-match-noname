from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from core.config import BASE_DIR, settings, validate_production_settings
from models import Base


@lru_cache(maxsize=1)
def get_engine():
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        future=True,
        connect_args=connect_args,
    )
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


@lru_cache(maxsize=1)
def init_db() -> None:
    validate_production_settings()
    alembic_ini = Path(BASE_DIR) / "alembic.ini"
    if settings.run_migrations and alembic_ini.exists():
        try:
            from alembic import command
            from alembic.config import Config
            cfg = Config(str(alembic_ini))
            cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
            command.upgrade(cfg, "head")
            return
        except Exception:
            if not settings.demo_mode:
                raise
    # Local demo/testing fallback only.
    Base.metadata.create_all(bind=get_engine())


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
