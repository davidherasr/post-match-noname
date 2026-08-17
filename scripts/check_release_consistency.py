from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "3.6.0"
HEAD_MIGRATION = "0006_player_report_360_3_6"


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
    if read_version() != EXPECTED:
        errors.append(f"VERSION no coincide: {read_version()}")
    if read_config_version() != EXPECTED:
        errors.append(f"APP_VERSION no coincide: {read_config_version()}")
    config_text = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    if "showSidebarNavigation = false" not in config_text:
        errors.append("Falta showSidebarNavigation=false")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    if 'st.set_option("client.showSidebarNavigation", False)' not in app_text:
        errors.append("Falta defensa runtime de navegación")
    for token in ['"scout"', '"calendar"', '"model"']:
        if token not in app_text:
            errors.append(f"Falta navegación heredada: {token}")

    required = [
        "pages/calendar.py", "pages/scout.py", "pages/model.py", "pages/scouted.py",
        "repositories/calendar.py", "repositories/planning.py", "repositories/data_quality.py",
        "repositories/player_report.py", "ui/player_report.py", "reports/player_report_pdf.py",
        "core/calendar_import.py", "repositories/advanced_scouting.py", "repositories/league_intelligence.py",
        "repositories/users.py", "repositories/players.py", "repositories/matches.py", "repositories/reports.py",
        "reports/payload.py", "reports/summary_pdf.py", "reports/full_pdf.py", "services/health_service.py",
        "scripts/live_acceptance.py", f"alembic/versions/{HEAD_MIGRATION}.py",
    ]
    for rel in required:
        if not (ROOT / rel).exists():
            errors.append(f"Falta archivo 3.6: {rel}")

    api, functions = reports_contract()
    if api != EXPECTED:
        errors.append(f"REPORTS_PAGE_API_VERSION no coincide: {api}")
    for name in {"render_work", "render_archive", "render"}:
        if name not in functions:
            errors.append(f"Falta pages.reports.{name}()")

    report_text = (ROOT / "pages" / "reports.py").read_text(encoding="utf-8")
    if "@st.fragment" not in report_text or "eval_dirty_34" not in report_text:
        errors.append("Falta modo rápido/dirty state heredado 3.4")

    scouted_text = (ROOT / "pages" / "scouted.py").read_text(encoding="utf-8")
    for required_text in ["Player Report 360", "Preparar ficha Scout ejecutiva", "Preparar dossier Player Report 360", "Evaluación DD por criterios"]:
        if required_text not in scouted_text:
            errors.append(f"Falta Player Report 360: {required_text}")
    model_text = (ROOT / "pages" / "model.py").read_text(encoding="utf-8")
    if "Mapear nuestra plantilla al modelo" not in model_text or "Plantilla No Name" not in model_text:
        errors.append("Falta comparación interna de plantilla para Player Report 360")

    if errors:
        raise SystemExit("Release inconsistente:\n- " + "\n- ".join(errors))
    print(f"OK · No Name PostMatch {EXPECTED} es internamente consistente · Alembic {HEAD_MIGRATION}")


if __name__ == "__main__":
    main()
