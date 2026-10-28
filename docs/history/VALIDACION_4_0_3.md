# Validación técnica · No Name PostMatch 4.0.3

## Resultado

- `python -m compileall -q .` → **OK**
- `pytest -q` → **71 passed**
- `python scripts/check_release_consistency.py` → **OK**
- Alembic base vacía → `0009_schema_repair_4_0_3` → **OK**
- Simulación de base marcada como `0008` pero sin columnas físicas 3.5/4.0 → `0009` → **OK**
- Backfill seguro de fecha orientativa y formación conocida en la simulación → **OK**
- directorio mágico `pages/` → **ausente**
- SQLite/DB/WAL/SHM incluidos en la release → **0**
- `secrets.toml` real incluido → **0**

## Caso reproducido por test

La suite crea una base con `alembic_version = 0008_match_study_4_0` y una tabla `matches` deliberadamente incompleta. Al ejecutar `alembic upgrade head`, 0009 restaura las columnas requeridas y deja la base en `0009_schema_repair_4_0_3` sin eliminar el partido existente.

## Limitación

El mensaje PostgreSQL original del error de Streamlit Cloud estaba redactado, por lo que no se puede certificar desde el traceback público cuál fue la columna/objeto exacto que provocó `ProgrammingError`. La corrección evita depender de esa inferencia: valida y repara explícitamente el contrato físico utilizado por 4.x antes de ejecutar workspaces.
