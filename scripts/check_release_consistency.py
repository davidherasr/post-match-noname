from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "3.4.0"


def read_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def read_config_version() -> str:
    text = (ROOT / "core" / "config.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)', text)
    if not match:
        raise RuntimeError("APP_VERSION no encontrado")
    return match.group(1)


def reports_contract() -> tuple[str | None, set[str]]:
    path = ROOT / "pages" / "reports.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    api = None
    functions: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "REPORTS_PAGE_API_VERSION" and isinstance(node.value, ast.Constant):
                    api = str(node.value.value)
    return api, functions


def main() -> None:
    errors: list[str] = []
    if read_version() != EXPECTED: errors.append(f"VERSION no coincide: {read_version()}")
    if read_config_version() != EXPECTED: errors.append(f"APP_VERSION no coincide: {read_config_version()}")
    config_text = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    if "showSidebarNavigation = false" not in config_text: errors.append("Falta showSidebarNavigation=false")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    if 'st.set_option("client.showSidebarNavigation", False)' not in app_text: errors.append("Falta defensa runtime de navegación")
    required = [
        "pages/scouted.py", "repositories/advanced_scouting.py", "repositories/league_intelligence.py",
        "repositories/users.py", "repositories/players.py", "repositories/matches.py", "repositories/reports.py",
        "reports/payload.py", "reports/summary_pdf.py", "reports/full_pdf.py", "services/health_service.py",
        "scripts/live_acceptance.py", "alembic/versions/0004_scout_workflow_3_3.py",
    ]
    for rel in required:
        if not (ROOT/rel).exists(): errors.append(f"Falta archivo 3.4: {rel}")
    api, functions = reports_contract()
    if api != EXPECTED: errors.append(f"REPORTS_PAGE_API_VERSION no coincide: {api}")
    for name in {"render_work", "render_archive", "render"}:
        if name not in functions: errors.append(f"Falta pages.reports.{name}()")
    report_text=(ROOT/"pages"/"reports.py").read_text(encoding="utf-8")
    if "@st.fragment" not in report_text or "eval_dirty_34" not in report_text: errors.append("Falta modo rápido/dirty state 3.4")
    admin_text=(ROOT/"pages"/"admin.py").read_text(encoding="utf-8")
    if "live_acceptance_rollback" not in admin_text: errors.append("Falta aceptación live desde Administración")
    if errors: raise SystemExit("Release inconsistente:\n- " + "\n- ".join(errors))
    print("OK · No Name PostMatch 3.4.0 es internamente consistente")

if __name__ == "__main__": main()
