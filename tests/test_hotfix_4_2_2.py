from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, text

from models import Base
import core.database as database

ROOT = Path(__file__).resolve().parents[1]
HEAD = "0013_data_governance_4_2_3"


def _reset_database_caches() -> None:
    database.init_db.cache_clear()
    database.get_session_factory.cache_clear()
    engine = database.get_engine.cache_info()
    # cache_info() is intentionally touched before clear so accidental API changes
    # are caught by this test without depending on private functools internals.
    assert engine.maxsize == 1
    database.get_engine.cache_clear()


def test_release_422_versions_and_head_are_consistent():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.4"
    assert 'APP_VERSION = "4.4"' in (ROOT / "core/config.py").read_text(encoding="utf-8")
    assert 'REPORTS_PAGE_API_VERSION = "4.4"' in (ROOT / "views/reports.py").read_text(encoding="utf-8")
    consistency = (ROOT / "scripts/check_release_consistency.py").read_text(encoding="utf-8")
    assert 'EXPECTED = "4.4"' in consistency
    assert f'HEAD_MIGRATION = "{HEAD}"' in consistency


def test_startup_skips_alembic_runner_when_database_is_already_at_head(tmp_path, monkeypatch):
    db_path = tmp_path / "already_at_head.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL PRIMARY KEY)"))
        connection.execute(text("INSERT INTO alembic_version(version_num) VALUES (:head)"), {"head": HEAD})

    monkeypatch.setattr(
        database,
        "settings",
        SimpleNamespace(database_url=url, run_migrations=True, demo_mode=False),
    )
    monkeypatch.setattr(database, "validate_production_settings", lambda: None)
    monkeypatch.setattr(database, "get_engine", lambda: engine)

    import alembic.command

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("Alembic upgrade must not run when DB is already at release head")

    monkeypatch.setattr(alembic.command, "upgrade", should_not_run)
    database.init_db.cache_clear()
    try:
        database.init_db()
    finally:
        database.init_db.cache_clear()
        engine.dispose()


def test_startup_error_screen_reports_exact_phase():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"migraciones / validación de esquema"' in app_source
    assert '"bootstrap técnico"' in app_source
    assert '"carga de ajustes"' in app_source
    assert 'logging.getLogger("noname.startup")' in app_source
