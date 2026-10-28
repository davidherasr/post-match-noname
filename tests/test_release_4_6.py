"""4.6: consultation first; no fake appearance from a roster; feed permissions."""
from __future__ import annotations
from pathlib import Path
from sqlalchemy import select, func
from models.entities import Participation, PlayerEvaluation, PlayerSeasonDecision
from repositories import staff_feed, report_roster, reports
from repositories import planning as planning_repo
from repositories import scouting as repo
from test_release_4_5 import seed, player, contribution


def test_staff_feed_excludes_drafts_and_includes_only_delivered(session_factory):
    with session_factory.begin() as s:
        admin, reporter, _, season, _, own, rival, _, m = seed(s)
        report = contribution(s, m, reporter, own_score=6)
        assert not any(e['kind']=='report' for e in staff_feed.load_activity(s, season_id=season.id, roles={'reporter'}))
        reports.submit_report(s, report.id, reporter.id)
        rows = staff_feed.load_activity(s, season_id=season.id, roles={'reporter'})
        assert any(e['kind']=='report' and e['match_id']==m.id and 'Observador 1' in e['detail'] for e in rows)


def test_dd_player_decision_visible_without_private_notes(session_factory):
    with session_factory.begin() as s:
        admin, reporter, _, season, _, own, rival, _, m = seed(s)
        target = player(s, admin, rival, season, 'Futbolista objetivo de prueba')
        planning_repo.upsert_season_decision(s, actor_id=admin.id, season_id=season.id,
            player_id=target.id, status='Interesante', priority=2,
            director_note='NO MOSTRAR ESTA NOTA PRIVADA')
        visible = staff_feed.load_activity(s, season_id=season.id, roles={'reporter'})
        entry = next(e for e in visible if e.get('player_id')==target.id)
        assert 'Interesante' in entry['title']
        assert 'Futbolista objetivo de prueba' in entry['detail']
        assert 'NO MOSTRAR' not in repr(visible)


def test_staff_feed_does_not_display_discarded_to_reporters(session_factory):
    with session_factory.begin() as s:
        admin, reporter, _, season, _, own, rival, _, m = seed(s)
        target = player(s, admin, rival, season, 'No seleccionar')
        planning_repo.upsert_season_decision(s, actor_id=admin.id, season_id=season.id,
            player_id=target.id, status='Descartado', priority=3)
        normal = staff_feed.load_activity(s, season_id=season.id, roles={'reporter'})
        director = staff_feed.load_activity(s, season_id=season.id, roles={'director'})
        assert not any(e.get('player_id')==target.id for e in normal)
        assert any(e.get('player_id')==target.id for e in director)


def test_season_roster_choice_does_not_invent_match_participation(session_factory):
    with session_factory.begin() as s:
        admin, reporter, _, season, _, own, rival, _, m = seed(s)
        known = player(s, admin, own, season, 'Jugador de la plantilla')
        before = s.scalar(select(func.count(Participation.id)))
        choices, unconfirmed = report_roster.optional_player_choices(s,
             season_id=season.id, team_id=own.id, confirmed=[])
        assert unconfirmed and [x.player_id for x in choices] == [known.id]
        assert choices[0].id is None and choices[0].starter is None
        report = reports.get_or_create_report(s, m.id, reporter.id)
        e = reports.upsert_evaluation(s, report.id, known.id, own.id, None,
            actor_id=reporter.id, observation_status='observed', highlight_rank=1)
        assert e.participation_id is None
        assert s.scalar(select(func.count(Participation.id))) == before
        reports.submit_report(s, report.id, reporter.id)


def test_confirmed_participations_take_priority_over_roster(session_factory):
    with session_factory.begin() as s:
        admin, reporter, _, season, _, own, rival, _, m = seed(s)
        chosen = player(s, admin, own, season, 'Jugador XI')
        only = [object()]
        values, fallback = report_roster.optional_player_choices(s, season_id=season.id,
                             team_id=own.id, confirmed=only)
        assert values == only and not fallback


def test_role_home_and_full_report_contract():
    root=Path(__file__).resolve().parents[1]
    home=(root/'views/home.py').read_text()
    reports_view=(root/'views/reports.py').read_text()
    assert 'staff_feed.load_activity' in home
    assert 'Novedades del cuerpo técnico' in home
    assert 'Aportar una lectura (voluntario)' in home
    assert "if roles == {'reporter'}" not in home
    assert 'include_rival=mode !=' in reports_view
    assert 'no hay participaciones confirmadas' in reports_view.lower()
    assert 'report_roster.optional_player_choices' in reports_view
