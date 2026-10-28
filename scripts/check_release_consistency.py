from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "4.7.4"
HEAD_MIGRATION = "0019_rating_release_4_7_3"


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
        errors.append("Existe pages/: Streamlit mostraría navegación automática")

    config_text = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    if "showSidebarNavigation = false" not in config_text:
        errors.append("Falta showSidebarNavigation=false")

    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    for label in ['Inicio', 'Dirección Deportiva', 'Administración']:
        if label not in app_text and label not in (ROOT/'views/experience47.py').read_text():
            errors.append(f'Falta navegación 4.7: {label}')
    if 'render_experience47(user, selected_label)' not in app_text:
        errors.append('La app no usa las rutas operativas de 4.7')
    if 'st.set_option("client.showSidebarNavigation", False)' not in app_text:
        errors.append("Falta defensa runtime de navegación")

    required = [
        "views/experience47.py", "views/home.py", "views/jornada.py", "views/player_hub.py", "views/squad.py", "views/admin_hub.py",
        "views/reports.py", "views/postmatch.py", "views/team_hub.py",
        "repositories/collaboration47.py", "repositories/staff_feed.py", "repositories/report_roster.py", "repositories/workspaces.py", "repositories/player_report.py", "repositories/planning.py",
        "repositories/sporting_reading.py", "repositories/tracking.py", "repositories/scouting.py", "repositories/calendar.py",
        "ui/player_report.py", "ui/match_study.py", "reports/player_report_pdf.py",
        "core/permissions.py", "core/presentation.py", "core/calendar_import.py", "core/clock.py",
        f"alembic/versions/{HEAD_MIGRATION}.py",
    ]
    for rel in required:
        if not (ROOT / rel).exists():
            errors.append(f"Falta archivo 4.2: {rel}")

    api, functions = reports_contract()
    if api != EXPECTED:
        errors.append(f"REPORTS_PAGE_API_VERSION no coincide: {api}")
    for name in {"render_work", "render_archive", "render"}:
        if name not in functions:
            errors.append(f"Falta views.reports.{name}()")

    permissions_text = (ROOT / "core" / "permissions.py").read_text(encoding="utf-8")
    for token in ['working_profile', 'own_only', 'Mis partidos', 'Dirección Deportiva', 'can_report', 'can_direct']:
        if token not in permissions_text:
            errors.append(f'Permisos 4.7 incompletos: {token}')
    active_ui=(ROOT/'views/experience47.py').read_text(encoding='utf-8')
    for token in ['def home(', 'def matches(', 'def match_detail(', 'def my_contributions(', 'def director(', 'def admin(', 'def player_detail(']:
        if token not in active_ui:
            errors.append(f'Ruta 4.7 incompleta: {token}')
    migration = (ROOT / "alembic" / "versions" / "0013_data_governance_4_2_3.py").read_text(encoding="utf-8")
    for token in ["is_test", "archived_at", "archived_previous_status"]:
        if token not in migration:
            errors.append(f"Migración 0013 incompleta: falta {token}")
    linked_migration = (ROOT / "alembic" / "versions" / "0015_observation_requests_4_4_3.py").read_text(encoding="utf-8")
    evidence_migration = (ROOT / "alembic" / "versions" / "0014_unified_player_evidence_4_4_2.py").read_text(encoding="utf-8")
    if "player_evaluation_id" not in evidence_migration or "0013_data_governance_4_2_3" not in evidence_migration:
        errors.append("Migración 0014 incompleta: falta enlace de evidencia al postpartido")
    if "player_observation_requests" not in linked_migration or "0014_unified_player_evidence_4_4_2" not in linked_migration:
        errors.append("Migración 0015 incompleta: falta peticiones y relaciones de seguimiento")

    jornada_text = (ROOT / "views" / "jornada.py").read_text(encoding="utf-8")
    for token in [
        "Estado del postpartido", "Estado de la lectura",
        "Dirección Deportiva · lectura conjunta", "Tu lectura del partido",
        "Seguimiento individual", "Iniciar seguimiento", "TITULARES", "SUPLENTES",
    ]:
        if token not in jornada_text:
            errors.append(f"Jornada 4.2 incompleta: falta {token}")
    for obsolete in ["Dirección Deportiva · asignar seguimiento", "Asignar trabajo de scouting", "Scout · registrar lo observado"]:
        if obsolete in jornada_text:
            errors.append(f"Jornada conserva flujo Scout obsoleto: {obsolete}")

    squad_text = (ROOT / "views" / "squad.py").read_text(encoding="utf-8")
    for token in [
        "Lectura deportiva", "Plantilla y modelo", "Criterio del staff",
        "Jugadores señalados", "Equipos", "Discrepancias", "Partidos recientes",
        "Se repiten en 2+ partidos", "Iniciar seguimiento",
    ]:
        if token not in squad_text:
            errors.append(f"Centro DD 4.2.2 incompleto: falta {token}")

    sporting_text = (ROOT / "repositories" / "sporting_reading.py").read_text(encoding="utf-8")
    for token in ["def league_intelligence", "def consensus_label", "def trend_label", "def team_reading_history"]:
        if token not in sporting_text:
            errors.append(f"Inteligencia transversal 4.2.2 incompleta: falta {token}")

    home_text = (ROOT / "views" / "home.py").read_text(encoding="utf-8")
    if not any(label in home_text for label in ("Abrir lectura deportiva", "Consultar inteligencia deportiva", "Abrir Dirección Deportiva")) or not any(label in home_text for label in ('request_navigation("Dirección Deportiva")', '_go("Dirección Deportiva")')):
        errors.append("Inicio no enlaza directamente con la lectura deportiva de DD")

    for legacy_view in ["views/scout.py", "views/director.py", "views/scouted.py", "views/model.py", "views/dashboard.py"]:
        if (ROOT / legacy_view).exists():
            errors.append(f"Sigue empaquetada una vista Scout/DD obsoleta: {legacy_view}")

    calendar_text = (ROOT / "views" / "calendar.py").read_text(encoding="utf-8")
    for obsolete in ["Asignar observación", "No hay usuarios con perfil Scout", "Tarea de scouting"]:
        if obsolete in calendar_text:
            errors.append(f"Calendario conserva asignación Scout obsoleta: {obsolete}")

    workspaces_text = (ROOT / "repositories" / "workspaces.py").read_text(encoding="utf-8")
    for obsolete in ["ScoutMission", "ScoutMissionTarget", "my_missions", "mission_counts", "targets_by_mission"]:
        if obsolete in workspaces_text:
            errors.append(f"Workspace activo conserva misiones Scout: {obsolete}")

    player_hub = (ROOT / "views" / "player_hub.py").read_text(encoding="utf-8")
    if "Asignar próxima acción" in player_hub or "Scout disponible" in player_hub:
        errors.append("Jugadores conserva asignación a Scout")
    if "Con observaciones" not in player_hub:
        errors.append("Jugadores no expone el filtro de observaciones de seguimiento")

    security_text = (ROOT / "core" / "security.py").read_text(encoding="utf-8")
    if "La contraseña no puede estar vacía" not in security_text or "al menos 10 caracteres" in security_text:
        errors.append("La política de contraseña ya no es simple/opcional")
    admin_text = (ROOT / "views" / "admin.py").read_text(encoding="utf-8")
    for token in ["Añadir", "Editar / eliminar", "Eliminados", "Puede realizar seguimiento individual de jugadores"]:
        if token not in admin_text:
            errors.append(f"Administración 4.2 incompleta: falta {token}")
    if '["admin", "director", "reporter", "scout"]' in admin_text:
        errors.append("Administración sigue exponiendo Scout como rol organizativo")

    if errors:
        raise SystemExit("Release inconsistente:\n- " + "\n- ".join(errors))
    print(f"OK · No Name · Área Técnica {EXPECTED} es internamente consistente · Alembic {HEAD_MIGRATION}")


if __name__ == "__main__":
    main()
