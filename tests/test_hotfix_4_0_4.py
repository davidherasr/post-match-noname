from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


def test_release_404_contract():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.2.3.2"
    assert 'APP_VERSION = "4.2.3.2"' in (ROOT / "core/config.py").read_text(encoding="utf-8")
    assert (ROOT / "alembic/versions/0010_core_workspace_schema_repair_4_0_4.py").exists()


def test_home_query_is_lean():
    text_body = (ROOT / "repositories/workspaces.py").read_text(encoding="utf-8")
    block = text_body[text_body.index("def _next_own_match"):text_body.index("def load_home_workspace")]
    assert "load_only(" in block
    assert "joinedload(Match.competition)" not in block
    assert "Match.video_available" not in block
    assert "Match.study_notes" not in block


def test_schema_contract_covers_full_match_entity():
    body = (ROOT / "core/database.py").read_text(encoding="utf-8")
    for column in ["report_due_at", "revision", "deleted_at", "created_by", "created_at", "updated_at"]:
        assert f'"{column}"' in body
    for table in ["teams", "competitions", "seasons"]:
        assert f'"{table}"' in body
