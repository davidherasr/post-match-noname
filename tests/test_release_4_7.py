"""4.7 acceptance: role-specific navigation, privacy, state and additive evidence."""
from __future__ import annotations
from datetime import date
import json
import pytest
from sqlalchemy import func, select
from models.entities import (
    Match, Participation, PlayerSeasonDecision, SportingContribution47 as Contribution,
    ActivityEvent47 as Event, ActivityState47 as EventState,
    PlayerProposal47 as Proposal, StaffRequest47 as Request, MatchPriority47 as Priority,
)
from core.permissions import navigation_for
from repositories import collaboration47 as domain, scouting as repo
from test_release_4_5 import seed, player


def _app_users(s):
    a,r,r2,season,comp,own,rival,third,m=seed(s,profile="full")
    return a,r,r2,season,comp,own,rival,third,m


def test_navigation_differentiates_aaron_david_coloto_and_admin():
    dd={'id':1,'role':'director','roles':['director','reporter'],'participation_profile':'viewer'}
    analyst={'id':2,'role':'reporter','roles':['reporter'],'participation_profile':'full'}
    own={'id':3,'role':'reporter','roles':['reporter'],'participation_profile':'own_only'}
    admin={'id':4,'role':'admin','roles':['admin']}
    assert navigation_for(dd)[:2]==['Inicio','Dirección Deportiva']
    assert 'Mis solicitudes' in navigation_for(analyst)
    assert navigation_for(own)==['Mis partidos','Mis valoraciones','Mis solicitudes']
    assert navigation_for(admin)[0]=='Administración'
    assert 'Dirección Deportiva' not in navigation_for(own)
    assert 'Administración' not in navigation_for(dd)


def test_private_drafts_denied_to_dd_until_shared_then_one_event(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        row=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
          kind='complete',title='Lectura del Cubillos',data={'rival':'Presiona en banda'},match_id=m.id)
        assert row.status=='draft'
        assert domain.list_contributions(s,actor_id=dd.id,season_id=season.id)==[]
        with pytest.raises(PermissionError):domain.get_contribution(s,row.id,dd.id)
        assert domain.visible_events(s,actor_id=dd.id,season_id=season.id)==[]
        assert domain.get_contribution(s,row.id,david.id).id==row.id
        domain.publish_draft(s,actor_id=david.id,contribution_id=row.id)
        domain.publish_draft(s,actor_id=david.id,contribution_id=row.id)
        assert len(domain.visible_events(s,actor_id=dd.id,season_id=season.id))==1
        assert domain.get_contribution(s,row.id,dd.id).status=='shared'
        assert domain.list_contributions(s,actor_id=roma.id,season_id=season.id)==[]


def test_private_not_found_from_other_staff_even_by_id(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        c=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
            kind='individual',title='Dorsal 11',data={'nota':8},match_id=m.id,publish=True)
        with pytest.raises(PermissionError):domain.get_contribution(s,c.id,roma.id)
        with pytest.raises(PermissionError):domain.publish_draft(s,actor_id=roma.id,contribution_id=c.id)
        with pytest.raises(PermissionError):domain.save_contribution(s,actor_id=roma.id,season_id=season.id,
              kind='individual',title='Hack',data={'nota':1},contribution_id=c.id,publish=True)


def test_quick_one_click_no_persist_no_lineup_and_edit_does_not_create_duplicate(session_factory):
    with session_factory.begin() as s:
        dd,diego,roma,season,comp,own,rival,_,m=_app_users(s)
        assert s.scalar(select(func.count(Participation.id)))==0
        # Picking an in-memory option is not a repository operation.
        assert s.scalar(select(func.count(Contribution.id)))==0
        c=domain.save_contribution(s,actor_id=diego.id,season_id=season.id,
           kind='quick',title='Nota Noname',match_id=m.id,team_id=own.id,
           data={'nota_noname':7,'comentario':''},publish=True)
        updated=domain.save_contribution(s,actor_id=diego.id,season_id=season.id,
           kind='quick',title='Nota Noname',match_id=m.id,team_id=own.id,
           data={'nota_noname':8,'comentario':'Más tarde'},publish=True,
           contribution_id=c.id,expected_revision=c.revision)
        assert updated.id==c.id and updated.revision==2
        assert s.scalar(select(func.count(Participation.id)))==0
        assert s.scalar(select(func.count(Contribution.id)))==1
        assert len(domain.visible_events(s,actor_id=dd.id,season_id=season.id))==2


