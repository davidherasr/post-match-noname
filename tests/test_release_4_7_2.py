"""Real mobile rating semantics: no fake XI, no duplicate, privacy & tamper protection."""
from pathlib import Path
import json
import pytest
from sqlalchemy import select,func
from core.federation_roster import parse_federation_roster
from repositories import mobile472 as board, collaboration47 as domain
from repositories import matches as matches_repo
from repositories import publication473
from models.entities import Participation, SportingContribution47 as Contribution, PlayerProposal47 as Proposal, PlayerSeasonDecision
from test_release_4_5 import seed, player

ROOT=Path(__file__).resolve().parents[1]


def release_fixture(session, admin, match, own, away, own_special=None, rival_special=None):
    """Prepare the genuine two XIs before rating, exactly as users must."""
    def xi(prefix,special):
        players=[f'1;Portero {prefix};POR']
        for no,pos in [(2,'LD'),(3,'DCD'),(4,'DCI'),(5,'LI'),(6,'MCD'),(7,'MCI'),
                       (8,'ED'),(9,'MP'),(10,'EI'),(11,'DC')]:
            players.append(f'{no};{special if no==11 and special else f"Futbolista {prefix} {no}"};{pos}')
        return '\n'.join(players)
    publication473.publish_match(session,actor_id=admin.id,match_id=match.id,
        home_text=xi('Noname',own_special),away_text=xi('Cubillos',rival_special))


def test_phone_paste_two_column_parsing_and_roles():
    plain=parse_federation_roster('1;Chuchi\n2;Yago\n15;Asiel')
    assert [x.shirt_number for x in plain]==[1,2,15]
    assert [x.name for x in plain]==['Chuchi','Yago','Asiel']
    assert all(x.squad_role is None for x in plain)
    lineup=parse_federation_roster('TITULARES\n1;Chuchi;POR\n2;Yago;LD\nSUPLENTES\n12;Jugador;POR')
    assert [x.squad_role for x in lineup]==['starter','starter','substitute']


def test_phone_paste_does_not_invent_participations_and_enables_named_players(session_factory):
    with session_factory.begin() as s:
        admin,david,roma,season,_,own,away,_,m=seed(s,profile='full')
        result=matches_repo.import_federation_roster_text(s,team_id=own.id,season_id=season.id,
           actor_id=david.id,text='1;Chuchi;POR\n2;Yago;LD',match_id=m.id)
        assert result['rows']==2 and result['starters']==0
        players,confirmed=board.choices(s,m.id,own.id)
        assert confirmed is False
        assert [r['name'] for r in players]==['Chuchi','Yago']
        assert s.scalar(select(func.count(Participation.id)))==0
        with pytest.raises(PermissionError,match='no está publicado'):
            board.save_board(s,actor_id=david.id,match_id=m.id,team_id=own.id,
                payload={'players':[{'key':players[0]['key'],'score':8}]})
        assert s.scalar(select(func.count(Contribution.id)))==0


def test_draft_not_revealed_and_rating_edit_is_idempotent(session_factory):
    with session_factory.begin() as s:
        admin,david,roma,season,_,own,away,_,m=seed(s,profile='full')
        pl=player(s,admin,own,season,'Futbolista Noname')
        release_fixture(s,admin,m,own,away,own_special='Futbolista Noname')
        key=f'p:{pl.id}'
        payload={'team_score':6,'players':[{'key':key,'score':7,'comment':'Primera lectura'}]}
        board.save_board(s,actor_id=david.id,match_id=m.id,team_id=own.id,payload=payload)
        payload['team_score']=8
        payload['players'][0]['score']=9
        board.save_board(s,actor_id=david.id,match_id=m.id,team_id=own.id,payload=payload)
        assert s.scalar(select(func.count(Contribution.id)))==2
        rows=domain.list_contributions(s,actor_id=admin.id,season_id=season.id)
        assert len(rows)==2
        assert all(row.status=='shared' for row in rows)
        assert domain.list_contributions(s,actor_id=roma.id,season_id=season.id)==[]
        assert board.existing(s,author_id=david.id,match_id=m.id)[1][f'{own.id}:{key}']['score']==9
        assert s.scalar(select(func.count(PlayerSeasonDecision.id)))==0


def test_explicit_favorite_only_once_and_not_from_grade(session_factory):
    with session_factory.begin() as s:
        admin,david,roma,season,_,own,away,_,m=seed(s,profile='full')
        pl=player(s,admin,away,season,'Extremo rival')
        release_fixture(s,admin,m,own,away,rival_special='Extremo rival')
        payload={'players':[{'key':f'p:{pl.id}','score':9,'comment':'Desborde repetido'}]}
        board.save_board(s,actor_id=david.id,match_id=m.id,team_id=away.id,payload=payload)
        assert s.scalar(select(func.count(Proposal.id)))==0
        payload['players'][0]['favorite']=True
        board.save_board(s,actor_id=david.id,match_id=m.id,team_id=away.id,payload=payload)
        board.save_board(s,actor_id=david.id,match_id=m.id,team_id=away.id,payload=payload)
        assert s.scalar(select(func.count(Proposal.id)))==1
        assert s.scalar(select(func.count(PlayerSeasonDecision.id)))==0
        assert not domain.list_proposals(s,roma.id,season.id)


