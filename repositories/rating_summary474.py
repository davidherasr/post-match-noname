"""One canonical view of active per-player grades across all retained models.

One observation per (player, match, author). New published individual grades
supersede historic opinions/reports; draft/retracted grades never count. No
arbitrary LIMIT affects averages. Result is access-filtered in the SQL layer.
"""
from __future__ import annotations
import json
from collections import defaultdict
from sqlalchemy import select
from models.entities import (Match, PlayerEvaluation, Report, MatchOpinion,
    MatchOpinionPlayer, SportingContribution47, Player)
from repositories.common import FINAL_REPORT_STATUSES
from repositories.users import user_has_role


def observations(session, *, actor_id:int, season_id:int, player_ids=None):
    ids=set(map(int,player_ids)) if player_ids is not None else None
    privileged=user_has_role(session,actor_id,'director','admin')
    data={}
    base=select(PlayerEvaluation,Report,Match).join(Report,Report.id==PlayerEvaluation.report_id).join(
        Match,Match.id==Report.match_id).where(Match.season_id==season_id,
        Report.status.in_(FINAL_REPORT_STATUSES))
    if ids is not None:base=base.where(PlayerEvaluation.player_id.in_(ids))
    if not privileged:base=base.where(Report.reporter_id==actor_id)
    for ev,rep,m in session.execute(base):
        if ev.general_rating is not None and 1<=float(ev.general_rating)<=10:
            key=(ev.player_id,m.id,rep.reporter_id)
            data[key]=(m.match_date,float(ev.general_rating),'informe histórico')
    opinions=select(MatchOpinionPlayer,MatchOpinion,Match).join(
        MatchOpinion,MatchOpinion.id==MatchOpinionPlayer.opinion_id).join(
        Match,Match.id==MatchOpinion.match_id).where(Match.season_id==season_id)
    if ids is not None:opinions=opinions.where(MatchOpinionPlayer.player_id.in_(ids))
    if not privileged:opinions=opinions.where(MatchOpinion.user_id==actor_id)
    for ev,op,m in session.execute(opinions):
        if ev.rating is not None and 1<=float(ev.rating)<=10:
            data.setdefault((ev.player_id,m.id,op.user_id),
                 (m.match_date,float(ev.rating),'valoración histórica'))
    modern=select(SportingContribution47,Match).join(
        Match,Match.id==SportingContribution47.match_id).where(
        SportingContribution47.status.in_(['shared','retracted']),
        SportingContribution47.kind=='individual',
        SportingContribution47.player_id.is_not(None),Match.season_id==season_id)
    if ids is not None:modern=modern.where(SportingContribution47.player_id.in_(ids))
    if not privileged:modern=modern.where(SportingContribution47.author_id==actor_id)
    modern=modern.order_by(SportingContribution47.updated_at,SportingContribution47.id)
    for note,m in session.execute(modern):
        key=(note.player_id,m.id,note.author_id)
        if note.status=='retracted':
            data.pop(key,None)
            continue
        try: payload=json.loads(note.data_json or '{}');score=payload.get('nota')
        except (ValueError,TypeError):continue
        if isinstance(score,(int,float)) and not isinstance(score,bool) and 1<=score<=10:
            data[key]=(m.match_date,float(score),'valoración individual')
    return data


def summary_for(observations_map,player_id):
    player_notes={(mid,author):value for (pid,mid,author),value in observations_map.items() if pid==player_id}
    matches=defaultdict(list)
    for (mid,_),(when,score,source) in player_notes.items():matches[mid].append((when,score,source))
    ordered=sorted(((min(x[0] for x in group),mid,sum(x[1] for x in group)/len(group))
        for mid,group in matches.items()),key=lambda x:(x[0],x[1]))
    grades=[v[1] for v in player_notes.values()]
    trend='—'
    if len(ordered)>=4:
        n=len(ordered)//2
        delta=sum(x[2] for x in ordered[-n:])/n - sum(x[2] for x in ordered[:n])/n
        trend='Mejora' if delta>=.8 else 'Baja' if delta<=-.8 else 'Estable'
    return {'matches':len(matches),'opinions':len(grades),
        'average':sum(grades)/len(grades) if grades else None,
        'trend':trend,'history':ordered}
