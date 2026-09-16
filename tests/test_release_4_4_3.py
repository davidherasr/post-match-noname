"""4.4.3 regression: voluntary DD requests, provenance, fast reports, neutral edits."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from core.permissions import navigation_for
from models.entities import (AuditLog, MatchOpinionPlayer, PlayerEvaluation,
    PlayerObservationRecipient, PlayerObservationRequest, PlayerObservationResponse)
from repositories import observation_requests as requests
from repositories import scouting as repo
from repositories import sporting_reading

ROOT = Path(__file__).resolve().parents[1]


def _seed(session):
    admin = repo.create_user(session, 'Admin', 'admin443@example.com', 'pass', role='admin',
        roles=['admin', 'director'])
    informant = repo.create_user(session, 'Informador', 'info443@example.com', 'pass',
        role='reporter', roles=['reporter'], actor_id=admin.id)
    other = repo.create_user(session, 'Otro informador', 'other443@example.com', 'pass',
        role='reporter', roles=['reporter'], actor_id=admin.id)
    dd_pure = repo.create_user(session, 'DD puro', 'dd443@example.com', 'pass',
        role='director', roles=['director'], actor_id=admin.id)
    season = repo.create_season(session, '2026/27', date(2026, 7, 1), date(2027, 6, 30), admin.id)
    repo.set_active_season(session, season.id, admin.id)
    competition = repo.create_competition(session, 'Regional 443', actor_id=admin.id)
    own = repo.create_team(session, 'C.D. Noname', actor_id=admin.id)
    rival = repo.create_team(session, 'Rival 443', actor_id=admin.id)
    third = repo.create_team(session, 'Otro club 443', actor_id=admin.id)
    repo.set_own_team(session, own.id, admin.id)
    external = repo.find_or_create_player(session, 'Futbolista externo', primary_position='LI', actor_id=admin.id)
    ours = repo.find_or_create_player(session, 'Futbolista propio', primary_position='DC', actor_id=admin.id)
    repo.assign_player_to_roster(session, rival.id, season.id, external.id, 3, actor_id=admin.id)
    repo.assign_player_to_roster(session, own.id, season.id, ours.id, 5, actor_id=admin.id)
    own_match = repo.create_match(session, season_id=season.id, competition_id=competition.id,
        round_name='J1', match_date=date(2026,9,12), home_team_id=own.id, away_team_id=rival.id,
        created_by=admin.id, status='published', kickoff_at=datetime(2026,9,12,17), schedule_status='confirmed')
    neutral = repo.create_match(session, season_id=season.id, competition_id=competition.id,
        round_name='J2', match_date=date(2026,9,19), home_team_id=rival.id, away_team_id=third.id,
        created_by=admin.id, status='published', kickoff_at=datetime(2026,9,19,17), schedule_status='confirmed')
    parts = repo.replace_participations(session, own_match.id, rival.id,[
        {'selected': True, 'player_id': external.id, 'shirt_number': 3, 'starter':True,
         'position': 'LI', 'minute_in': 0, 'minute_out': 90, 'captain':False}], admin.id)
    repo.assign_reporters(session,own_match.id,[informant.id],admin.id)
    report=repo.get_or_create_report(session,own_match.id,informant.id)
    ev=repo.upsert_evaluation(session,report.id,external.id,rival.id,parts[0].id,
        actor_id=informant.id, observation_status='evaluated', general_rating=8.0,
        short_note='Buen lateral en defensa y combinación')
    repo.submit_report(session,report.id,informant.id)
    return locals()


def test_release_navigation_and_direct_click_scores():
    assert (ROOT / 'VERSION').read_text().strip() == '4.4.3'
    assert 'Informes' in navigation_for({'id':1, 'roles':['reporter'], 'role':'reporter'})
    assert 'Informes' in navigation_for({'id':1, 'roles':['director'], 'role':'director'})
    assert 'Informes' not in navigation_for({'id':1, 'roles':['admin'], 'role':'admin'})
    code=(ROOT / 'views/reports.py').read_text()
    assert 'def _render_quick_report' in code and 'st.pills' in code
    assert 'default=[]' in code and 'Sin evaluar' in code
    assert '"postmatch_tracking_wizard"' in code
    neutral=(ROOT/'views/jornada.py').read_text()
    assert 'home_choice = c1.pills' in neutral and 'rating = rating_from_choice' in neutral


def test_dd_creates_voluntary_request_and_rejects_ineligible_players_and_roles(session_factory):
    with session_factory.begin() as s:
        x=_seed(s)
        a,informant,other,dd=x['admin'],x['informant'],x['other'],x['dd_pure']
        season,external,ours,m=x['season'],x['external'],x['ours'],x['own_match']
        with pytest.raises(PermissionError):
            requests.create_request(s,actor_id=informant.id, player_id=external.id,
                season_id=season.id, recipient_ids=[other.id],question='Defensa del uno contra uno')
        with pytest.raises(ValueError,match='propios'):
            requests.create_request(s,actor_id=a.id,player_id=ours.id,
                season_id=season.id,recipient_ids=[informant.id],question='Defensa del uno contra uno')
        with pytest.raises(PermissionError):
            requests.create_request(s,actor_id=a.id,player_id=external.id,
                season_id=season.id,recipient_ids=[dd.id],question='Defensa del uno contra uno')
        q=requests.create_request(s,actor_id=a.id, player_id=external.id,
            season_id=season.id,recipient_ids=[informant.id], question='Defensa del uno contra uno',
            target_match_id=m.id)
        assert q.status=='open' and len(requests.recipients(s,q.id))==1
        same=requests.create_request(s,actor_id=a.id, player_id=external.id,
            season_id=season.id,recipient_ids=[informant.id,other.id],question='Defensa del uno contra uno',
            target_match_id=m.id)
        assert same.id==q.id and len(requests.recipients(s,q.id))==2
        assert requests.match_relevance(s,q,m.id)=='participation'
        assert {r.id for r in requests.list_requests(s,season_id=season.id,reporter_id=other.id)}=={q.id}
        assert s.scalar(select(AuditLog).where(AuditLog.action=='create_observation_request'))


def test_request_respond_links_existing_rating_never_fabricates_another(session_factory):
    with session_factory.begin() as s:
        x=_seed(s)
        a,inf,season,p,m,ev=x['admin'],x['informant'],x['season'],x['external'],x['own_match'],x['ev']
        q=requests.create_request(s,actor_id=a.id,player_id=p.id,season_id=season.id,
            recipient_ids=[inf.id],question='Cómo protege su espalda',target_match_id=m.id)
        with pytest.raises(PermissionError):
            requests.respond(s,actor_id=a.id,request_id=q.id,result='seen',match_id=m.id,note='Bien')
        first=requests.respond(s,actor_id=inf.id,request_id=q.id,result='seen',match_id=m.id)
        assert first.player_evaluation_id==ev.id and first.neutral_signal_id is None
        assert first.note is None
        assert s.scalar(select(PlayerEvaluation).where(PlayerEvaluation.id==ev.id)).general_rating==8.0
        assert s.scalar(select(PlayerObservationRecipient).where(
            PlayerObservationRecipient.request_id==q.id, PlayerObservationRecipient.user_id==inf.id)).status=='answered'
        with pytest.raises(PermissionError):
            requests.respond(s,actor_id=inf.id,request_id=q.id,result='seen',match_id=m.id)
        assert s.query(PlayerObservationResponse).filter_by(request_id=q.id).count()==1
        requests.close_request(s,actor_id=a.id,request_id=q.id,reason='Información suficiente')
        assert not requests.list_requests(s,season_id=season.id,active_only=True)


def test_no_play_confirmation_required_for_roster_only_and_voluntary_decline(session_factory):
    with session_factory.begin() as s:
        x=_seed(s)
        a,inf,other,season,p,n=x['admin'],x['informant'],x['other'],x['season'],x['external'],x['neutral']
        q=requests.create_request(s,actor_id=a.id,player_id=p.id,season_id=season.id,
            recipient_ids=[inf.id,other.id],question='Comportamiento de lateral en campo',target_match_id=n.id)
        assert requests.match_relevance(s,q,n.id)=='possible'
        with pytest.raises(ValueError,match='confirmar'):
            requests.respond(s,actor_id=inf.id,request_id=q.id,result='seen',match_id=n.id,note='Defensivamente correcto')
        answer=requests.respond(s,actor_id=inf.id,request_id=q.id,result='seen',match_id=n.id,
            note='Defensivamente correcto',confirmed_played=True)
        assert answer.player_evaluation_id is None and answer.neutral_signal_id is None
        requests.respond(s,actor_id=other.id,request_id=q.id,result='declined',note='No lo vi')
        assert not requests.list_requests(s,season_id=season.id,reporter_id=other.id,active_only=True)
        assert requests.list_requests(s,season_id=season.id,active_only=True)


def test_neutral_edit_preserves_signal_id_and_dd_response_link(session_factory):
    with session_factory.begin() as s:
        x=_seed(s)
        a,inf,season,p,n,r=x['admin'],x['informant'],x['season'],x['external'],x['neutral'],x['rival']
        opinion=sporting_reading.save_neutral_opinion(s,match_id=n.id,user_id=inf.id,
            home_team_rating=7,away_team_rating=6,summary='Primera lectura',
            player_rows=[{'player_id':p.id,'team_id':r.id,'rating':8,'note':'Defensivamente fuerte'}])
        row=s.scalar(select(MatchOpinionPlayer).where(MatchOpinionPlayer.opinion_id==opinion.id))
        q=requests.create_request(s,actor_id=a.id,player_id=p.id,season_id=season.id,
            recipient_ids=[inf.id],question='Defensa uno contra uno')
        response=requests.respond(s,actor_id=inf.id,request_id=q.id,result='seen',match_id=n.id,confirmed_played=True)
        assert response.neutral_signal_id==row.id
        sporting_reading.save_neutral_opinion(s,match_id=n.id,user_id=inf.id,
            home_team_rating=8,away_team_rating=6,summary='Editada',
            player_rows=[{'player_id':p.id,'team_id':r.id,'rating':9,'note':'Mejoró'}])
        assert s.scalar(select(MatchOpinionPlayer).where(MatchOpinionPlayer.opinion_id==opinion.id)).id==row.id
        assert s.get(PlayerObservationResponse,response.id).neutral_signal_id==row.id
        assert s.get(MatchOpinionPlayer,row.id).rating==9


def test_quick_report_two_team_grades_without_rating_full_roster(session_factory):
    with session_factory.begin() as s:
        x = _seed(s)
        a, another, match = x['admin'], x['other'], x['own_match']
        repo.assign_reporters(s, match.id, [x['informant'].id, another.id], a.id)
        report = repo.get_or_create_report(s, match.id, another.id)
        repo.save_report_summary(s, report.id, rival_level=None,
            opponent_overview=None, own_team_note=None, key_takeaways=None,
            standout_player_id=None, actor_id=another.id, own_team_rating=7, rival_team_rating=6)
        repo.submit_report(s, report.id, another.id)
        assert report.status == 'incorporated'
        assert s.query(PlayerEvaluation).filter_by(report_id=report.id).count() == 0


def test_target_match_requires_real_player_link_and_later_can_be_repeated(session_factory):
    with session_factory.begin() as s:
        x = _seed(s)
        a, inf, season, p = x['admin'], x['informant'], x['season'], x['external']
        # The roster belongs to Rival; the pair Noname vs Otro club does not include Rival.
        unrelated = repo.create_match(s, season_id=season.id, competition_id=x['competition'].id,
            round_name='J3', match_date=date(2026,9,26), home_team_id=x['own'].id,
            away_team_id=x['third'].id, created_by=a.id,
            status='published', kickoff_at=datetime(2026,9,26,17), schedule_status='confirmed')
        with pytest.raises(ValueError, match='no consta vinculado'):
            requests.create_request(s, actor_id=a.id, player_id=p.id, season_id=season.id,
                recipient_ids=[inf.id], question='Defensa del uno contra uno', target_match_id=unrelated.id)
        q=requests.create_request(s,actor_id=a.id,player_id=p.id,season_id=season.id,
            recipient_ids=[inf.id],question='Defensa del uno contra uno')
        later=requests.respond(s,actor_id=inf.id,request_id=q.id,result='later',note='La semana que viene')
        later2=requests.respond(s,actor_id=inf.id,request_id=q.id,result='later',note='Todavía no')
        assert later.id == later2.id and later2.note == 'Todavía no'
        assert len(requests.responses(s,q.id))==1
        assert requests.list_requests(s,season_id=season.id,reporter_id=inf.id)


def test_dd_can_audit_delete_wrong_unlinked_tracking_but_not_postmatch_source(session_factory):
    from models.entities import ScoutObservation
    from repositories import tracking
    with session_factory.begin() as s:
        x=_seed(s)
        admin, author, match, ev, player = x['admin'],x['informant'],x['own_match'],x['ev'],x['external']
        author.can_track_players=True
        standalone, created = tracking.get_or_create_match_observation(s,
            player_id=player.id,author_id=author.id,match_id=match.id)
        assert created
        with pytest.raises(PermissionError):
            tracking.delete_erroneous_observation(s,observation_id=standalone.id,
                actor_id=author.id,reason='Esta nota está mal')
        with pytest.raises(ValueError,match='ocho'):
            tracking.delete_erroneous_observation(s,observation_id=standalone.id,
                actor_id=admin.id,reason='error')
        # When linked to the postmatch the source cannot be removed by DD.
        linked = tracking.enrich_postmatch_evaluation(s,evaluation_id=ev.id,author_id=author.id)
        assert linked.id == standalone.id
        with pytest.raises(ValueError,match='postpartido'):
            tracking.delete_erroneous_observation(s,observation_id=linked.id,
                actor_id=admin.id,reason='Informe equivocado')
        assert s.get(ScoutObservation,standalone.id) is not None
        assert s.get(PlayerEvaluation,ev.id) is not None
