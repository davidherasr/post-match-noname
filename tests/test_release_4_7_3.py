"""4.7.4 acceptance: both named XIs, only explicit publication grants rating access."""
from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import select, func
from test_release_4_5 import seed
from models.entities import MatchRatingRelease473 as Release, Participation, SportingContribution47 as Contribution, Player, TeamRoster
from repositories import publication473 as publication, mobile472 as board
from repositories import matches as matches_repo, collaboration47 as domain
from core.lineup473 import parse_xi
from core.constants import POSITIONS

ROOT=Path(__file__).resolve().parents[1]


def xi(team, shirt_offset=0):
    entries=[('1',f'Portero {team}','POR'),('2',f'Lateral {team}','LD'),
         ('3',f'Central derecho {team}','DCD'),('4',f'Central izquierdo {team}','DCI'),
         ('5',f'Lateral zurdo {team}','LI'),('6',f'Pivote derecho {team}','MCD'),
         ('7',f'Pivote izquierdo {team}','MCI'),('8',f'Extremo derecho {team}','ED'),
         ('9',f'Mediapunta {team}','MP'),('10',f'Extremo izquierdo {team}','EI'),
         ('11',f'Delantero {team}','DC')]
    return 'TITULARES\n'+'\n'.join(';'.join(r) for r in entries)


def published(s, admin, match):
    return publication.publish_match(s,actor_id=admin.id,match_id=match.id,
       home_text=xi('Noname'), away_text=xi('Betis'))


def test_positions_are_distinct_match_roles():
    assert {'POR','LD','DCD','DCI','DCC','MCD','MCI','MCC','EI','ED','MP','DC'} <= set(POSITIONS)
    assert [r.position for r in parse_xi(xi('Prueba'))][5:7]==['MCD','MCI']
    assert len(parse_xi(xi('Prueba')))==11
    assert len(parse_xi(xi('Prueba')+'\nSUPLENTES\n12;Reserva;SD'))==12


@pytest.mark.parametrize('bad,needle',[
    (xi('Prueba').replace('11;Delantero Prueba;DC',''),'11 titulares'),
    (xi('Prueba').replace('4;Central izquierdo Prueba;DCI','4;Central izquierdo Prueba;VOL'),'posición'),
    (xi('Prueba').replace('4;Central izquierdo Prueba;DCI','3;Central izquierdo Prueba;DCI'),'duplicados'),
    (xi('Prueba').replace('1;Portero Prueba;POR','1;Portero Prueba;DC'),'portero'),
    (xi('Prueba').replace('7;Pivote izquierdo Prueba;MCI','7;Pivote derecho Prueba;MCI'),'repetidos'),
])
def test_strict_xi_rejects_error(bad,needle):
    with pytest.raises(ValueError,match=needle):parse_xi(bad)


def test_unpublished_not_evaluable_and_11_own_alone_insufficient(session_factory):
    with session_factory.begin() as s:
        admin,scout,_,season,_,own,away,_,m=seed(s)
        assert publication.readiness(s,m.id)['published'] is False
        with pytest.raises(PermissionError,match='publicado'):
            board.save_board(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                            payload={'players':[{'key':'p:100','score':8}]})
        with pytest.raises(ValueError,match='0/11'):
            publication.publish_match(s,actor_id=admin.id,match_id=m.id,home_text=xi('Noname'))
        # Caller would roll the failed transaction back; product never calls it
        # twice in one already-failed request.
        assert not publication.is_open(s,m.id)


def test_no_delegation_to_casual_scout(session_factory):
    with session_factory.begin() as s:
        admin,scout,_,_,_,_,_,_,m=seed(s,profile='own_only')
        with pytest.raises(PermissionError,match='habilitada'):
            publication.publish_match(s,actor_id=scout.id,match_id=m.id,
                home_text=xi('Noname'),away_text=xi('Betis'))
        assert not publication.is_open(s,m.id)


def test_full_workflow_publication_privacy_and_real_players(session_factory):
    with session_factory.begin() as s:
        admin,scout,roma,season,_,own,away,_,m=seed(s,profile='own_only')
        release=published(s,admin,m)
        assert release.published_by==admin.id
        state=publication.readiness(s,m.id)
        assert state['published'] and all(x['ready'] and x['starters']==11 for x in state['teams'].values())
        own_list,own_confirmed=board.choices(s,m.id,own.id)
        rival_list,rival_confirmed=board.choices(s,m.id,away.id)
        assert own_confirmed and rival_confirmed
        assert len(own_list)==len(rival_list)==11
        assert own_list[5]['position']=='MCD'
        assert all(x['player_id'] is not None for x in rival_list)
        one=own_list[0]
        for score in (7,9):
            board.save_board(s,actor_id=scout.id,match_id=m.id,team_id=own.id,
                payload={'players':[{'key':one['key'],'score':score,'comment':'Buen partido'}]})
        assert board.existing(s,author_id=scout.id,match_id=m.id)[1][f'{own.id}:{one["key"]}']['score']==9
        assert s.scalar(select(func.count(Contribution.id)).where(Contribution.kind=='individual'))==1
        assert domain.list_contributions(s,actor_id=roma.id,season_id=season.id)==[]
        assert len(domain.list_contributions(s,actor_id=admin.id,season_id=season.id))==1
        # User cannot rate a never-registered substitute / unrelated player.
        with pytest.raises(PermissionError,match='ajenos'):
            board.save_board(s,actor_id=scout.id,match_id=m.id,team_id=away.id,
                payload={'players':[{'key':'p:999999','score':9}]})
        with pytest.raises(ValueError,match='publicado'):
            published(s,admin,m)
        with pytest.raises(ValueError,match='publicada'):
            matches_repo.replace_participations(s,m.id,own.id,[],admin.id)


