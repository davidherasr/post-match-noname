"""Administration-only multi-record purge, previewed against the live FK graph."""
from __future__ import annotations

import streamlit as st
from sqlalchemy import func, or_, select

from core.database import session_scope
from core.permissions import can_admin
from models.entities import Match, Player, Season, Team
from repositories import permanent_deletion as purge

PAGE_SIZE = 40
ENTITY_TYPES = (
    ('temporadas', Season, 'name'),
    ('partidos', Match, 'round_name'),
    ('equipos', Team, 'name'),
    ('jugadores', Player, 'full_name'),
)


def _label(kind: str, item) -> str:
    if kind == 'temporadas':
        return item.name + (' · Temporada activa' if item.active else '')
    if kind == 'equipos':
        suffix = ' · EQUIPO PROPIO' if item.is_own_team else ''
        return f'{item.name}{suffix}'
    if kind == 'partidos':
        return (f'{item.match_date} · {item.round_name} · '
                f'{item.home_team.name} – {item.away_team.name} · {item.status}')
    return f'{item.full_name} · {item.primary_position or "Sin posición"}' + (f' · {item.date_of_birth}' if item.date_of_birth else '')


def _mark_page(kind: str, identifiers: list[int], selected: bool) -> None:
    """Called before widgets render, avoiding a Streamlit session-state exception."""
    for ident in identifiers:
        st.session_state[f'purge_selected_{kind}_{ident}'] = selected


def _clear_selection() -> None:
    """Global reset runs before any selection widget is constructed."""
    for key in list(st.session_state):
        if key.startswith('purge_selected_'):
            st.session_state[key] = False
    st.session_state.pop('purge_preview', None)


def _selection() -> dict[str, list[int]]:
    result = {}
    for kind in purge.ROOTS:
        prefix = f'purge_selected_{kind}_'
        result[kind] = sorted(int(key[len(prefix):]) for key, checked in st.session_state.items()
                              if key.startswith(prefix) and checked and key[len(prefix):].isdigit())
    return result


