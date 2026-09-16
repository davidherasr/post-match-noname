"""4.2.3 · SQL-filtered, paged player catalogue. No hidden pre-filter cap."""
from __future__ import annotations

from sqlalchemy import Integer, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from core.presentation import normalize_player_state
from models.entities import (Match, MatchOpinion, MatchOpinionPlayer, Player,
    PlayerEvaluation, PlayerSeasonDecision, Report, ScoutObservation,
    ScoutedPlayerProfile, Team, TeamRoster)
from repositories.common import FINAL_REPORT_STATUSES
from repositories.data_governance import official_match_clause, official_team_clause
from repositories.players import get_own_team

PAGE_SIZE = 20


def teams_for_filter(session: Session, season_id: int | None):
    stmt = select(Team).where(official_team_clause(), Team.active.is_(True))
    if season_id:
        stmt = stmt.where(Team.id.in_(select(TeamRoster.team_id).where(TeamRoster.season_id == int(season_id))))
    return list(session.scalars(stmt.order_by(Team.name)).all())


def search_players(session: Session, *, season_id: int | None,
                   search: str = '', position: str | None = None,
                   team_id: int | str | None = None, scope: str = 'Todos',
                   state_filter: str = 'Todos', evidence: str = 'Cualquiera',
                   order: str = 'Nombre', page: int = 1, page_size: int = PAGE_SIZE) -> dict:
    season = int(season_id) if season_id else None
    own = get_own_team(session)
    official_roster = (select(TeamRoster.player_id)
        .join(Team, Team.id == TeamRoster.team_id)
        .where(TeamRoster.active.is_(True), official_team_clause()))
    all_roster = select(TeamRoster.player_id).where(TeamRoster.active.is_(True))
    if season:
        official_roster = official_roster.where(TeamRoster.season_id == season)
        all_roster = all_roster.where(TeamRoster.season_id == season)

    report_players = (select(PlayerEvaluation.player_id)
        .join(Report, Report.id == PlayerEvaluation.report_id)
        .join(Match, Match.id == Report.match_id)
        .where(official_match_clause(), Report.status.in_(FINAL_REPORT_STATUSES),
               PlayerEvaluation.observation_status == 'evaluated',
               PlayerEvaluation.general_rating.is_not(None), PlayerEvaluation.general_rating > 0))
    signal_players = (select(MatchOpinionPlayer.player_id)
        .join(MatchOpinion, MatchOpinion.id == MatchOpinionPlayer.opinion_id)
        .join(Match, Match.id == MatchOpinion.match_id)
        .where(official_match_clause()))
    tracking_players = (select(ScoutedPlayerProfile.player_id)
        .join(ScoutObservation, ScoutObservation.profile_id == ScoutedPlayerProfile.id)
        .where(ScoutObservation.status == 'submitted',
               or_(ScoutObservation.match_id.is_(None),
                   ScoutObservation.match_id.in_(select(Match.id).where(official_match_clause())))))
    if season:
        report_players = report_players.where(Match.season_id == season)
        signal_players = signal_players.where(Match.season_id == season)
        # formal tracking is a cumulative dossier; don't assign unknown matchless work to any season
        tracking_players = tracking_players.where(ScoutObservation.match_id.in_(
            select(Match.id).where(official_match_clause(), Match.season_id == season)))
    stmt = select(Player.id).where(Player.active.is_(True), Player.merged_into_id.is_(None))
    # Exclude players found exclusively in marked-test/archived rosters, without
    # hiding legitimate free agents who never had any roster.
    stmt = stmt.where(or_(Player.id.in_(official_roster), ~Player.id.in_(all_roster)))
    if search.strip():
        term = '%' + search.strip() + '%'
        stmt = stmt.where(or_(Player.full_name.ilike(term), Player.display_name.ilike(term)))
    if position:
        stmt = stmt.where(Player.primary_position == position)
    if team_id == 'Sin equipo':
        stmt = stmt.where(~Player.id.in_(all_roster))
    elif team_id is not None:
        selected = select(TeamRoster.player_id).where(
            TeamRoster.team_id == int(team_id), TeamRoster.active.is_(True))
        if season: selected = selected.where(TeamRoster.season_id == season)
        stmt = stmt.where(Player.id.in_(selected), Player.id.in_(official_roster))
    if scope in {'Propios', 'Externos'}:
        if own is None:
            stmt = stmt.where(Player.id == -1)
        else:
            own_players = select(TeamRoster.player_id).where(TeamRoster.team_id == own.id, TeamRoster.active.is_(True))
            if season: own_players = own_players.where(TeamRoster.season_id == season)
            stmt = stmt.where(Player.id.in_(own_players) if scope == 'Propios' else ~Player.id.in_(own_players))
    decision_ids = select(PlayerSeasonDecision.player_id)
    if season: decision_ids = decision_ids.where(PlayerSeasonDecision.season_id == season)
    if state_filter == 'Sin decisión':
        stmt = stmt.where(~Player.id.in_(decision_ids))
    elif state_filter in {'Observado','Interesante','Seguimiento','Prioritario','Descartado'}:
        matching_decisions = select(PlayerSeasonDecision.player_id).where(PlayerSeasonDecision.status == state_filter)
        if season: matching_decisions = matching_decisions.where(PlayerSeasonDecision.season_id == season)
        stmt = stmt.where(Player.id.in_(matching_decisions))
    elif state_filter == 'Destacados':
        highlighted = (select(PlayerEvaluation.player_id).join(Report, Report.id == PlayerEvaluation.report_id)
            .join(Match, Match.id == Report.match_id)
            .where(official_match_clause(), Report.status.in_(FINAL_REPORT_STATUSES), PlayerEvaluation.standout.is_(True)))
        if season: highlighted = highlighted.where(Match.season_id == season)
        stmt = stmt.where(Player.id.in_(highlighted))
    elif state_filter == 'Con observaciones':
        stmt = stmt.where(Player.id.in_(tracking_players))
    if evidence == 'Postpartidos': stmt = stmt.where(Player.id.in_(report_players))
    elif evidence == 'Señales neutrales': stmt = stmt.where(Player.id.in_(signal_players))
    elif evidence == 'Seguimiento formal': stmt = stmt.where(Player.id.in_(tracking_players))
    elif evidence == 'Sin valoraciones': stmt = stmt.where(~Player.id.in_(report_players), ~Player.id.in_(signal_players))

    rated_count = (select(func.count(PlayerEvaluation.id)).join(Report, Report.id == PlayerEvaluation.report_id)
        .join(Match, Match.id == Report.match_id)
        .where(PlayerEvaluation.player_id == Player.id, official_match_clause(),
               Report.status.in_(FINAL_REPORT_STATUSES), PlayerEvaluation.general_rating > 0).correlate(Player).scalar_subquery())
    last_rating = (select(func.max(Match.match_date)).join(Report, Report.match_id == Match.id)
        .join(PlayerEvaluation, PlayerEvaluation.report_id == Report.id)
        .where(PlayerEvaluation.player_id == Player.id, official_match_clause(),
               Report.status.in_(FINAL_REPORT_STATUSES)).correlate(Player).scalar_subquery())
    order_by = {
        'Nombre': [Player.full_name, Player.id],
        'Posición': [Player.primary_position.nullslast(), Player.full_name],
        'Partidos evaluados': [desc(rated_count), Player.full_name],
        'Última evaluación': [desc(last_rating), Player.full_name],
    }.get(order, [Player.full_name, Player.id])
    total = int(session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    per_page = max(1, min(int(page_size), 100))
    pages = max(1, (total + per_page - 1) // per_page)
    current = min(max(1, int(page)), pages)
    ids = list(session.scalars(select(Player.id).where(Player.id.in_(stmt)).order_by(*order_by)
                  .offset((current-1)*per_page).limit(per_page)).all())
    if not ids:
        return {'rows': [], 'total': total, 'page': current, 'pages': pages}
    players = {p.id:p for p in session.scalars(select(Player).where(Player.id.in_(ids))).all()}
    rosters = (select(TeamRoster).options(joinedload(TeamRoster.team))
        .join(Team, Team.id == TeamRoster.team_id)
        .where(TeamRoster.player_id.in_(ids), TeamRoster.active.is_(True), official_team_clause())
        .order_by(desc(TeamRoster.updated_at), desc(TeamRoster.id)))
    if season: rosters = rosters.where(TeamRoster.season_id == season)
    team_map = {}
    for row in session.scalars(rosters).unique().all():
        team_map.setdefault(row.player_id, row.team)
    decisions = select(PlayerSeasonDecision).where(PlayerSeasonDecision.player_id.in_(ids))
    if season: decisions = decisions.where(PlayerSeasonDecision.season_id == season)
    decision_map = {d.player_id:d for d in session.scalars(decisions).all()}
    rated = (select(PlayerEvaluation.player_id, func.avg(PlayerEvaluation.general_rating),
                    func.count(PlayerEvaluation.id), func.count(func.distinct(Match.id)),
                    func.count(func.distinct(Report.reporter_id)), func.max(Match.match_date),
                    func.sum(func.cast(PlayerEvaluation.standout, Integer)))
        .join(Report, Report.id == PlayerEvaluation.report_id)
        .join(Match, Match.id == Report.match_id)
        .where(PlayerEvaluation.player_id.in_(ids), official_match_clause(),
               Report.status.in_(FINAL_REPORT_STATUSES),
               PlayerEvaluation.observation_status == 'evaluated', PlayerEvaluation.general_rating > 0)
        .group_by(PlayerEvaluation.player_id))
    if season: rated = rated.where(Match.season_id == season)
    ratings = {row[0]:row for row in session.execute(rated).all()}
    signals = (select(MatchOpinionPlayer.player_id, func.count(MatchOpinionPlayer.id),
                    func.count(func.distinct(Match.id)), func.count(func.distinct(MatchOpinion.user_id)))
        .join(MatchOpinion, MatchOpinion.id == MatchOpinionPlayer.opinion_id)
        .join(Match, Match.id == MatchOpinion.match_id)
        .where(MatchOpinionPlayer.player_id.in_(ids), official_match_clause())
        .group_by(MatchOpinionPlayer.player_id))
    if season: signals = signals.where(Match.season_id == season)
    signal_map = {row[0]:row for row in session.execute(signals).all()}
    tracking = (select(ScoutedPlayerProfile.player_id, func.count(ScoutObservation.id))
        .join(ScoutObservation, ScoutObservation.profile_id == ScoutedPlayerProfile.id)
        .where(ScoutedPlayerProfile.player_id.in_(ids), ScoutObservation.status == 'submitted',
              or_(ScoutObservation.match_id.is_(None), ScoutObservation.match_id.in_(select(Match.id).where(official_match_clause()))))
        .group_by(ScoutedPlayerProfile.player_id))
    if season: tracking = tracking.where(ScoutObservation.match_id.in_(select(Match.id).where(official_match_clause(), Match.season_id == season)))
    track_map = dict(session.execute(tracking).all())
    output = []
    for pid in ids:
        player = players[pid]
        dec = decision_map.get(pid)
        row = ratings.get(pid)
        sig = signal_map.get(pid)
        output.append({'player':player, 'team':team_map.get(pid), 'state':normalize_player_state(dec.status) if dec else 'Sin decisión',
            'priority':dec.priority if dec else None,
            'rating':round(float(row[1]),2) if row and row[1] is not None else None,
            'postmatch_count':int(row[2]) if row else 0, 'match_count':int(row[3]) if row else 0,
            'authors':int(row[4]) if row else 0, 'latest':row[5] if row else None,
            'standouts':int(row[6] or 0) if row else 0,
            'neutral_mentions':int(sig[1]) if sig else 0,
            'neutral_matches':int(sig[2]) if sig else 0,
            'neutral_authors':int(sig[3]) if sig else 0,
            'tracking_count':int(track_map.get(pid,0) or 0),
            'scope':'Propio' if own and team_map.get(pid) and team_map[pid].id == own.id else 'Externo' if team_map.get(pid) else 'Sin equipo'})
    return {'rows':output, 'total':total, 'page':current, 'pages':pages}