def test_overwriting_private_draft_requires_revision_and_author(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        c=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
            kind='complete',title='Partido',data={'rival':'Cosas'},match_id=m.id)
        with pytest.raises(RuntimeError,match='Recarga'):
            domain.save_contribution(s,actor_id=david.id,season_id=season.id,
             kind='complete',title='Cambio',data={'rival':'Nuevo'},match_id=m.id,
             contribution_id=c.id,expected_revision=0)
        with pytest.raises(PermissionError):
            domain.save_contribution(s,actor_id=roma.id,season_id=season.id,
             kind='complete',title='Cambio',data={'rival':'Nuevo'},match_id=m.id,contribution_id=c.id)
        assert c.title=='Partido'


def test_note_eight_is_not_automatic_proposal_or_dd_interest(session_factory):
    with session_factory.begin() as s:
        dd,david,_,season,comp,own,rival,_,m=_app_users(s)
        c=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
            kind='individual',title='Extremo',data={'nota':8},match_id=m.id,publish=True)
        assert s.scalar(select(func.count(Proposal.id)))==0
        assert s.scalar(select(func.count(PlayerSeasonDecision.id)))==0
        p=domain.propose_player(s,actor_id=david.id,season_id=season.id,
            subject='Dorsal 11 del Cubillos',reason='Desborde repetido',contribution_id=c.id,match_id=m.id)
        assert p.state=='new'
        assert len([e for e,state in domain.visible_events(s,actor_id=dd.id,
                    season_id=season.id) if e.kind=='proposal'])==1
        domain.decide_proposal(s,actor_id=dd.id,proposal_id=p.id,state='saved')
        assert p.state=='saved'
        assert s.scalar(select(func.count(PlayerSeasonDecision.id)))==0
        with pytest.raises(PermissionError):
            domain.decide_proposal(s,actor_id=david.id,proposal_id=p.id,state='tracking')


