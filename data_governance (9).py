"""Admin-only governance of own team and explicitly selected test data (4.2.3)."""
from __future__ import annotations

import streamlit as st
from core.database import session_scope
from core.permissions import can_admin
from repositories import players as players_repo
from repositories import matches as matches_repo
from repositories import data_governance as governance


def render(user: dict) -> None:
    if not can_admin(user):
        st.error('Solo Administración puede gestionar datos de prueba y equipo propio.')
        return
    st.markdown('### Identidad deportiva y datos de prueba')
    st.caption('Selecciona los registros exactos. Los cambios quedan auditados y no alteran valoraciones existentes.')
    with session_scope() as session:
        teams = players_repo.list_teams(session)
        own = players_repo.get_own_team(session)
        configured = players_repo.get_setting(session, 'own_team_id')
        flagged_ids = {t.id for t in teams if t.is_own_team}
    by_id = {t.id: t for t in teams}
    st.markdown('#### Equipo propio')
    if own and (configured != str(own.id) or flagged_ids != {own.id}):
        st.warning('La configuración del equipo propio presenta referencias distintas. Confirma el equipo correcto para sincronizarlas.')
    st.write(f'**Equipo propio actual:** {own.name}' if own else 'No hay equipo propio válido. Selecciona el registro real ya existente.')
    candidates = [t.id for t in teams if t.active and not t.is_test and t.archived_at is None]
    if candidates:
        target_id = st.selectbox('Seleccionar equipo propio', candidates,
                                 index=candidates.index(own.id) if own and own.id in candidates else 0,
                                 format_func=lambda tid: by_id[tid].name, key='gov_own_423')
        st.caption('No se crearán clubes nuevos, ni se reasignarán partidos, jugadores o informes históricos.')
        if st.button('Confirmar equipo propio', disabled=bool(own and own.id == target_id and configured == str(target_id) and flagged_ids == {target_id}), key='gov_set_own_423'):
            try:
                with session_scope() as session:
                    players_repo.set_own_team(session, target_id, user['id'])
                st.session_state.pop('noname_postmatch_context', None)
                st.success('Equipo propio actualizado correctamente.'); st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        st.warning('No hay equipos activos disponibles. Revisa el catálogo y restaura registros válidos si corresponde.')
    st.divider()
    st.markdown('#### Equipos de prueba / archivados')
    if not teams:
        st.info('No hay equipos.'); return
    team_id = st.selectbox('Inspeccionar equipo', [t.id for t in teams],
                           format_func=lambda tid: by_id[tid].name + (' · ARCHIVADO' if by_id[tid].archived_at else '') + (' · PRUEBA' if by_id[tid].is_test else ''),
                           key='gov_team_423')
    with session_scope() as session:
        selected_team = session.get(type(teams[0]), team_id)
        deps = governance.team_dependencies(session, team_id)
        team_is_test = bool(selected_team.is_test)
        team_archived = selected_team.archived_at is not None
        is_own = bool(selected_team.is_own_team or (own and team_id == own.id))
    st.write(f'**{by_id[team_id].name}**')
    st.caption('Dependencias existentes (no se borran): ' + ' · '.join(f'{label}: {count}' for label, count in deps.items()))
    if is_own:
        st.warning('Equipo propio protegido. No puede marcarse como prueba ni archivarse.')
    elif team_archived:
        if st.button('Restaurar equipo archivado', key='gov_restore_team_423'):
            try:
                with session_scope() as session:
                    governance.restore_team(session, team_id, user['id'])
                st.success('Equipo restaurado (permanece etiquetado como prueba hasta que decidas lo contrario).'); st.rerun()
            except Exception as exc: st.error(str(exc))
    else:
        if st.button('Marcar como real' if team_is_test else 'Marcar como equipo de prueba', key='gov_mark_team_423'):
            try:
                with session_scope() as session:
                    governance.mark_team_test(session, team_id, user['id'], not team_is_test)
                st.success('Clasificación actualizada.'); st.rerun()
            except Exception as exc: st.error(str(exc))
        if team_is_test:
            confirm_team = st.checkbox(f'Confirmo que quiero archivar {by_id[team_id].name} y conservar sus datos.', key=f'gov_confirm_team_{team_id}')
            if st.button('Archivar equipo de prueba', disabled=not confirm_team, key='gov_archive_team_423'):
                try:
                    with session_scope() as session:
                        governance.archive_team(session, team_id, user['id'])
                    st.success('Equipo archivado y excluido de los resultados oficiales.'); st.rerun()
                except Exception as exc: st.error(str(exc))
    st.divider()
    st.markdown('#### Partidos de prueba / archivados')
    with session_scope() as session:
        all_matches = matches_repo.list_matches(session, include_archived=True, limit=2000)
    related = [m for m in all_matches if team_id in {m.home_team_id, m.away_team_id}]
    st.caption(f'{len(related)} encuentros asociados al equipo seleccionado. Solo se modifica el partido que confirmes.')
    show = related if related else all_matches
    if not show:
        st.info('No hay partidos registrados.'); return
    matches = {m.id:m for m in show}
    match_id = st.selectbox('Inspeccionar encuentro', list(matches),
        format_func=lambda mid: f'{matches[mid].match_date} · {matches[mid].home_team.name} - {matches[mid].away_team.name} · {matches[mid].round_name}' + (' · ARCHIVADO' if matches[mid].deleted_at else '') + (' · PRUEBA' if matches[mid].is_test else ''),
        key=f'gov_match_{team_id}_423')
    with session_scope() as session:
        deps = governance.match_dependencies(session, match_id)
        match = matches_repo.get_match(session, match_id)
        is_test, archived = bool(match.is_test), bool(match.deleted_at is not None)
        restorable = archived and bool(match.archived_previous_status)
    st.write(f'**{match.home_team.name} – {match.away_team.name}** · {match.match_date} · {match.round_name}')
    st.caption('Dependencias conservadas: ' + ' · '.join(f'{label}: {count}' for label, count in deps.items()))
    if archived:
        if restorable and st.button('Restaurar partido archivado', key=f'gov_restore_match_{match_id}'):
            try:
                with session_scope() as session: governance.restore_test_match(session, match_id, user['id'])
                st.success('Partido restaurado; sigue siendo prueba hasta desmarcarlo explícitamente.'); st.rerun()
            except Exception as exc: st.error(str(exc))
        elif not restorable:
            st.warning('Archivo de una versión anterior sin estado previo registrado; no se restaura automáticamente para no inventar su estado.')
    else:
        if st.button('Marcar como real' if is_test else 'Marcar como partido de prueba', key=f'gov_mark_match_{match_id}'):
            try:
                with session_scope() as session: governance.mark_match_test(session, match_id, user['id'], not is_test)
                st.success('Clasificación del partido actualizada.'); st.rerun()
            except Exception as exc: st.error(str(exc))
        if is_test:
            confirm = st.checkbox(f'Confirmo el archivado reversible de {match.home_team.name} – {match.away_team.name} del {match.match_date}.', key=f'gov_confirm_match_{match_id}')
            if st.button('Archivar este partido de prueba', disabled=not confirm, key=f'gov_archive_match_{match_id}'):
                try:
                    with session_scope() as session: governance.archive_test_match(session, match_id, user['id'])
                    st.success('Partido archivado. Se conserva el histórico y se excluye de indicadores oficiales.'); st.rerun()
                except Exception as exc: st.error(str(exc))
