from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "3.0.1"


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
                if isinstance(target, ast.Name) and target.id == "REPORTS_PAGE_API_VERSION":
                    if isinstance(node.value, ast.Constant):
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
        errors.append("Falta client.showSidebarNavigation = false en .streamlit/config.toml")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    if 'st.set_option("client.showSidebarNavigation", False)' not in app_text:
        errors.append("Falta la defensa runtime para ocultar la navegación automática")

    api, functions = reports_contract()
    if api != EXPECTED:
        errors.append(f"REPORTS_PAGE_API_VERSION no coincide: {api}")
    for name in {"render_work", "render_archive", "render"}:
        if name not in functions:
            errors.append(f"Falta pages.reports.{name}()")
    if errors:
        raise SystemExit("Release inconsistente:\n- " + "\n- ".join(errors))
    print("OK · No Name PostMatch 3.0.1 es internamente consistente")


if __name__ == "__main__":
    main()
