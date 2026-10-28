"""4.7.4 regression/acceptance: security, retract, substitutes, metrics, merge, aggregate."""
from pathlib import Path
import json
import pytest
from sqlalchemy import select, func

from test_release_4_5 import seed, player
from test_release_4_7_3 import published
from models.entities import Player, SportingContribution47 as Contribution, Participation
from repositories import mobile472 as board, publication473 as pub, player_metrics474 as metrics
from repositories import rating_summary474 as summaries, players as players_repo

ROOT=Path(__file__).resolve().parents[1]


def test_consult_role_cannot_save_even_with_valid_fixture(session_factory):
    with session_factory.begin() as s:
        admin,scout,_,_,_,own,away,_,m=seed(s,profile='viewer')
        published(s,admin,m)
        key=board.choices(s,m.id,own.id)[0][0]['key']
        with pytest.raises(PermissionError,match='Consulta'):
            board.save_board(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                             payload={'players':[{'key':key,'score':7}]})
        assert not s.scalar(select(Contribution.id).limit(1))


def test_remove_grade_updates_canonical_summary_and_can_restore(session_factory):
    with session_factory.begin() as s:
        admin,scout,_,season,_,own,away,_,m=seed(s,profile='full')
        published(s,admin,m)
        first=board.choices(s,m.id,own.id)[0][0]
        pid=first['player_id'];key=first['key']
        grade=lambda score:board.save_board(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                                             payload={'players':[{'key':key,'score':score}]})
        grade(8)
        assert summaries.summary_for(summaries.observations(s,actor_id=admin.id,
                      season_id=season.id,player_ids=[pid]),pid)['opinions']==1
        removed=board.save_board(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                                 payload={'players':[],'cleared':[key]})
        assert removed['retiradas']==1
        assert board.existing(s,author_id=scout.id,match_id=m.id)[1]=={}
        assert summaries.summary_for(summaries.observations(s,actor_id=admin.id,
                      season_id=season.id,player_ids=[pid]),pid)['opinions']==0
        grade(9)
        assert summaries.summary_for(summaries.observations(s,actor_id=admin.id,
                      season_id=season.id,player_ids=[pid]),pid)['opinions']==1
        rows=s.scalars(select(Contribution).where(Contribution.kind=='individual')).all()
        assert len(rows)==2 and sorted(r.status for r in rows)==['retracted','shared']


def test_confirmed_substitute_added_after_publish_can_be_rated(session_factory):
    with session_factory.begin() as s:
        admin,scout,_,season,_,own,away,_,m=seed(s,profile='full')
        published(s,admin,m)
        part=pub.register_substitute(s,actor_id=admin.id,match_id=m.id,
                 team_id=own.id,name='Suplente que entró',shirt=21,position='DC',minute_in=72)
        assert part.starter is False and part.minute_in==72 and part.minute_out==90
        candidates,confirmed=board.choices(s,m.id,own.id)
        assert confirmed and len(candidates)==12
        spare=next(p for p in candidates if p['player_id']==part.player_id)
        assert spare['status']=='Participó'
        board.save_board(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                         payload={'players':[{'key':spare['key'],'score':7}]})
        assert summaries.summary_for(summaries.observations(s,actor_id=admin.id,
            season_id=season.id,player_ids=[part.player_id]),part.player_id)['opinions']==1
        with pytest.raises(ValueError,match='dorsal'):
            pub.register_substitute(s,actor_id=admin.id,match_id=m.id,
                 team_id=own.id,name='Otro',shirt=21,position='EI',minute_in=80)
        assert s.scalar(select(func.count(Participation.id)).where(Participation.match_id==m.id))==23


def test_analyst_metrics_separate_from_subjective_rating(session_factory):
    with session_factory.begin() as s:
        admin,scout,_,season,_,own,away,_,m=seed(s,profile='full')
        published(s,admin,m)
        first=board.choices(s,m.id,own.id)[0][0]
        board.save_board(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                         payload={'players':[{'key':first['key'],'score':8}]})
        note=metrics.save_stats(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                               player_id=first['player_id'],passes_complete=35,passes_total=39,
                               duels_won=7,duels_total=7)
        assert json.loads(note.data_json)['estadisticas']['pases_correctos']==35
        before=note.revision
        metrics.save_stats(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                           player_id=first['player_id'],passes_complete=35,passes_total=39,
                           duels_won=7,duels_total=7)
        assert note.revision==before
        summary=summaries.summary_for(summaries.observations(s,actor_id=admin.id,
            season_id=season.id,player_ids=[first['player_id']]),first['player_id'])
        assert summary['opinions']==1 and summary['average']==8
        with pytest.raises(ValueError,match='superar'):
            metrics.save_stats(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                              player_id=first['player_id'],passes_complete=40,passes_total=39,
                              duels_won=7,duels_total=7)


def test_merge_repairs_modern_player_reference_and_ui_key(session_factory):
    with session_factory.begin() as s:
        admin,scout,_,season,_,own,away,_,m=seed(s,profile='full')
        published(s,admin,m)
        first=board.choices(s,m.id,own.id)[0][0]
        # A canonical identity without overlapping game evaluation.
        target=Player(full_name='Nombre corregido',normalized_name='nombre corregido',
                      active=True,primary_position='POR')
        s.add(target);s.flush()
        board.save_board(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
            payload={'players':[{'key':first['key'],'score':8}]})
        target_id=target.id;source_id=first['player_id']
        players_repo.merge_players(s,source_id,target_id,admin.id)
        row=s.scalar(select(Contribution).where(Contribution.kind=='individual'))
        assert row.player_id==target_id
        assert json.loads(row.data_json)['key']==f'p:{target_id}'
        assert summaries.summary_for(summaries.observations(s,actor_id=admin.id,
            season_id=season.id,player_ids=[target_id]),target_id)['opinions']==1


def test_updated_ui_contract_and_no_new_migration():
    assert (ROOT/'VERSION').read_text().strip()=='4.7.4'
    root=(ROOT/'views/experience47.py').read_text()
    assert 'register_substitute(' in root
    assert 'Guardar estadísticas' in root
    assert "if False:  # legacy" in root
    assert "elif mode=='board472':" in root
    assert "if own_match:\n            _mobile_board(user,match,own_id)" in root
    assert (ROOT/'alembic/versions/0019_rating_release_4_7_3.py').exists()
