# Validación técnica · No Name PostMatch 4.0.2

## Resultado

- `python -m compileall -q .` → **OK**
- `python -m pytest -q` → **68 passed**
- `python scripts/check_release_consistency.py` → **OK**
- Alembic fresh → `0008_match_study_4_0` → **OK**
- Alembic `0007_product_consolidation_3_8 -> 0008_match_study_4_0` → **OK**
- `pages/` → **ausente**
- bases SQLite runtime / WAL / SHM → **ausentes del paquete**
- `secrets.toml` real → **ausente**
- contrato interno 4.0.2 (`VERSION`, `core/config.py`, `app.py`, `views/reports.py`) → **OK**

## Hotfix específico

4.0.2 elimina la causa del `ImportError` observado cuando Streamlit Cloud ejecutaba un `app.py` nuevo sobre un `core/config.py` antiguo. El arranque ahora valida el contrato de `core.config` antes de cargar el resto de módulos y muestra un diagnóstico legible si el repositorio vuelve a quedar mezclado.

El ZIP se entrega con **raíz plana**, para que al extraerlo aparezcan directamente `app.py`, `core/`, `views/`, etc. y no una carpeta contenedora adicional.

## Base de datos

No existe migración nueva en 4.0.2. El head continúa siendo `0008_match_study_4_0`; se mantiene el mismo Supabase, `DATABASE_URL`, Secrets y datos existentes.
