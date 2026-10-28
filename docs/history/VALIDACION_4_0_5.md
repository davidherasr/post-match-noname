# Validación técnica · No Name PostMatch 4.0.5

## Corrección principal

Se corrige `StreamlitWidgetAlreadyInstantiatedError` provocado por escribir en `st.session_state["main_navigation"]` después de haber instanciado el `st.radio` de navegación lateral.

La navegación ahora se solicita mediante `_pending_main_navigation` y se aplica al comienzo del siguiente rerun, antes de crear el widget.

## Alembic / PostgreSQL

`alembic/env.py` prepara `public.alembic_version.version_num` como `VARCHAR(128)` antes de ejecutar migraciones PostgreSQL. Esto evita el límite por defecto de 32 caracteres detectado con `0010_core_workspace_schema_repair_4_0_4`.

No existe migración 0011: el head continúa siendo `0010_core_workspace_schema_repair_4_0_4`.

## Pruebas

- `python -m compileall -q .`: OK
- `python scripts/check_release_consistency.py`: OK
- `pytest -q`: 78 passed
- Alembic SQLite desde base vacía hasta head: OK
- No hay escrituras directas a `main_navigation` en `views/`: OK
- `pages/`: ausente
- Bases SQLite incluidas en release: 0
- `secrets.toml` real incluido: 0
