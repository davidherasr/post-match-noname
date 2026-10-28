# Acta de validación técnica local · 4.5

**Fecha:** 28/10/2026. **Base inicial:** ZIP 4.4.4.1 adjunto, sin reconstrucción de releases anteriores. **Head final:** `0016_partial_reading_4_5`.

| Comprobación | Resultado |
| --- | --- |
| Baseline ZIP 4.4.4.1 sin cambios | 167 tests superados |
| Batería final 4.5 `pytest -q` | **183 passed in 36.49s** |
| `python -m compileall -q .` | OK |
| `python scripts/check_release_consistency.py` | OK, 4.5 + 0016 |
| Migración SQLite desde cero a 0016 | OK (prueba automatizada) |
| Migración SQLite desde 0015, fila histórica conservada | OK (prueba automatizada) |
| Migración de esquema generado desde ZIP 4.4.4.1 original, no copia 4.5 | OK, head 0016, fila `Histórico 4.4.4.1` conservada |
| Generación PDF full y summary, estado actual y snapshot versionado | OK, 4 PDFs válidos, con señal anónima y apunte verificado mediante texto extraído |
| Migración PostgreSQL 0015 → 0016 sobre una copia de Supabase | **No ejecutada**: sin copia ni credenciales autorizadas |
| Arranque Streamlit Cloud / bucket privado Supabase | **No ejecutado** |
| Validación visual en móvil 375px y escritorio | **No ejecutada** |
| Carga/concurrencia, RLS y recuperación de backup de producción | **No ejecutadas** |

Los 167 tests históricos se actualizaron en los contratos donde el requisito 4.5 modifica deliberadamente la autorización por asignación, la confirmación de hora y el número de versión. Se han añadido **16 casos nuevos** de regresión 4.5. Este resultado acredita la batería local vigente, no que las 167 pruebas originales inalteradas pasaran sobre la versión nueva.

**Dictamen:** paquete 4.5 localmente comprobado; **no se considera aprobada la puesta en producción** hasta superar las validaciones externas pendientes y la aceptación visual/funcional con datos representativos del cuerpo técnico.
