# Validación 4.0.6

- `python -m compileall -q .`: OK.
- `python scripts/check_release_consistency.py`: OK.
- `pytest -q`: 82 passed.
- Pruebas específicas del selector de XI: el jugador elegido se oculta en otros slots y permanece disponible en el slot actual.
- El editor ya no está dentro de `st.form`, por lo que los cambios de selección producen rerun y actualizan inmediatamente las opciones.
- La validación de repositorio sigue rechazando jugadores duplicados al guardar.
- Sin migración nueva; head Alembic: `0010_core_workspace_schema_repair_4_0_4`.
