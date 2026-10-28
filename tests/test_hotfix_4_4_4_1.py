from pathlib import Path
import importlib.util

from sqlalchemy.engine import make_url

from core import config

ROOT = Path(__file__).resolve().parents[1]


def test_release_identity_4441():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.5"
    assert 'APP_VERSION = "4.5"' in (ROOT / "core/config.py").read_text(encoding="utf-8")
    assert 'REPORTS_PAGE_API_VERSION = "4.5"' in (ROOT / "views/reports.py").read_text(encoding="utf-8")


def test_requirements_cover_both_supported_postgresql_drivers():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "psycopg2-binary>=2.9.11,<3" in req
    assert "psycopg[binary]>=3.2,<4" in req
    assert "alembic>=1.17,<2" in req


def test_plain_postgresql_url_normalizes_to_psycopg3(monkeypatch):
    monkeypatch.setattr(config, "env", lambda name, default=None: "postgresql://u:p@example.com/db" if name == "DATABASE_URL" else default)
    url = make_url(config.normalized_database_url())
    assert url.drivername == "postgresql+psycopg"
    assert url.query.get("connect_timeout") == "10"


def test_explicit_psycopg2_url_is_preserved(monkeypatch):
    monkeypatch.setattr(config, "env", lambda name, default=None: "postgresql+psycopg2://u:p@example.com/db" if name == "DATABASE_URL" else default)
    url = make_url(config.normalized_database_url())
    assert url.drivername == "postgresql+psycopg2"


def test_runtime_dependency_validator_is_present_and_called():
    db = (ROOT / "core/database.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def validate_runtime_dependencies()" in db
    assert "validate_runtime_dependencies()" in db
    assert "except ModuleNotFoundError as exc:" in app
    assert "_render_runtime_dependency_error" in app
