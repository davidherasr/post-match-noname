# Validación técnica · No Name PostMatch 4.0.1

La release se valida sobre un árbol limpio y, después, sobre el ZIP vuelto a extraer.

Comprobaciones exigidas:

- `python -m compileall -q .`
- `pytest -q`
- `python scripts/check_release_consistency.py`
- Alembic fresh → `0008_match_study_4_0`
- actualización usando una base creada con el código 3.9/0007 → 0008
- ausencia de directorio Streamlit `pages/`
- ausencia de `.db`, `.sqlite`, `.sqlite3` y `secrets.toml` en el ZIP
- `views/reports.py` y `app.py` con contrato 4.0.1

El paquete no contiene credenciales ni datos deportivos de demostración.
