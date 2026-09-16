# Validación reproducible No Name PostMatch 4.2.3

- Código completo derivado de 4.2.2, sin mezclar el repositorio 4.2.1.
- `VERSION`, `APP_VERSION`, `REPORTS_PAGE_API_VERSION`: `4.2.3`.
- Head Alembic: `0013_data_governance_4_2_3`; migración anterior: `0012_sporting_reading_4_2`.
- `python -m pytest -q --disable-warnings`: **113 tests passed** (incluidos 4 nuevos de gobierno de datos, clasificación oficial/catálogo, entrega directa con reapertura/versionado y descubribilidad del asistente).
- `python -m compileall -q .`: OK.
- `python scripts/check_release_consistency.py`: OK.
- Alembic fresh → head en SQLite aislada: OK, contrato físico OK.
- Alembic 0012 → 0013 en SQLite aislada: OK, contrato físico OK.
- No se ha ejecutado `alembic upgrade` contra Supabase; no se han cambiado los registros productivos, ni simulado que el backup técnico incompleto sea un respaldo íntegro.
- No hay Streamlit instalado en el entorno de pruebas, por lo que **no se verificó el render interactivo ni el arranque en Cloud**. Requiere aceptación del usuario postdespliegue.
- No se conocen los IDs productivos de C.D. Noname, Noname Club o los dos partidos de Santa Marta. Ninguna migración los modifica o archiva automáticamente; deberán seleccionarse y auditarse en la UI de Administración por ID.
- Se mantiene la limitación histórica del «backup técnico» de la app. Antes de migrar Supabase, copia íntegra PostgreSQL verificable y respaldo separado del bucket.
