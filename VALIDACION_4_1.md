# Validación 4.1.0

Validaciones ejecutadas sobre la release:

- `python -m compileall -q .` → OK.
- `pytest -q` → **94 passed**.
- `python scripts/check_release_consistency.py` → OK.
- Alembic desde base vacía hasta `0010_core_workspace_schema_repair_4_0_4` → OK.
- Alembic desde `0006_player_report_360_3_6` hasta head → OK.
- Contraseña provisional `1234` aceptada solo con cambio obligatorio → cubierta por test.
- Contraseña definitiva simple rechazada → cubierta por test.
- Admin puro no hereda DD/Scout; usuario multirol sí acumula capacidades → cubierto por test.
- Admin puro no puede crear misiones Scout; DD sí y solo puede asignarlas a un usuario con rol Scout → cubierto por test.
- Jornada no contiene selector `Tipo de seguimiento` ni `Dossier completo` → cubierto por test/consistencia.
- No se introduce migración nueva en 4.1.0.
