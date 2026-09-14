from pathlib import Path


def test_streamlit_magic_pages_directory_is_gone():
    assert not Path("pages").exists()
    assert Path("views/jornada.py").exists()


def test_release_contract_is_401_everywhere():
    assert Path("VERSION").read_text(encoding="utf-8").strip() == "4.0.3"
    assert 'APP_VERSION = "4.0.3"' in Path("core/config.py").read_text(encoding="utf-8")
    assert 'REPORTS_PAGE_API_VERSION = "4.0.3"' in Path("views/reports.py").read_text(encoding="utf-8")
    assert 'expected_api = "4.0.3"' in Path("app.py").read_text(encoding="utf-8")


def test_database_startup_has_safe_connection_handling():
    source = Path("core/database.py").read_text(encoding="utf-8")
    assert "_connect_with_retry" in source
    assert "DatabaseUnavailableError" in source
    assert 'cfg.attributes["connection"] = connection' in source


def test_alembic_can_reuse_validated_application_connection():
    source = Path("alembic/env.py").read_text(encoding="utf-8")
    assert 'config.attributes.get("connection")' in source
    assert "_run_with_connection" in source
