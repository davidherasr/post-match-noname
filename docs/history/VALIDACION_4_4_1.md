# Validación técnica — 4.4.1

Base de código: ZIP completo 4.4 de esta conversación. El código 4.4.1 está construido íntegramente sobre esta copia; no mezcla releases antiguas.

- Versión coherente: `VERSION`, `core.config.APP_VERSION`, `views.reports.REPORTS_PAGE_API_VERSION`, `app.py` y `scripts/check_release_consistency.py` alineados.
- Pruebas locales: **140 superadas** (`python -m pytest -q`), incluidas seis regresiones adicionales de notas exactas/decimales históricos, limpieza de sesión, rechazo, reactivación, preservación de borrador, protección de informes incorporados y voluntariado DD+Informador.
- `python -m compileall -q .` y `python scripts/check_release_consistency.py`: OK.
- SQLite aislado: migración desde cero a `0013_data_governance_4_2_3`, OK; actualización desde `0012_sporting_reading_4_2` al mismo head, OK. Sin migración nueva.
- Pendiente: prueba de componentes Streamlit con navegador real, pruebas end-to-end y validación sobre PostgreSQL aislado o Supabase productivo. No inferir que pasar pytest verifica la pantalla ni la instancia Cloud.

El ZIP final debe comprobarse por integridad y exclusión de credenciales y bases de datos locales antes de entregarse.