def test_explicit_separate_event_seen_saved_and_request_status(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        req=domain.create_request(s,actor_id=dd.id,recipient_id=david.id,season_id=season.id,
           match_id=m.id,subject='Ver extremo',question='¿Cómo ataca la espalda?',priority='Alta')
        (event,state),=domain.visible_events(s,actor_id=david.id,season_id=season.id)
        assert state is None and req.state=='pending'
        domain.change_event_state(s,actor_id=david.id,event_id=event.id,action='seen')
        assert domain.visible_events(s,actor_id=david.id,season_id=season.id)==[]
        assert req.state=='pending'
        domain.change_event_state(s,actor_id=david.id,event_id=event.id,action='save')
        assert len(domain.visible_events(s,actor_id=david.id,season_id=season.id,filter_by='saved'))==1
        assert len(domain.list_requests(s,actor_id=david.id,season_id=season.id,include_closed=False))==1
        with pytest.raises(PermissionError):
            domain.change_event_state(s,actor_id=roma.id,event_id=event.id,action='seen')
        domain.respond_request(s,actor_id=david.id,request_id=req.id,answer='No pudo ser observado')
        assert req.state=='answered'
        assert len([e for e,state in domain.visible_events(s,actor_id=dd.id,
                    season_id=season.id) if e.kind=='response'])==1


def test_formation_disagreement_independent_personal_readings(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        for uid,shape in ((david.id,'4-4-2'),(roma.id,'4-2-3-1')):
            domain.save_contribution(s,actor_id=uid,season_id=season.id,
                kind='formation',title='Estructura rival',match_id=m.id,
                data={'equipo':rival.id,'sistema':shape},publish=True)
        assert m.away_formation is None
        assert m.away_formation_known is False
        view=domain.list_contributions(s,actor_id=dd.id,season_id=season.id,match_id=m.id)
        assert len(view)==2
        assert {json.loads(x.data_json)['sistema'] for x in view}=={'4-4-2','4-2-3-1'}
        assert domain.list_contributions(s,actor_id=david.id,season_id=season.id,match_id=m.id)[0].author_id==david.id


def test_provisional_identification_preserves_original_dorsal_and_no_participation(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        c=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
            kind='individual',title='EI sin nombre',match_id=m.id,team_id=rival.id,
            data={'posicion_observada':'EI','dorsal_observado':11,'nota':8},publish=True)
        second=domain.save_contribution(s,actor_id=roma.id,season_id=season.id,
            kind='individual',title='Dorsal 11',match_id=m.id,team_id=rival.id,
            data={'posicion_observada':'EI','dorsal_observado':11,'nota':7},publish=True)
        suggestions=domain.possible_identity_links(s,actor_id=dd.id,contribution_id=c.id)
        assert [x.id for x in suggestions]==[second.id]
        assert c.player_id is None and second.player_id is None
        p=player(s,dd,rival,season,'Extremo real 47')
        domain.resolve_observed_identity(s,actor_id=dd.id,contribution_id=c.id,player_id=p.id)
        assert json.loads(c.data_json)['identificacion_resuelta']['dorsal_original']==11
        assert s.scalar(select(func.count(Participation.id)))==0
        assert second.player_id is None


def test_match_priority_and_requests_separate_from_weekly_obligation(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        priority=domain.set_match_importance(s,actor_id=dd.id,
            match_id=m.id,importance='Muy importante',reason='Rival directo')
        assert priority.importance=='Muy importante'
        assert s.scalar(select(func.count(Request.id)))==0
        domain.create_request(s,actor_id=dd.id,recipient_id=roma.id,
            season_id=season.id,match_id=m.id,subject='Observar',question='Céntrate en EI')
        assert s.scalar(select(func.count(Request.id)))==1
        with pytest.raises(PermissionError):
            domain.set_match_importance(s,actor_id=david.id,match_id=m.id,importance='Normal')


def test_corrections_reportable_by_anybody_resolvable_only_by_admin(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        c=domain.create_correction(s,actor_id=david.id,season_id=season.id,
            entity_type='match',entity_id=m.id,description='Dorsal equivocado')
        assert domain.list_corrections(s,actor_id=roma.id)==[]
        with pytest.raises(PermissionError):
            domain.resolve_correction(s,actor_id=roma.id,correction_id=c.id,state='resolved',resolution='Corregido')
        # Seeded DD has an Admin role. The resolution is performed by an Admin-only account.
        pure=repo.create_user(s,'Administrador puro','pure47@example.test','pass',role='admin',actor_id=dd.id)
        domain.resolve_correction(s,actor_id=pure.id,correction_id=c.id,state='dismissed',resolution='Datos ya correctos')
        assert c.state=='dismissed' and c.resolved_by==pure.id


def test_create_official_match_requires_verified_date_role_and_handles_duplicates(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,third,m=_app_users(s)
        second=domain.create_official_match(s,actor_id=david.id,season_id=season.id,
             competition_id=comp.id,home_team_id=rival.id,away_team_id=third.id,
             match_date=date(2026,9,20),round_name='J2')
        assert second.kickoff_at is None
        with pytest.raises(ValueError,match='existe'):
            domain.create_official_match(s,actor_id=david.id,season_id=season.id,
                 competition_id=comp.id,home_team_id=rival.id,away_team_id=third.id,
                 match_date=date(2026,9,20),round_name='J2')
        own_only=repo.create_user(s,'Coloto','colo47@example.test','pass',role='reporter',actor_id=dd.id,
                                  participation_profile='own_only')
        with pytest.raises(PermissionError):
            domain.create_official_match(s,actor_id=own_only.id,season_id=season.id,
                 competition_id=comp.id,home_team_id=rival.id,away_team_id=own.id,
                 match_date=date(2026,9,29),round_name='J3')


def test_reading_shared_by_dd_can_be_shown_to_selected_staff_only(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        p=domain.propose_player(s,actor_id=david.id,season_id=season.id,
            subject='Dorsal 7 Ribert',reason='Merece visionado')
        domain.share_proposal(s,actor_id=dd.id,proposal_id=p.id,recipient_ids=[roma.id])
        assert p in domain.list_proposals(s,actor_id=roma.id,season_id=season.id)
        outsider=repo.create_user(s,'Diego','outsider47@example.test','pass',role='reporter',actor_id=dd.id)
        assert p not in domain.list_proposals(s,actor_id=outsider.id,season_id=season.id)
        with pytest.raises(PermissionError):domain.get_proposal(s,p.id,outsider.id)
        with pytest.raises(PermissionError):domain.share_proposal(s,actor_id=roma.id,proposal_id=p.id,recipient_ids=[])


def test_director_cannot_identify_another_reporters_unpublished_draft(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        original=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
            kind='individual',title='Dorsal desconocido',match_id=m.id,team_id=rival.id,
            data={'posicion_observada':'EI','dorsal_observado':11},publish=False)
        p=player(s,dd,rival,season,'Jugador privado 47')
        with pytest.raises(PermissionError):
            domain.resolve_observed_identity(s,actor_id=dd.id,
                contribution_id=original.id,player_id=p.id)
        assert original.player_id is None


def test_shared_proposals_do_not_expose_source_contribution(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        c=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
            kind='individual',title='Extremo evaluado',match_id=m.id,
            data={'nota':8,'comentario':'Observación privada del autor'},publish=True)
        p=domain.propose_player(s,actor_id=david.id,season_id=season.id,
            subject='Extremo a revisar',reason='Interesante y rápido',
            contribution_id=c.id,match_id=m.id)
        domain.share_proposal(s,actor_id=dd.id,proposal_id=p.id,recipient_ids=[roma.id])
        assert domain.get_proposal(s,p.id,roma.id).id==p.id
        with pytest.raises(PermissionError): domain.get_contribution(s,c.id,roma.id)


def test_general_observation_without_match_is_not_counted_as_participation(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        person=player(s,dd,own,season,'Jugador observado sin partido 47')
        row=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
            kind='general',title='Mejor lectura de presion',player_id=person.id,
            data={'observacion':'Evolución durante los entrenamientos'},publish=True)
        assert row.match_id is None
        assert s.scalar(select(func.count(Participation.id)))==0
        assert row in domain.list_contributions(s,actor_id=dd.id,season_id=season.id,player_id=person.id)


def test_request_response_links_only_an_authorised_published_document(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        request=domain.create_request(s,actor_id=dd.id,recipient_id=david.id,
            season_id=season.id,subject='Observar lateral',question='Dime si llega al área',match_id=m.id)
        private=domain.save_contribution(s,actor_id=david.id,season_id=season.id,kind='complete',
            title='Lectura preliminar',match_id=m.id,data={'rival':'Visto'},publish=False)
        with pytest.raises(PermissionError):domain.respond_request(s,actor_id=david.id,
            request_id=request.id,answer='',contribution_id=private.id)
        domain.publish_draft(s,actor_id=david.id,contribution_id=private.id)
        domain.respond_request(s,actor_id=david.id,request_id=request.id,
            answer='Revisado en el archivo',contribution_id=private.id)
        assert request.state=='answered'
        assert request.response_contribution_id==private.id
        assert domain.get_contribution(s,request.response_contribution_id,dd.id).id==private.id


def test_retrying_quick_save_without_id_is_idempotent(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        first=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
             match_id=m.id,team_id=own.id,kind='quick',title='Partido',
             data={'nota_noname':7},publish=True)
        retry=domain.save_contribution(s,actor_id=david.id,season_id=season.id,
             match_id=m.id,team_id=own.id,kind='quick',title='Partido',
             data={'nota_noname':7},publish=True)
        assert retry.id==first.id
        assert s.scalar(select(func.count(Contribution.id)))==1
        assert retry.revision==2


def test_backfilled_legacy_history_remains_in_all_not_fake_new(session_factory):
    with session_factory.begin() as s:
        dd,david,roma,season,comp,own,rival,_,m=_app_users(s)
        item=Event(season_id=season.id,actor_id=david.id,kind='legacy_report',
            title='Informe historico',detail='Archivo',target_type='legacy_report',
            target_id=999,audience='director')
        s.add(item);s.flush()
        assert not domain.visible_events(s,actor_id=dd.id,season_id=season.id,filter_by='new')
        assert [(e.id,e.kind) for e,state in domain.visible_events(
            s,actor_id=dd.id,season_id=season.id,filter_by='all')]==[(item.id,'legacy_report')]
