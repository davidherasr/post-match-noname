from pathlib import Path

from core.formations import available_lineup_player_ids

ROOT = Path(__file__).resolve().parents[1]


def test_release_406_contract():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.1.2"
    assert 'APP_VERSION = "4.1.2"' in (ROOT / "core/config.py").read_text(encoding="utf-8")
    assert 'REPORTS_PAGE_API_VERSION = "4.1.2"' in (ROOT / "views/reports.py").read_text(encoding="utf-8")


def test_lineup_picker_hides_players_selected_in_other_slots():
    roster = [1, 4, 6, 7, 8, 9, 10, 12]
    slots = [1, 4, 6, None]

    assert available_lineup_player_ids(roster, slots, 3) == [7, 8, 9, 10, 12]


def test_lineup_picker_keeps_own_current_player_available():
    roster = [1, 4, 6, 7]
    slots = [1, 4, 6, None]

    assert available_lineup_player_ids(roster, slots, 2) == [6, 7]


def test_lineup_editor_is_reactive_not_inside_a_form():
    body = (ROOT / "views/jornada.py").read_text(encoding="utf-8")
    start = body.index("def _formation_lineup_editor")
    end = body.index("def _neutral_match_study")
    editor = body[start:end]

    assert "available_lineup_player_ids" in editor
    assert "st.selectbox(" in editor
    assert "st.form(" not in editor
    assert "st.form_submit_button(" not in editor
    assert "Cada jugador seleccionado desaparece automáticamente" in editor
    assert "Un jugador no puede ocupar dos posiciones" in (ROOT / "repositories/matches.py").read_text(encoding="utf-8")
