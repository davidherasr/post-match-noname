# Validación 4.0.7

Release centrada en convocatoria, XI y claridad de Scouting.

Resultados sobre la build final:
- `python -m compileall -q .` → OK
- `python scripts/check_release_consistency.py` → OK
- `pytest -q` → 88 passed
- parser de Federación con TITULARES/SUPLENTES → OK
- lista simple sin inferir titulares → OK
- convocatoria de partido con titulares/suplentes → OK
- XI + banquillo → OK
- protección frente a duplicados → OK
- head Alembic → `0010_core_workspace_schema_repair_4_0_4` (sin migración nueva)