def test_release_requires_both_xi_not_hours_or_score(session_factory):
    with session_factory.begin() as s:
        admin,scout,_,season,_,own,away,_,m=seed(s)
        assert m.kickoff_at is None and m.home_score is None
        publication.publish_match(s,actor_id=admin.id,match_id=m.id,
            home_text=xi('Noname'),away_text=xi('Betis'))
        assert publication.is_open(s,m.id)
        assert s.scalar(select(func.count(Participation.id)).where(Participation.match_id==m.id))==22
        assert s.scalar(select(func.count(Player.id)))==22
        assert s.scalar(select(func.count(TeamRoster.id)))==22


def test_future_postponed_and_old_calendar_match_remains_private(session_factory):
    with session_factory.begin() as s:
        admin,_,_,_,_,_,_,_,m=seed(s)
        m.match_date=date(2027,1,1)
        with pytest.raises(ValueError,match='todavía'):
            published(s,admin,m)
        m.match_date=date(2026,9,13)
        m.schedule_status='postponed'
        with pytest.raises(ValueError,match='aplazado'):
            published(s,admin,m)
        assert not publication.is_open(s,m.id)


def test_ui_requires_publish_before_any_rating():
    src=(ROOT/'views/experience47.py').read_text()
    server=(ROOT/'repositories/mobile472.py').read_text()
    mobile=(ROOT/'ui/mobile472.py').read_text()
    assert 'if not released:' in src and '_prepare_rating_release473(user,match)' in src
    assert 'Valorar jugadores' in src and 'Cargar alineaciones y publicar' in src
    assert 'if not is_open(session, match.id)' in server
    assert 'teamgrade' not in mobile and 'NOTA COLECTIVA' not in mobile
    assert (ROOT/'VERSION').read_text().strip()=='4.7.4'


def test_atomic_publishing_rolls_back_first_team_if_second_invalid(session_factory):
    # Simulates the production session_scope transaction boundary.
    with session_factory.begin() as s:
        admin,_,_,_,_,own,away,_,m=seed(s)
        ids=(admin.id,m.id,own.id,away.id)
    aid,mid,oid,rid=ids
    with pytest.raises(ValueError,match='11 titulares'):
        with session_factory.begin() as s:
            publication.publish_match(s,actor_id=aid,match_id=mid,
                home_text=xi('Noname'),away_text='1;Portero Rival;POR')
    with session_factory.begin() as s:
        assert not publication.is_open(s,mid)
        assert s.scalar(select(func.count(Participation.id)))==0
        assert s.scalar(select(func.count(Player.id)))==0
        assert s.scalar(select(func.count(TeamRoster.id)))==0


def test_publish_previously_confirmed_two_XI_without_reimport(session_factory):
    with session_factory.begin() as s:
        admin,_,_,_,_,own,away,_,m=seed(s)
        # Use the existing Federation importer when users already uploaded an XI
        # via an older screen; do not require them to paste the same text again.
        for tid,name in ((own.id,'Noname'),(away.id,'Betis')):
            result=matches_repo.import_federation_roster_text(
                s,team_id=tid,season_id=m.season_id,actor_id=admin.id,
                match_id=m.id,text=xi(name))
            assert result['starters']==11
        assert publication.readiness(s,m.id)['teams'][own.id]['ready'] is True
        publication.publish_match(s,actor_id=admin.id,match_id=m.id)
        assert publication.is_open(s,m.id)
        assert s.scalar(select(func.count(Participation.id)))==22


def test_svg_preview_escapes_html_and_only_uses_declared_positions():
    from ui.lineup473 import lineup_svg
    markup=lineup_svg([{'Dorsal':2,'Jugador':'Juan <script>alert(1)</script>','Posición':'LD'}])
    assert '<script>' not in markup
    assert '&lt;script&gt;' in markup
    assert 'aria-label=' in markup


def test_player_positions_from_xi_never_used_as_inferred_formation(session_factory):
    with session_factory.begin() as s:
        admin,_,_,season,_,own,away,_,m=seed(s)
        published(s,admin,m)
        assert m.home_formation_known is False and m.away_formation_known is False
        assert m.home_formation is None and m.away_formation is None
        ps=list(s.scalars(select(Participation).where(Participation.match_id==m.id,
             Participation.team_id==own.id,Participation.starter.is_(True))).all())
        assert {p.position for p in ps}>={'MCD','MCI','DCD','DCI'}
