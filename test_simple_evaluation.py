from __future__ import annotations

from core.evaluation_rules import derive_simple_evaluation_state
from repositories import scouting as repo

from test_repository_flow import seed


def test_zero_is_not_observed_and_pdf_can_remain_preselected():
    state = derive_simple_evaluation_state(0, pdf_include=True)
    assert state.observation_status == "not_observed"
    assert state.general_rating is None
    assert state.pdf_include is True
    assert state.standout is False


def test_positive_rating_is_valid_and_eight_is_automatic_standout():
    ordinary = derive_simple_evaluation_state(7.5, pdf_include=False)
    highlighted = derive_simple_evaluation_state(8.0, pdf_include=False)
    assert ordinary.observation_status == "evaluated"
    assert ordinary.pdf_include is True
    assert ordinary.standout is False
    assert highlighted.standout is True


def test_manual_checkbox_overrides_are_respected():
    state = derive_simple_evaluation_state(
        9.0,
        pdf_include=False,
        standout=False,
        pdf_manually_changed=True,
        standout_manually_changed=True,
    )
    assert state.pdf_include is False
    assert state.standout is False


def test_report_can_be_submitted_without_general_overview_and_mvp_is_synced(session_factory):
    with session_factory.begin() as session:
        _, reporter, _, _, _, _, rival, _, rival_player, match = seed(session)
        report = repo.get_or_create_report(session, match.id, reporter.id)
        part = repo.get_participations(session, match.id, rival.id)[0]
        repo.upsert_evaluation(
            session,
            report.id,
            rival_player.id,
            rival.id,
            part.id,
            actor_id=reporter.id,
            observation_status="evaluated",
            general_rating=8.5,
            standout=True,
            pdf_include=True,
        )
        repo.sync_report_standout(session, report.id, reporter.id)
        assert report.standout_player_id == rival_player.id
        assert repo.validate_report_for_finalization(session, report.id) == []
