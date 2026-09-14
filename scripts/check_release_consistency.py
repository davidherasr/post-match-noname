from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "4.0.2"
HEAD_MIGRATION = "0008_match_study_4_0"


def read_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def read_config_version() -> str:
    text = (ROOT / "core" / "config.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)', text)
    if not match:
        raise RuntimeError("APP_VERSION no encontrado")
    return match.group(1)


def reports_contract() -> tuple[str | None, set[str]]:
    path = ROOT / "views" / "reports.py"
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

    if (ROOT / "pages").exists():
        errors.append("Existe el directorio especial pages/: Streamlit mostraría navegación automática")

    config_text = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    if "showSidebarNavigation = false" not in config_text:
        errors.append("Falta showSidebarNavigation=false")

    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    if 'st.set_option("client.showSidebarNavigation", False)' not in app_text:
        errors.append("Falta defensa runtime de navegación")
    for label in ["Inicio", "Jornada", "Jugadores", "Plantilla", "Administración"]:
        if f'"{label}"' not in app_text:
            errors.append(f"Falta navegación 4.0: {label}")
    if "active_profile_role" not in app_text or ".pop(" not in app_text:
        errors.append("No se limpia el selector de Perfil activo heredado")

    required = [
        "views/home.py", "views/jornada.py", "views/player_hub.py", "views/squad.py", "views/admin_hub.py",
        "views/reports.py", "views/postmatch.py", "views/scout.py", "views/team_hub.py",
        "repositories/workspaces.py", "repositories/player_report.py", "repositories/planning.py",
        "repositories/scouting.py", "repositories/calendar.py", "repositories/data_quality.py",
        "ui/player_report.py", "ui/match_study.py", "reports/player_report_pdf.py", "core/permissions.py", "core/presentation.py",
        "core/calendar_import.py", "core/clock.py", "scripts/live_acceptance.py", "scripts/check_matchday_readiness.py", f"alembic/versions/{HEAD_MIGRATION}.py",
    ]
    for rel in required:
        if not (ROOT / rel).exists():
            errors.append(f"Falta archivo 4.0: {rel}")

    api, functions = reports_contract()
    if api != EXPECTED:
        errors.append(f"REPORTS_PAGE_API_VERSION no coincide: {api}")
    for name in {"render_work", "render_archive", "render"}:
        if name not in functions:
            errors.append(f"Falta views.reports.{name}()")

    calendar_text = (ROOT / "views" / "calendar.py").read_text(encoding="utf-8")
    if "time(17, 0)" in calendar_text:
        errors.append("El calendario todavía propone 17:00 cuando la hora es desconocida")
    if 'main_navigation"] = "Misiones"' in calendar_text or 'main_navigation"] = "Nuevo postpartido"' in calendar_text:
        errors.append("El calendario mantiene navegación legacy fuera de Jornada")

    reports_text = (ROOT / "views" / "reports.py").read_text(encoding="utf-8")
    if 'user["role"]' in reports_text:
        errors.append("Informes todavía depende del perfil principal en lugar de capacidades acumulativas")

    permissions_text = (ROOT / "core" / "permissions.py").read_text(encoding="utf-8")
    if 'items = ["Inicio", "Jornada", "Jugadores"]' not in permissions_text:
        errors.append("La navegación base no coincide con Inicio/Jornada/Jugadores")
    if 'items.append("Plantilla")' not in permissions_text or 'items.append("Administración")' not in permissions_text:
        errors.append("Faltan capas de Plantilla/Administración por permiso")

    migration_text = (ROOT / "alembic" / "versions" / f"{HEAD_MIGRATION}.py").read_text(encoding="utf-8")
    for token in ["video_available", "home_formation_known", "away_formation_known", "study_notes"]:
        if token not in migration_text:
            errors.append(f"Migración 0008 incompleta: falta {token}")

    jornada_text = (ROOT / "views" / "jornada.py").read_text(encoding="utf-8")
    for token in ["Vídeo disponible", "Formación desconocida", "render_campogram", "Actualizar plantilla desde Federación"]:
        if token not in jornada_text:
            errors.append(f"Jornada 4.0 incompleta: falta {token}")

    if errors:
        raise SystemExit("Release inconsistente:\n- " + "\n- ".join(errors))
    print(f"OK · No Name PostMatch {EXPECTED} es internamente consistente · Alembic {HEAD_MIGRATION}")


if __name__ == "__main__":
    main()
