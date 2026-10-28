# Validación técnica — 4.4

Base: ZIP íntegro 4.2.3.2 de esta conversación, modificado en una copia de trabajo.

- Versión: `VERSION`, `APP_VERSION`, contrato de informes y comprobador interno alineados en `4.4`.
- Tests: `pytest -q --disable-warnings` → **134 superados** (incluye regresión nueva de tareas por rol, partido pasado sin preparar, no contabilizar partidos de prueba, Player 360 de propio, confianza con muestra insuficiente, XI parcial, integridad de participantes, navegación y mantenimiento).
- `python scripts/check_release_consistency.py` → OK.
- `python -m compileall -q app.py core models repositories services views ui reports alembic tests` → OK.
- Alembic en SQLite temporal: `upgrade head` desde cero → `0013_data_governance_4_2_3`; `upgrade 0012` seguido de `upgrade head` → `0013_data_governance_4_2_3`. Sin migración nueva ni cambios de esquema en 4.4.
- ZIP: raíz plana, excluye credenciales reales, `.db`, cachés, logs y entornos virtuales; comprobación posterior de integrantes/versión e integridad de ZIP.

No se han ejecutado pruebas end-to-end en navegador, PostgreSQL aislado ni Supabase real: no afirmar funcionamiento productivo confirmado. Antes de cualquier borrado definitivo en la app obtener respaldo PostgreSQL restaurable independiente.
