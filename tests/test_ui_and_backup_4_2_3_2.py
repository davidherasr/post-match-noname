"""Regressions for live selection, Spanish admin UI, full-table technical export."""
from __future__ import annotations

from io import BytesIO
import ast
from types import SimpleNamespace
from pathlib import Path
import json
import zipfile

from models.base import Base
from services.export_service import technical_backup_zip
from repositories import permanent_deletion as purge

ROOT = Path(__file__).resolve().parents[1]


def _load_ui_function(relative_file, function, namespace):
    source = (ROOT / relative_file).read_text(encoding='utf-8')
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    # Run just the pure callback without importing Streamlit into the test process.
    node.decorator_list = []
    ns = dict(namespace)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / relative_file), 'exec'), ns)
    return ns[function]


def test_reporter_select_all_and_clear_callbacks():
    fake = SimpleNamespace(session_state={})
    callback = _load_ui_function('ui/selection.py', '_set_checks', {'st': fake})
    callback('reporters', [7, 13], True)
    assert fake.session_state == {'reporters_7': True, 'reporters_13': True}
    callback('reporters', [7, 13], False)
    assert not any(fake.session_state.values())


def test_purge_select_all_only_affects_visible_page():
    fake = SimpleNamespace(session_state={'purge_selected_jugadores_3': True})
    callback = _load_ui_function('views/permanent_deletion.py', '_mark_page', {'st': fake})
    selection = _load_ui_function('views/permanent_deletion.py', '_selection', {'st': fake, 'purge': purge})
    callback('jugadores', [4, 5], True)
    assert selection()['jugadores'] == [3, 4, 5]
    callback('jugadores', [4, 5], False)
    assert selection()['jugadores'] == [3]


def test_live_assignment_selector_is_not_buffered_inside_a_form():
    source = (ROOT / 'views/jornada.py').read_text(encoding='utf-8')
    block = source.split('def _manage_postmatch_assignments_4231(', 1)[1].split('def _render_match_hub(', 1)[0]
    assert 'reporter_checkboxes(' in block
    assert 'st.form(' not in block
    assert 'st.button("Guardar asignaciones y activar tareas"' in block
    assert 'disabled=not selected_ids' not in block
    assert "st.error(\"Selecciona al menos un Informador" in block
    deletion = (ROOT / 'views/permanent_deletion.py').read_text(encoding='utf-8')
    assert 'disabled=not ready' not in deletion
    assert 'Seleccionar todos los de esta página' in deletion
    assert 'suggestions[:50]' in deletion
    assert ' · ID ' not in deletion


def test_technical_export_includes_all_current_mapped_tables(session_factory):
    with session_factory() as session:
        content = technical_backup_zip(session)
    with zipfile.ZipFile(BytesIO(content)) as archive:
        assert set(archive.namelist()) == {'exportacion.json', 'LEEME.txt'}
        export = json.loads(archive.read('exportacion.json'))
        assert set(export['tables']) == set(Base.metadata.tables)
        assert export['table_count'] == len(Base.metadata.tables)
        notice = archive.read('LEEME.txt').decode('utf-8')
        assert 'NO es una copia SQL restaurable' in notice
        assert 'bucket' in notice


def test_brand_and_release_no_public_postmatch():
    from core.config import APP_NAME, APP_VERSION
    assert APP_NAME == 'No Name · Área Técnica'
    assert APP_VERSION == '4.4.3'
    assert 'PostMatch' not in (ROOT / 'app.py').read_text(encoding='utf-8')
