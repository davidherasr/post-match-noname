"""4.7.1: user journeys simplified without weakening data rules."""
from pathlib import Path
import pytest
from sqlalchemy import select, func
from models.entities import Player, TeamRoster, AuditLog, PlayerProposal47 as Proposal
from core.permissions import navigation_for
from repositories import scouting as repo, players as players_repo, permanent_deletion as purge, collaboration47 as domain
from test_release_4_5 import seed, player

ROOT=Path(__file__).resolve().parents[1]


def test_simplified_navigation_leaves_tools_available_in_context():
    analyst={'id':1,'role':'reporter','roles':['reporter'],'participation_profile':'full'}
    own={'id':2,'role':'reporter','roles':['reporter'],'participation_profile':'own_only'}
    assert navigation_for(analyst)==['Inicio','Partidos','Jugadores','Mis solicitudes']
    assert navigation_for(own)==['Mis partidos','Mis solicitudes']
    ui=(ROOT/'views/experience47.py').read_text(encoding='utf-8')
    assert "def _admin_players471" in ui
    assert "'Buscar por nombre'" in ui
    assert 'purge.build_plan' in ui and 'purge.execute_plan' in ui
    assert "f'Elaborar postpartido de {rival.name}'" in ui
    assert "with st.expander('Buscar partidos anteriores o de otros equipos'" in ui
    assert "'Solo puntuar a Noname'" in ui
    assert "'⭐ Destacar este jugador para Aarón'" in ui
    assert 'if own_only:' in ui and "return my_contributions(user,ratings_only=True)" in ui
    assert "st.radio('Periodo'" not in ui


def test_admin_can_correct_typo_without_losing_roster_then_delete_with_preview(session_factory):
    with session_factory.begin() as s:
        admin,reporter,_,season,_,own,rival,_,match=seed(s)
        p=player(s,admin,rival,season,'Tomss Calvo')
        old=p.id
        players_repo.update_player(s,old,admin.id,full_name='Tomás Calvo')
        assert s.get(Player,old).full_name=='Tomás Calvo'
        assert s.scalar(select(func.count(TeamRoster.id)).where(TeamRoster.player_id==old))==1
        with pytest.raises(ValueError,match='vacío'):
            players_repo.update_player(s,old,admin.id,full_name='   ')
        with pytest.raises(PermissionError):
            purge.build_plan(s,{'jugadores':[old]},reporter.id)
        plan=purge.build_plan(s,{'jugadores':[old]},admin.id)
        assert old in plan.rows['players'] and len(plan.rows['team_rosters'])==1
        with pytest.raises(ValueError,match='vista previa'):
            purge.execute_plan(s,{'jugadores':[old]},admin.id,'0'*64)
        purge.execute_plan(s,{'jugadores':[old]},admin.id,plan.fingerprint)
        assert s.get(Player,old) is None
        assert s.scalar(select(func.count(TeamRoster.id)).where(TeamRoster.player_id==old))==0
        assert s.scalar(select(func.count(AuditLog.id)).where(AuditLog.action=='permanent_delete_sporting_records'))==1


def test_favorite_must_be_explicit_and_sent_to_dd_only(session_factory):
    with session_factory.begin() as s:
        admin,diego,roma,season,_,own,rival,_,match=seed(s)
        row=domain.save_contribution(s,actor_id=diego.id,season_id=season.id,
            kind='individual',title='Lateral sin identificar',match_id=match.id,
            data={'nota':8,'posicion_observada':'LD'},publish=True)
        assert s.scalar(select(func.count(Proposal.id)))==0
        p=domain.propose_player(s,actor_id=diego.id,season_id=season.id,
            subject='Lateral dorsal 2',reason='Fue decisivo en el partido',
            match_id=match.id,contribution_id=row.id)
        assert p.author_id==diego.id
        assert [x.id for x in domain.list_proposals(s,admin.id,season.id)]==[p.id]
        assert domain.list_proposals(s,roma.id,season.id)==[]
