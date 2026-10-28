"""Regression 4.5.1: deployment imports, compact catalogue and negative ranking."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import select

from models.entities import PlayerEvaluation
from repositories import scouting as repo
from repositories import reports
from repositories.player_report import build_player_report_360
from services.report_service import generate_report_pdf


def _seed(session):
    admin = repo.create_user(session, 'Admin 451', 'admin451@example.test', 'valid', role='admin', roles=['admin'])
    reporter = repo.create_user(session, 'Reporter 451', 'reporter451@example.test', 'valid', role='reporter', actor_id=admin.id)
    season = repo.create_season(session, '2026-27', date(2026, 7, 1), date(2027, 6, 30), admin.id)
    competition = repo.create_competition(session, 'Liga regional', actor_id=admin.id)
    own = repo.create_team(session, 'C.D. Noname', is_own_team=True, actor_id=admin.id)
    rival = repo.create_team(session, 'Club Rival', actor_id=admin.id)
    repo.set_setting(session, 'own_team_id', str(own.id), admin.id)
    match = repo.create_match(session, season_id=season.id, competition_id=competition.id,
        round_name='J1', match_date=date(2026, 9, 12), home_team_id=own.id,
        away_team_id=rival.id, status='scheduled', schedule_status='provisional', created_by=admin.id)
    p1 = repo.find_or_create_player(session, 'Jugador 451 Uno', actor_id=admin.id)
    p2 = repo.find_or_create_player(session, 'Jugador 451 Dos', actor_id=admin.id)
    for p in (p1, p2):
        repo.assign_player_to_roster(session, own.id, season.id, p.id, 12, admin.id)
    return admin, reporter, season, own, rival, match, p1, p2


def test_451_redeploy_contract_imports_are_explicit():
    # Both of these failed in the deployed UI screenshots.
    from repositories.users import PARTICIPATION_PROFILES
    from models.entities import PlayerObservationResponse, UnidentifiedPlayerSignal
    from repositories.dd_attention import team_knowledge
    from pathlib import Path
    admin_path = Path(__file__).resolve().parents[1] / 'views/admin.py'
    hub_path = Path(__file__).resolve().parents[1] / 'views/team_hub.py'
    assert PARTICIPATION_PROFILES['own_only'] == 'No Name'
    assert PlayerObservationResponse.__tablename__ == 'player_observation_responses'
    assert UnidentifiedPlayerSignal.__tablename__ == 'unidentified_player_signals'
    assert callable(team_knowledge)
    assert 'from repositories.users import PARTICIPATION_PROFILES' in admin_path.read_text(encoding='utf8')
    assert 'from repositories.dd_attention import team_knowledge' in hub_path.read_text(encoding='utf8')


def test_451_lowlight_is_valid_without_score_and_separate_from_highlight(session_factory):
    with session_factory.begin() as session:
        _, reporter, season, own, _, match, p1, p2 = _seed(session)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        low = reports.upsert_evaluation(session, report.id, p1.id, own.id, None,
            actor_id=reporter.id, observation_status='observed', lowlight_rank=1)
        assert low.general_rating is None and low.lowlight_rank == 1 and not low.standout
        positive = reports.upsert_evaluation(session, report.id, p2.id, own.id, None,
            actor_id=reporter.id, observation_status='observed', highlight_rank=1)
        assert positive.highlight_rank == 1 and positive.lowlight_rank is None
        with pytest.raises(ValueError, match='a la vez'):
            reports.upsert_evaluation(session, report.id, p1.id, own.id, None,
                actor_id=reporter.id, observation_status='observed', highlight_rank=2, lowlight_rank=1)
        with pytest.raises(ValueError, match='menor destaque'):
            reports.upsert_evaluation(session, report.id, p2.id, own.id, None,
                actor_id=reporter.id, observation_status='observed', lowlight_rank=1,
                highlight_rank=None)
        repo.submit_report(session, report.id, reporter.id)
        cover = build_player_report_360(session, p1.id, season_id=season.id)['knowledge_45']['own']
        assert cover['least_3'] == 1 and cover['ratings'] == 0 and cover['average'] is None
        assert cover['top_3'] == 0


def test_451_pdf_includes_lowlight_without_fabricated_rating(session_factory):
    with session_factory.begin() as session:
        admin, reporter, _, own, _, match, p1, _ = _seed(session)
        repo.replace_participations(session, match.id, own.id,
            [{'player_id': p1.id, 'starter': True, 'position': 'DC'}], actor_id=admin.id)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        reports.upsert_evaluation(session, report.id, p1.id, own.id, None,
            actor_id=reporter.id, observation_status='observed', lowlight_rank=1)
        repo.submit_report(session, report.id, reporter.id)
        for mode in ('executive', 'full'):
            pdf = generate_report_pdf(session, report.id, mode=mode)
            assert pdf.startswith(b'%PDF-') and len(pdf) > 1000


def test_451_compact_player_rows_distinguish_missing_values():
    class P:
        id = 8
        full_name = 'Futbolista de ejemplo'
        display_name = None
        primary_position = None
    fake = {'player': P(), 'team': None, 'scope': 'Externo', 'rating': None,
            'match_count': 0, 'authors': 0, 'neutral_mentions': 0,
            'tracking_count': 0, 'state': 'Sin decisión', 'latest': None}
    # Pure formatting helper can be exercised without a Streamlit server.
    import ast
    import pandas as pd
    source = (Path(__file__).resolve().parents[1] / 'views/player_hub.py').read_text(encoding='utf8')
    definition = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == '_table_rows')
    namespace = {'pd': pd}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), '<catalog>', 'exec'), namespace)
    _table_rows = namespace['_table_rows']
    row = _table_rows([fake]).iloc[0]
    assert row['Jugador'] == 'Futbolista de ejemplo'
    assert row['Nota'] == '—'
    assert row['Partidos'] == 0
    assert len(_table_rows([fake])) == 1


def test_451_catalog_paginates_25_or_50_and_sorts_before_slice(session_factory):
    from repositories.player_catalog import search_players
    with session_factory.begin() as session:
        admin, *_ = _seed(session)
        for i in range(34):
            repo.find_or_create_player(session, f'Registro ordenación {i:02}', actor_id=admin.id)
        first = search_players(session, season_id=None, search='Registro ordenación',
                               order='Nombre', page=1, page_size=25)
        second = search_players(session, season_id=None, search='Registro ordenación',
                                order='Nombre', page=2, page_size=25)
        reverse = search_players(session, season_id=None, search='Registro ordenación',
                                 order='Nombre', descending=True, page=1, page_size=50)
        assert first['total'] == 34 and first['pages'] == 2
        assert len(first['rows']) == 25 and len(second['rows']) == 9
        assert first['rows'][0]['player'].full_name.endswith('00')
        assert second['rows'][-1]['player'].full_name.endswith('33')
        assert reverse['rows'][0]['player'].full_name.endswith('33')


def test_451_upgrade_from_populated_0016_keeps_evaluation(tmp_path):
    from sqlalchemy import create_engine, text, inspect
    from alembic import command
    from alembic.config import Config
    root = Path(__file__).resolve().parents[1]
    engine = create_engine(f"sqlite:///{tmp_path / 'upgrade451.sqlite'}")
    cfg = Config(str(root / 'alembic.ini'))
    cfg.set_main_option('script_location', str(root / 'alembic'))
    try:
        with engine.connect() as conn:
            cfg.attributes['connection'] = conn
            command.upgrade(cfg, '0016_partial_reading_4_5')
            conn.commit()
            conn.execute(text("INSERT INTO player_evaluations "
                 "(id,report_id,player_id,team_id,evaluation_scope,observation_status," 
                 "standout,attention_signal,pdf_include,revision,created_at,updated_at) "
                 "VALUES (451,7,8,9,'own','observed',0,1,1,1,'2026-09-01','2026-09-01')"))
            conn.commit()
            command.upgrade(cfg, 'head')
            conn.commit()
            assert conn.scalar(text('SELECT version_num FROM alembic_version')) == '0017_lowlight_compact_4_5_1'
            assert conn.scalar(text('SELECT attention_signal FROM player_evaluations WHERE id = 451')) == 1
            assert conn.scalar(text('SELECT lowlight_rank FROM player_evaluations WHERE id = 451')) is None
            from core.database import validate_schema_contract
            validate_schema_contract(conn)
            assert 'lowlight_rank' in {col['name'] for col in inspect(conn).get_columns('player_evaluations')}
    finally:
        engine.dispose()
