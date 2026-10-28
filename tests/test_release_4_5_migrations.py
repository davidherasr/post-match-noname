"""4.5.1 schema is additive and safely upgrades a populated 0015 database."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from core.database import validate_schema_contract

ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_from_populated_0015_preserves_historical_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'noname_upgrade.db'}")
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    with engine.connect() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0015_observation_requests_4_4_3")
        conn.commit()
        conn.execute(text("INSERT INTO seasons (id,name,active,updated_at) VALUES (9745, 'Temporada histórica', 1, '2026-09-01')"))
        conn.commit()
        command.upgrade(cfg, "head")
        conn.commit()
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0017_lowlight_compact_4_5_1"
        assert conn.scalar(text("SELECT name FROM seasons WHERE id=9745")) == "Temporada histórica"
        validate_schema_contract(conn)
        old = conn.scalar(text("SELECT count(*) FROM seasons"))
        command.upgrade(cfg, "head")
        assert conn.scalar(text("SELECT count(*) FROM seasons")) == old
        assert conn.scalar(text("SELECT name FROM seasons WHERE id=9745")) == "Temporada histórica"
    engine.dispose()


def test_fresh_database_migrates_through_0017(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'noname_fresh.db'}")
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    with engine.connect() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        conn.commit()
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0017_lowlight_compact_4_5_1"
        validate_schema_contract(conn)
        assert "unidentified_player_signals" in inspect(conn).get_table_names()
    engine.dispose()
