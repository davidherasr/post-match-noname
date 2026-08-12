# Validación técnica · No Name PostMatch 3.4.0

## Estado local de release

- Compilación Python completa: correcta.
- Suite automatizada: **33 pruebas superadas**.
- Contrato de versión: **3.4.0**.
- Revisión Alembic actual: **`0004_scout_workflow_3_3`** (sin migración nueva en 3.4).
- `scripts/check_release_consistency.py`: correcto.
- No se incluyen bases `.db`, `.sqlite` o `.sqlite3`.
- No se incluyen equipos, jugadores, partidos, informes o PDFs deportivos de demostración.

## Cobertura nueva 3.4

- confianza explicable y recencia;
- detección de homónimos rivales;
- prioridad del contexto equipo+temporada;
- aceptación transaccional con rollback;
- además de las 29 pruebas heredadas de seguridad, importación, fusión, postpartido, bulk upsert, PDFs, liga y scouting avanzado.

## Prueba de aceptación live

La release incorpora dos vías para ejecutar la prueba **después del despliegue**, contra la DATABASE_URL real:

- Administración → Rendimiento → `Ejecutar aceptación real (rollback)`;
- `python scripts/live_acceptance.py --admin-email <correo-admin>`.

No puede certificarse desde la build local la latencia concreta de Streamlit Community Cloud + el proyecto Supabase del usuario porque esas credenciales/conexión no están presentes aquí. La prueba queda integrada para ejecutarse en el entorno real y revierte todos sus datos temporales.
