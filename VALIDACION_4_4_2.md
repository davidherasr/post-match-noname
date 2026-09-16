# Validación de la release 4.4.2

- Origen de código: extracción íntegra de `NoName_Area_Tecnica_4.4.1.zip` de la conversación, sin integrar archivos de ramas antiguas.
- Contratos de versión: `VERSION`, `core/config.py`, `views/reports.py`, `app.py` y `scripts/check_release_consistency.py` deben señalar 4.4.2.
- Head de Alembic NUEVO: `0014_unified_player_evidence_4_4_2`, revisión anterior 0013. Migración aditiva, columna nullable + FK `ON DELETE SET NULL` + índice único; downgrade deliberadamente no destructivo.
- Pruebas nuevas: permiso explícito, sugerencia sin automatismo, vinculación al postpartido, nota original sin duplicar, guardado idempotente, reutilización del registro anterior, cronología/PDF deduplicados, recuentos catálogo, actividad atribuida DD, borrado exclusivo DD con protección del último y del vinculado, y upgrade SQLite conservando filas legadas.
- **Ejecutado en el código fuente:** `python -m pytest -q` → **147 superados**; `python -m compileall -q .` → correcto; `python scripts/check_release_consistency.py` → correcto. Migración SQLite desde cero y 0013→0014 probada dentro de pytest, incluidas dos filas legadas conservadas sin cambios. La integridad del ZIP se comprueba además sobre la copia extraída antes de la entrega.
- Verificar que el ZIP no contiene bases SQLite productivas/locales, `.streamlit/secrets.toml`, `.env`, `__pycache__` ni credenciales; raíz directa `app.py`/`VERSION`.
- **Pendiente y fuera del entorno local:** aceptación visual Streamlit/móvil, migración y concurrencia PostgreSQL sobre réplica, arranque Cloud, cuentas/datos reales y backup restaurable.