def _rows(session, kind, model, field, search, page):
    condition = None
    if search:
        if kind == 'partidos':
            condition = or_(Match.round_name.ilike(f'%{search}%'),
                            Match.home_team.has(Team.name.ilike(f'%{search}%')),
                            Match.away_team.has(Team.name.ilike(f'%{search}%')))
        else:
            condition = getattr(model, field).ilike(f'%{search}%')
    query = select(model)
    count_query = select(func.count(model.id))
    if condition is not None:
        query = query.where(condition)
        count_query = count_query.where(condition)
    total = int(session.scalar(count_query) or 0)
    items = session.scalars(query.order_by(model.id).offset((page-1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    return items, total


def render(user: dict) -> None:
    if not can_admin(user):
        st.error('No tienes permiso para gestionar eliminaciones.'); return
    for pid in st.session_state.pop('purge_add_pending', []):
        st.session_state[f'purge_selected_jugadores_{pid}'] = True
    st.markdown('### Eliminación definitiva de registros')
    st.caption('Marca uno o varios elementos. Antes de borrar verás cuántos datos relacionados '
               'se eliminarán y qué referencias se conservarán sin vinculación.')
    st.warning('Esta operación no se puede deshacer. Antes de continuar necesitas una copia íntegra '
               'y verificable de PostgreSQL y, cuando existan documentos, del almacenamiento externo.')

    tabs = st.tabs(['Temporadas', 'Partidos', 'Equipos', 'Jugadores'])
    for tab, (kind, model, field) in zip(tabs, ENTITY_TYPES):
        with tab:
            search = st.text_input('Buscar', key=f'purge_filter_{kind}',
                                   placeholder='Filtrar registros por nombre, partido o equipo')
            page = int(st.number_input('Página', min_value=1, value=1, step=1,
                                       key=f'purge_page_{kind}', help=f'{PAGE_SIZE} registros por página. '
                                       'Las casillas seleccionadas se conservan al cambiar de página.'))
            with session_scope() as session:
                items, total = _rows(session, kind, model, field, search.strip(), page)
                labels = [(item.id, _label(kind, item)) for item in items]
            st.caption(f'{total} registros encontrados · página {page}. La selección se conserva al cambiar de página.')
            if labels:
                ids_on_page = [ident for ident, _ in labels]
                a, b = st.columns(2)
                a.button('Seleccionar todos los de esta página', key=f'purge_select_page_{kind}_{page}',
                         use_container_width=True, on_click=_mark_page, args=(kind, ids_on_page, True))
                b.button('Quitar selección de esta página', key=f'purge_clear_page_{kind}_{page}',
                         use_container_width=True, on_click=_mark_page, args=(kind, ids_on_page, False))
            for ident, label in labels:
                st.checkbox(label, key=f'purge_selected_{kind}_{ident}')
            if not labels:
                st.info('No hay registros en esta página. Ajusta los filtros o la página.')

    roots = _selection()
    selected_count = sum(map(len, roots.values()))
    st.divider()
    st.markdown(f'**Selección actual: {selected_count} registros**')
    if selected_count:
        st.button('Quitar toda la selección', key='purge_clear_all', on_click=_clear_selection)
    if selected_count:
        st.caption(' · '.join(f'{kind}: {len(ids)}' for kind, ids in roots.items() if ids))
    if st.button('Analizar dependencias y preparar eliminación', disabled=not selected_count,
                 key='purge_prepare', use_container_width=True):
        try:
            with session_scope() as session:
                plan = purge.build_plan(session, roots, user['id'])
                suggestions = purge.orphan_player_suggestions(session, plan)
            st.session_state['purge_preview'] = {'roots': roots, 'fingerprint': plan.fingerprint,
                                                  'suggestions': suggestions}
        except Exception as exc:
            st.session_state.pop('purge_preview', None)
            st.error(str(exc))

    preview = st.session_state.get('purge_preview')
    if not preview:
        return
    if roots != preview['roots']:
        st.info('Has cambiado la selección. Vuelve a analizar las dependencias para confirmar el nuevo alcance.')
        return
    try:
        with session_scope() as session:
            plan = purge.build_plan(session, preview['roots'], user['id'])
    except Exception as exc:
        st.error(str(exc)); return
    if plan.fingerprint != preview['fingerprint']:
        st.error('Los datos cambiaron después del análisis. Actualiza la vista previa antes de continuar.')
        return
    st.markdown('#### Impacto completo de la eliminación')
    st.metric('Filas de base de datos que se eliminarán', plan.total)
    for table, ids in sorted(plan.rows.items()):
        st.write(f'• {purge.LABELS.get(table, table)}: **{len(ids)}**')
    if plan.detach:
        st.markdown('**Referencias que se desvincularán sin borrar el registro:**')
        for (table, column), ids in sorted(plan.detach.items()):
            st.caption(f'{purge.LABELS.get(table, table)} · {len(ids)} registros conservados con referencia desvinculada')
    if plan.settings:
        st.warning('Se dejarán sin configurar estos ajustes, porque apuntan a registros seleccionados: '
                   + ', '.join('temporada activa' if key == 'active_season_id' else 'equipo propio' if key == 'own_team_id' else key for key in plan.settings))
    if 'teams' in plan.rows and any(i in plan.rows['teams'] for i in preview['roots'].get('equipos', [])):
        st.caption('Al borrar equipos, sus partidos y plantillas desaparecen. Los jugadores son identidades '
                   'independientes; selecciona también aquellos que quieras eliminar.')
    suggestions = preview.get('suggestions') or []
    if suggestions:
        with st.expander(f'Jugadores sin otras referencias detectadas ({len(suggestions)})', expanded=False):
            st.caption('Se trata de jugadores cuyas plantillas y partidos se eliminarán. Comprueba los nombres antes de incluirlos; no se seleccionan automáticamente.')
            for pid, name in suggestions[:50]:
                st.write(name)
            if len(suggestions) > 50:
                st.caption('Se muestran los primeros 50. Para seleccionar otros, utiliza la pestaña Jugadores.')
            if st.button('Seleccionar estos jugadores y volver a analizar', key='purge_include_orphans'):
                st.session_state['purge_add_pending'] = [pid for pid, _ in suggestions[:50]]
                st.session_state.pop('purge_preview', None)
                st.rerun()
    if plan.external_files:
        st.error(f'Hay {len(plan.external_files)} archivos referenciados en almacenamiento externo/local. '
                 'El borrado de filas NO elimina los bytes del bucket o del disco. '
                 'Conserva sus rutas para depurarlas mediante el procedimiento de almacenamiento.')
        with st.expander('Rutas de documentos afectados', expanded=False):
            for bucket, path in plan.external_files:
                st.code(f'{bucket}: {path}', language='text')
    st.caption('Se conserva un registro administrativo de la operación, '
               'pero los registros deportivos y dependencias indicados desaparecerán físicamente.')
    with st.form('purge_confirm_form', border=True):
        backed_up = st.checkbox('Confirmo que ya dispongo de un backup COMPLETO de PostgreSQL '
                               'y del almacenamiento documental necesario, y he revisado el impacto.')
        phrase = st.text_input('Para confirmar, escribe ELIMINAR DEFINITIVAMENTE',
                               help='La selección no se puede recuperar sin restaurar una copia de seguridad.')
        ready = backed_up and phrase.strip() == 'ELIMINAR DEFINITIVAMENTE'
        # A Streamlit form batches checkbox/text changes; a disabled submit button
        # cannot react to those changes until the form is submitted. Validate then.
        proceed = st.form_submit_button('Eliminar definitivamente los registros seleccionados',
                                        type='primary', use_container_width=True)
    if proceed:
        if not ready:
            st.error('Para eliminar, confirma el backup y escribe la frase exacta.')
            return
        try:
            with session_scope() as session:
                deleted = purge.execute_plan(session, preview['roots'], user['id'], preview['fingerprint'])
            for key in [key for key in st.session_state if key.startswith('purge_selected_')]:
                st.session_state.pop(key, None)
            st.session_state.pop('purge_preview', None)
            st.success(f'Eliminación realizada: {sum(deleted.values())} filas. Revisa las rutas de archivos externos si se mostraron.')
            st.rerun()
        except Exception as exc:
            st.error(f'Eliminación cancelada sin confirmar cambios: {exc}')