def test_unidentified_opponent_is_not_rated_without_published_named_xi(session_factory):
    with session_factory.begin() as s:
        admin,david,roma,season,_,own,away,_,m=seed(s,profile='full')
        key=board.positional_choices('4-2-3-1')[0]['key']
        with pytest.raises(PermissionError,match='no está publicado'):
            board.save_board(s,actor_id=david.id,match_id=m.id,team_id=away.id,
              payload={'formation':'4-2-3-1','players':[{'key':key,'score':7}]})
        release_fixture(s,admin,m,own,away)
        with pytest.raises(PermissionError,match='ajenos'):
            board.save_board(s,actor_id=david.id,match_id=m.id,team_id=away.id,
              payload={'formation':'4-2-3-1','players':[{'key':key,'score':7}]})
        assert s.scalar(select(func.count(Contribution.id)))==0


def test_security_rejects_arbitrary_player_cross_team_and_duplicate(session_factory):
    with session_factory.begin() as s:
        admin,david,roma,season,_,own,away,third,m=seed(s,profile='full')
        rogue=player(s,admin,third,season,'Jugador fuera de partido')
        valid=player(s,admin,own,season,'Jugador del partido')
        release_fixture(s,admin,m,own,away,own_special='Jugador del partido')
        with pytest.raises(PermissionError):
            board.save_board(s,actor_id=david.id,match_id=m.id,team_id=own.id,
                payload={'players':[{'key':f'p:{rogue.id}','score':9}]})
        with pytest.raises(ValueError,match='repetido'):
            board.save_board(s,actor_id=david.id,match_id=m.id,team_id=own.id,
                payload={'players':[{'key':f'p:{valid.id}','score':6},{'key':f'p:{valid.id}','score':6}]})
        with pytest.raises(ValueError):
            board.save_board(s,actor_id=david.id,match_id=m.id,team_id=away.id,
                payload={'team_score':9,'players':[]})
        assert s.scalar(select(func.count(Contribution.id)))==0


def test_code_integrates_real_v2_component_and_version():
    view=(ROOT/'views/experience47.py').read_text()
    comp=(ROOT/'ui/mobile472.py').read_text()
    assert 'scoreboard_component(' in view and 'inbox_component(' in view
    assert 'setTriggerValue' in comp
    assert "setTriggerValue('save',packet)" in comp
    assert "textContent" in comp and 'innerHTML' not in comp
    assert 'parse_federation_roster(text)' in view
    assert (ROOT/'VERSION').read_text().strip()=='4.7.4'
    assert 'streamlit>=1.51' in (ROOT/'requirements.txt').read_text()


def test_fixture_anchors_exclude_postponed_without_inventing_played_status(session_factory):
    from core.match_priority472 import current_fixtures
    from datetime import date
    with session_factory.begin() as s:
        admin,david,roma,season,_,own,away,_,m=seed(s,profile='full')
        today=date(2026,10,28)
        past,next_game=current_fixtures([m],today)
        assert past.id==m.id and next_game is None
        m.schedule_status='aplazado'
        assert current_fixtures([m],today)==(None,None)


def test_lineup_import_requires_really_declared_starting_section(session_factory):
    with session_factory.begin() as s:
        admin,david,roma,season,_,own,away,_,m=seed(s,profile='full')
        first=matches_repo.import_federation_roster_text(s,team_id=own.id,
          season_id=season.id,actor_id=david.id,match_id=m.id,
          text='TITULARES\n1;Chuchi;POR\n2;Yago;LD\nSUPLENTES\n12;Juan')
        assert first['starters']==2 and first['substitutes']==1
        team,confirmed=board.choices(s,m.id,own.id)
        assert confirmed and len(team)==2
        assert len([r for r in team if r['status']=='Titular'])==2


def test_repeat_identical_individual_rating_does_not_make_new_revision(session_factory):
    with session_factory.begin() as s:
        admin,david,roma,season,_,own,away,_,m=seed(s,profile='full')
        pl=player(s,admin,own,season,'Mediocentro')
        release_fixture(s,admin,m,own,away,own_special='Mediocentro')
        payload={'players':[{'key':f'p:{pl.id}','score':7,'comment':'Correcto'}]}
        board.save_board(s,actor_id=david.id,match_id=m.id,team_id=own.id,payload=payload)
        row=s.scalar(select(Contribution).where(Contribution.kind=='individual'))
        original=row.revision
        board.save_board(s,actor_id=david.id,match_id=m.id,team_id=own.id,payload=payload)
        assert row.revision==original
        assert s.scalar(select(func.count(Contribution.id)))==1


def test_full_postmatch_is_still_immutable_after_shared(session_factory):
    with session_factory.begin() as s:
        admin,david,roma,season,_,own,away,_,m=seed(s,profile='full')
        row=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
             kind='complete',title='Postpartido',data={'rival':'Bloque medio'},
             match_id=m.id,publish=True)
        with pytest.raises(ValueError,match='inmutable'):
            domain.save_contribution(s,actor_id=david.id,season_id=season.id,
             kind='complete',title='Cambio',data={'rival':'Otro'},
             match_id=m.id,contribution_id=row.id,publish=True)
