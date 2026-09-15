from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[1]


def test_403_release_contract_and_repair_migration_present():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.2.1"
    assert 'APP_VERSION = "4.2.1"' in (ROOT / "core/config.py").read_text(encoding="utf-8")
    assert (ROOT / "alembic/versions/0010_core_workspace_schema_repair_4_0_4.py").exists()
    assert 'HEAD_MIGRATION = "0012_sporting_reading_4_2"' in (ROOT / "scripts/check_release_consistency.py").read_text(encoding="utf-8")


def test_schema_contract_is_checked_before_workspaces_render():
    source = (ROOT / "core/database.py").read_text(encoding="utf-8")
    assert "validate_schema_contract(connection)" in source
    assert "DatabaseSchemaError" in source
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "except DatabaseSchemaError" in app


def test_upgrade_repairs_database_stamped_0008_but_missing_physical_columns(tmp_path):
    db = tmp_path / "broken_0008.sqlite"
    url = f"sqlite:///{db}"
    engine = create_engine(url, future=True)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE matches (
                id INTEGER PRIMARY KEY,
                season_id INTEGER NOT NULL,
                match_date DATE NOT NULL,
                home_formation VARCHAR(40),
                away_formation VARCHAR(40)
            )
        """))
        conn.execute(text("""
            INSERT INTO matches (id, season_id, match_date, home_formation, away_formation)
            VALUES (1, 1, '2026-09-13', '4-3-3', NULL)
        """))
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version(version_num) VALUES ('0008_match_study_4_0')"))
    engine.dispose()

    env = os.environ.copy()
    env["DATABASE_URL"] = url
    env["DEMO_MODE"] = "true"
    env["RUN_MIGRATIONS"] = "true"
    code = """
from alembic import command
from alembic.config import Config
cfg = Config('alembic.ini')
command.upgrade(cfg, 'head')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    engine = create_engine(url, future=True)
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("matches")}
    assert {
        "window_start", "window_end", "kickoff_at", "schedule_status", "fixture_type",
        "video_available", "video_reference", "home_formation_known",
        "away_formation_known", "study_notes",
    }.issubset(columns)
    with engine.connect() as conn:
        version = conn.scalar(text("SELECT version_num FROM alembic_version"))
        row = conn.execute(text(
            "SELECT window_start, window_end, home_formation_known, away_formation_known "
            "FROM matches WHERE id=1"
        )).first()
    engine.dispose()
    assert version == "0012_sporting_reading_4_2"
    assert str(row[0]) == "2026-09-13"
    assert str(row[1]) == "2026-09-13"
    assert bool(row[2]) is True
    assert bool(row[3]) is False
