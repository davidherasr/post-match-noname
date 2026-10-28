"""4.5.1.1: exact public schema received 28 Oct and real 4.4.4.1 fixture upgrade."""
from __future__ import annotations

import gzip
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from core.database import validate_schema_contract
from core.schema_diagnostics import describe_public_schema, parse_public_manifest

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / 'docs/ESQUEMA_PUBLIC_RECIBIDO_2026_10_28.txt'
LEGACY_DUMP = ROOT / 'tests/fixtures/legacy_0015_43tablas_461campos.sql.gz'


def test_4511_manifest_exact_missing_elements():
    actual = parse_public_manifest(EXPORT.read_text(encoding='utf-8'))
    result = describe_public_schema(actual)
    assert (result['tables'], result['columns']) == (43, 461)
    assert (result['expected_tables'], result['expected_columns']) == (44, 488)
    assert result['matches_4441_public_shape'] is True
    assert result['missing_tables'] == ['unidentified_player_signals']
    assert result['extra_tables'] == [] and result['extra_columns'] == {}
    assert result['schema_matches_orm'] is False


def test_4511_legacy_actual_4441_schema_migrates_without_losing_data(tmp_path):
    db = tmp_path / 'produccion_simulada_desde_4441.sqlite'
    with sqlite3.connect(db) as conn:
        conn.executescript(gzip.open(LEGACY_DUMP, 'rt', encoding='utf-8').read())
        columns = {name: {row[1] for row in conn.execute(f'PRAGMA table_info("{name}")')}
                   for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        assert len(columns) == 43 and sum(map(len, columns.values())) == 461
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0015_observation_requests_4_4_3'
        original = conn.execute('SELECT id, general_rating, standout FROM player_evaluations WHERE id=901').fetchone()
        assert original == (901, 8.0, 1)
    engine = create_engine(f'sqlite:///{db}')
    cfg = Config(str(ROOT / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'alembic'))
    with engine.connect() as conn:
        cfg.attributes['connection'] = conn
        command.upgrade(cfg, 'head')
        conn.commit()
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        assert len(tables) == 44
        assert sum(len(inspector.get_columns(t)) for t in tables) == 488
        assert conn.scalar(text('SELECT version_num FROM alembic_version')) == '0017_lowlight_compact_4_5_1'
        assert conn.execute(text('SELECT id,general_rating,standout,lowlight_rank,highlight_rank FROM player_evaluations WHERE id=901')).one() == (901,8.0,1,None,None)
        assert conn.scalar(text('SELECT own_team_rating FROM reports WHERE id=901')) == 7.5
        assert conn.scalar(text('SELECT COUNT(*) FROM matches')) == 1
        assert conn.scalar(text('SELECT COUNT(*) FROM users')) == 1
        assert conn.scalar(text('SELECT COUNT(*) FROM players')) == 1
        validate_schema_contract(conn)
    engine.dispose()


def test_4511_manifest_does_not_claim_alembic_head_from_shape():
    # The export contains only column TYPES, never version_num row contents.
    actual = parse_public_manifest(EXPORT.read_text(encoding='utf-8'))
    assert len(actual['alembic_version']) == 1
    assert 'version_num' in actual['alembic_version']
    assert '0015_observation_requests_4_4_3' not in EXPORT.read_text(encoding='utf-8')


def test_4511_cli_only_reads_schema():
    source = (ROOT / 'scripts/diagnosticar_esquema_4511.py').read_text(encoding='utf-8')
    assert 'command.upgrade' not in source and 'init_db()' not in source
    assert 'CREATE TABLE' not in source and 'supabase_migrations.schema_migrations' not in source
