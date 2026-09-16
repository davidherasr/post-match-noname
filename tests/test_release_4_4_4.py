"""4.4.4 regression coverage: DD navigation, selective interest, voluntary neutral reporting, honest UX."""
from __future__ import annotations

import ast
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from core.interest import explicitly_selected, qualifies_for_discovery
from models.entities import MatchOpinion, Report
from repositories import scouting as repo
from repositories import sporting_reading
from repositories import workspaces
from tests.test_release_4_4_3 import _seed

ROOT = Path(__file__).resolve().parents[1]


def test_interest_is_manual_and_discovery_discloses_sample():
    for state in (None, "Observado", "Descartado", "Sin decisión"):
        assert not explicitly_selected(decision_status=state)
    for state in ("Interesante", "Seguimiento", "Prioritario"):
        assert explicitly_selected(decision_status=state)
    assert explicitly_selected(has_open_request=True)
    assert explicitly_selected(has_formal_tracking=True)
    assert not qualifies_for_discovery({"weighted_rating": None, "match_count": 8})
    assert not qualifies_for_discovery({"weighted_rating": 7.99, "match_count": 8})
    assert not qualifies_for_discovery({"weighted_rating": 9, "match_count": 1})
    assert qualifies_for_discovery({"weighted_rating": 8.0, "match_count": 2})
    assert qualifies_for_discovery({"weighted_rating": 9, "match_count": 1}, minimum_matches=1)


def test_no_dd_widget_mutation_after_instantiation():
    tree = ast.parse((ROOT / "views/squad.py").read_text(encoding="utf-8"))
    render = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "render")
    widget_key = "dd_area_select_444"
    # Separate logical navigation and widget keys; on_click is a pre-render callback.
    source = ast.get_source_segment((ROOT / "views/squad.py").read_text(encoding="utf-8"), render)
    assert "on_change=_sync_dd_navigation" in source
    assert "on_click=_navigate_dd" in source
    assert 'key="dd_area_42"' not in source
    assert f'key="{widget_key}"' in source
    assert 'st.session_state["dd_area_42"] = "Jugadores de interés"' not in source
    assert 'st.session_state["dd_area_42"] = "Peticiones de opinión"' not in source


def test_calendar_navigation_uses_callback_and_season_reset():
    text = (ROOT / "views/jornada.py").read_text(encoding="utf-8")
    assert 'st.session_state.get("round_season_444") != active.id' in text
    assert "on_click=_set_round_444" in text
    assert "Primera jornada" in text and "Ir a la jornada actual" in text
    assert 'key="round_selected_444"' not in text or 'round_key = "round_selected_444"' in text


def test_neutral_submission_never_locked_by_checkbox_in_same_form():
    text = (ROOT / "views/jornada.py").read_text(encoding="utf-8")
    assert 'disabled=not confirm_viewed' not in text
    assert 'if not confirm_viewed:' in text
    assert "Realizar lectura voluntaria" in text
    assert "Tu lectura del partido" in text


def test_neutral_report_voluntary_no_assignment_and_no_own_false_report(session_factory):
    with session_factory.begin() as session:
        data = _seed(session)
        neutral = data["neutral"]
        author = data["other"]  # Not assigned to this neutral fixture.
        opinion = sporting_reading.save_neutral_opinion(session, match_id=neutral.id,
            user_id=author.id, home_team_rating=8.0, away_team_rating=None,
            summary="Lo vi en directo", player_rows=[])
        assert opinion.user_id == author.id and opinion.match_id == neutral.id
        again = sporting_reading.save_neutral_opinion(session, match_id=neutral.id,
            user_id=author.id, home_team_rating=7.0, away_team_rating=5.0,
            summary="Lectura actualizada", player_rows=[])
        assert again.id == opinion.id
        assert session.scalar(select(MatchOpinion).where(MatchOpinion.match_id == neutral.id,
            MatchOpinion.user_id == author.id)).home_team_rating == 7.0
        with pytest.raises(ValueError, match="No Name"):
            sporting_reading.save_neutral_opinion(session, match_id=data["own_match"].id,
                user_id=author.id, home_team_rating=9, away_team_rating=6,
                summary="No debe permitirse como neutral", player_rows=[])


def test_report_archive_round_filters_before_pagination(session_factory):
    with session_factory.begin() as session:
        data = _seed(session)
        admin, reporter, season, comp, own, rival = (
            data["admin"], data["informant"], data["season"], data["competition"],
            data["own"], data["rival"])
        first = data["report"]
        for day in range(1, 19):
            match = repo.create_match(session, season_id=season.id, competition_id=comp.id,
                round_name=f"Jornada {day}", match_date=date(2026, 10, day),
                home_team_id=own.id, away_team_id=rival.id, created_by=admin.id,
                status="published", kickoff_at=datetime(2026, 10, day, 18), schedule_status="confirmed")
            repo.assign_reporters(session, match.id, [reporter.id], admin.id)
            repo.get_or_create_report(session, match.id, reporter.id)
        original = repo.list_reports(session, reporter_id=reporter.id,
            round_name="J1", limit=1)
        # Search 'J1' is specific to the original seed, not a post-limit filter.
        assert original and original[0].id == first.id
        assert repo.list_reports(session, reporter_id=reporter.id, round_name="J1", limit=1, offset=1) == []
        assert len(repo.list_reports(session, reporter_id=reporter.id, season_id=season.id,
                                    round_name="Jornada 1", limit=10)) == 1


def test_visual_regressions_pdf_mobile_and_no_duplicate_archive_select():
    css = (ROOT / "ui/styles.py").read_text()
    pitch = (ROOT / "ui/match_study.py").read_text()
    pdf = (ROOT / "reports/player_report_pdf.py").read_text()
    archive = (ROOT / "views/reports.py").read_text()
    assert 'grid-template-columns:1fr;' in css
    assert 'var(--pm-primary,' in pitch
    assert 'row.get("note")' in pdf and 'note).replace("\\n", "<br/>")' in pdf
    assert 'offset=(page-1) * page_size' in archive
    assert 'st.session_state["archive_open_report_33"] = item.id' in archive
    assert 'round_name=round_query' in archive
