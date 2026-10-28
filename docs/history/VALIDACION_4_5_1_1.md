# Validación · 4.5.1.1

## Ejecutado localmente

- `pytest -q`: **193 pruebas superadas** (189 anteriores + cuatro nuevas).
- `python -m compileall -q .`: correcto.
- `python scripts/check_release_consistency.py`: correcto; versión 4.5.1.1 y Alembic 0017.
- Manifest real recibido: comparación exacta `public` **43 tablas/461 columnas** contra contrato ORM **44/488**, sin diferencias adicionales; la versión Alembic no figura en el manifiesto.
- Base sintética histórica generada a partir del ZIP 4.4.4.1 (sin datos productivos), `0015` con 43 tablas/461 columnas: `alembic upgrade head` la lleva a 0017, 44 tablas/488 columnas, conservando el usuario, el partido, el jugador, la nota y el informe de ejemplo.
- Script de diagnóstico ejecutado en modo `--export` sin conexión. Su exit code 2 es esperado para un esquema previo a 4.5.

## No validado — no afirmar que funciona en producción

- Migración real de `0015` a `0017` contra PostgreSQL/Supabase con los datos de negocio existentes.
- Servicio interno de migraciones Supabase ni origen exacto de los errores `42P01`.
- Renderizado/operación de Streamlit, que no está instalado en este entorno.
- Arranque de Cloud, compatibilidad de `secrets`, navegador, concurrencia ni Storage/PDF remoto.
- Restauración efectiva de backup de PostgreSQL/Storage.

El entorno local no dispone del paquete `psycopg` ni de `streamlit`; las pruebas de migración citadas son **SQLite**, no PostgreSQL real. El paquete contiene el smoke test `scripts/check_ui_contract_451.py` para ejecutar al instalar todos los requisitos en el entorno de despliegue.

## Regla de despliegue

No ejecutar migraciones sobre la producción antes de confirmar valor de `public.alembic_version`, crear respaldo restaurable y revisar `UPGRADE_4_5_1_1.md`.
