"""4.5 regression: ungraded signals, operational contribution counts and PDF snapshots."""
from sqlalchemy import select
from models.entities import MatchOpinion, PlayerEvaluation
from repositories import dd_attention, reports, unidentified_players, workspaces
from reports.payload import build_report_payload
from reports.full_pdf import generate_full_pdf
from reports.summary_pdf import generate_summary_pdf
from test_release_4_5 import seed, player


def test_attention_signal_without_grade_reaches_dd(session_factory):
    with session_factory.begin() as s:
        admin, reporter, _, season, _, _, rival, _, match = seed(s)
        named = player(s, admin, rival, season, "Observado sin nota")
        report = reports.get_or_create_report(s, match.id, reporter.id)
        reports.upsert_evaluation(s, report.id, named.id, rival.id, None, actor_id=reporter.id,
                                  observation_status="observed", attention_signal=True)
        reports.submit_report(s, report.id, reporter.id)
        items = [i for i in dd_attention.attention_feed(s, season.id) if i["player_id"] == named.id]
        assert len(items) == 1
        assert items[0]["average"] is None and items[0]["matches"] == 1
        assert any("sin nota" in reason for reason in items[0]["reasons"])


def test_jornada_counts_submissions_not_autoassignments(session_factory):
    with session_factory.begin() as s:
        admin, reporter, _, season, _, _, _, _, match = seed(s)
        report = reports.get_or_create_report(s, match.id, reporter.id)
        before = workspaces.load_round_workspace(s, season_id=season.id, round_name="J1", user_id=reporter.id)
        assert before["contribution_counts"][match.id] == 0
        assert before["my_contributions"][match.id] == "Borrador"
        reports.save_report_summary(s, report.id, actor_id=reporter.id, rival_level=None,
                                    opponent_overview=None, own_team_note=None, standout_player_id=None,
                                    key_takeaways=None, own_team_rating=6, rival_team_rating=None)
        reports.submit_report(s, report.id, reporter.id)
        after = workspaces.load_round_workspace(s, season_id=season.id, round_name="J1", user_id=reporter.id)
        assert after["contribution_counts"][match.id] == 1
        assert after["my_contributions"][match.id] == "Entregada"


def test_pdf_current_and_immutable_snapshot_include_unidentified_signal(session_factory):
    with session_factory.begin() as s:
        admin, reporter, _, season, _, _, rival, _, match = seed(s)
        report = reports.get_or_create_report(s, match.id, reporter.id)
        unidentified_players.save_signal(s, actor_id=reporter.id, match_id=match.id,
            team_id=rival.id, position="EI", shirt_number=11, highlight_rank=1,
            attention_signal=True, source="own_report", note="Llegó varias veces al área")
        reports.submit_report(s, report.id, reporter.id)
        for version in (None, 1):
            payload = build_report_payload(s, report.id, version=version)
            assert len(payload["unidentified_signals"]) == 1
            for builder in (generate_summary_pdf, generate_full_pdf):
                pdf = builder(payload, current_version=1)
                assert pdf.startswith(b"%PDF-") and len(pdf) > 4000
