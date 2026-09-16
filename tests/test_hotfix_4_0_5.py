from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_405_contract():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "4.2.3.2"
    assert 'APP_VERSION = "4.2.3.2"' in (ROOT / "core/config.py").read_text(encoding="utf-8")
    assert 'REPORTS_PAGE_API_VERSION = "4.2.3.2"' in (ROOT / "views/reports.py").read_text(encoding="utf-8")


def test_navigation_changes_are_deferred_until_before_radio_instantiation():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    helper = (ROOT / "core/navigation.py").read_text(encoding="utf-8")
    home = (ROOT / "views/home.py").read_text(encoding="utf-8")

    assert "apply_pending_navigation(labels, nav_key=nav_key)" in app
    assert app.index("apply_pending_navigation(labels, nav_key=nav_key)") < app.index('st.radio("Navegación"')
    assert '_PENDING_NAVIGATION_KEY = "_pending_main_navigation"' in helper
    assert 'request_navigation("Jornada")' in home
    assert 'st.session_state["main_navigation"] = "Jornada"' not in home


def test_active_views_do_not_mutate_widget_backed_navigation_key():
    for rel in [
        "views/home.py", "views/calendar.py", "views/admin_hub.py",
        "views/squad.py", "views/team_hub.py",
    ]:
        body = (ROOT / rel).read_text(encoding="utf-8")
        assert 'st.session_state["main_navigation"] =' not in body, rel
        assert 'st.session_state["main_navigation"]=' not in body, rel


def test_postgres_alembic_version_capacity_is_widened_before_migrations():
    env = (ROOT / "alembic/env.py").read_text(encoding="utf-8")
    assert "_ensure_version_table_capacity(connection)" in env
    assert "VARCHAR(128)" in env
    assert "ALTER COLUMN version_num TYPE VARCHAR(128)" in env
    assert env.index("_ensure_version_table_capacity(connection)") < env.index("context.configure(connection=connection")
