# Validación 4.6

- Basada exclusivamente en los archivos de 4.5.1.1 recibidos y sus documentos de referencia.
- `pytest -q`: **199 pruebas superadas** en la última ejecución antes de empaquetar (se repite tras el cierre).
- `python -m compileall -q .`: correcto.
- `python scripts/check_release_consistency.py`: correcto; Alembic 0017.
- Pruebas específicas: borradores excluidos del feed; estado DD sin nota privada; descarte reservado a DD; selección del roster sin crear participaciones; XI confirmado prioritario; contratos de Inicio/Informe.
- Base SQL: conserva migración Alembic `0017_lowlight_compact_4_5_1` sin introducir cambios físicos.
- **No comprobado aquí:** UI Streamlit (dependencia ausente en el entorno), render de navegador, Supabase real, migración en PostgreSQL productivo, permisos de Cloud/Storage y usabilidad móvil.

No llamar a esta versión «validada en producción» sin completar los puntos anteriores.
