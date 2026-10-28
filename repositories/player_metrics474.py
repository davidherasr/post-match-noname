"""Optional factual individual statistics, with source and audit.
No grade is derived from passes/duels. Analyst-only, match-scoped and published.
"""
from __future__ import annotations
import json
from sqlalchemy import select
from models.entities import Match, SportingContribution47 as Contribution
from repositories import collaboration47 as collab, mobile472, publication473


def save_stats(session, *, actor_id, match_id, team_id, player_id,
               passes_complete, passes_total, duels_won, duels_total,
               source='Registro manual del analista'):
    person=collab._actor(session,actor_id)
    collab._reporter(session,actor_id)
    if person.participation_profile not in {'full','free'}:
        raise PermissionError('Estas estadísticas corresponden al perfil de analista.')
    m=session.get(Match,int(match_id))
    if not m or not publication473.is_open(session,m.id):
        raise PermissionError('El partido no está publicado.')
    choices,confirmed=mobile472.choices(session,match_id,team_id)
    if not confirmed or f'p:{int(player_id)}' not in {p['key'] for p in choices}:
        raise PermissionError('El jugador no consta como participante de este equipo.')
    values=[]
    for value in (passes_complete,passes_total,duels_won,duels_total):
        if isinstance(value,bool) or not isinstance(value,int) or value<0 or value>300:
            raise ValueError('Los datos deben ser enteros no negativos.')
        values.append(value)
    pc,pt,dw,dt=values
    if pc>pt or dw>dt:raise ValueError('Los éxitos no pueden superar los intentos.')
    source=str(source).strip()[:180]
    if len(source)<4:raise ValueError('Indica la procedencia de los datos.')
    old=None
    for row in session.scalars(select(Contribution).where(Contribution.author_id==actor_id,
        Contribution.match_id==m.id, Contribution.player_id==int(player_id),
        Contribution.kind=='individual')).all():
        try: data=json.loads(row.data_json or '{}')
        except (ValueError,TypeError):continue
        if data.get('source')=='metrics474' and row.status=='shared':old=row;break
    payload={'source':'metrics474','estadisticas':{'pases_correctos':pc,
        'pases_intentados':pt,'duelos_ganados':dw,'duelos_disputados':dt},
        'procedencia':source}
    if old and json.loads(old.data_json or '{}')==payload:return old
    return collab.save_contribution(session,actor_id=actor_id,season_id=m.season_id,
        kind='individual',match_id=m.id,team_id=int(team_id),player_id=int(player_id),
        title='Estadísticas individuales',data=payload,publish=True,
        contribution_id=old.id if old else None,
        expected_revision=old.revision if old else None,notify=False)
