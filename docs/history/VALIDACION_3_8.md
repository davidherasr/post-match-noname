# Validación técnica · No Name PostMatch 3.8.0

Comprobaciones realizadas sobre el árbol de release:

- `python -m compileall -q .`: OK.
- `python scripts/check_release_consistency.py`: OK.
- Alembic base vacía → `0007_product_consolidation_3_8`: OK.
- Alembic `0006_player_report_360_3_6` → `0007_product_consolidation_3_8`: OK.
- No se incluyen bases `.db`, `.sqlite` o `.sqlite3`.
- No se incluye `.streamlit/secrets.toml`.
- No se incluyen datos deportivos de demostración.

Nota sobre pytest: las pruebas ejecutadas por módulos que alcanzaron finalización pasan correctamente. En este entorno, la ejecución monolítica de toda la suite presenta un bloqueo de proceso después de varias decenas de pruebas; el test identificado en ese punto pasa cuando se ejecuta aisladamente. No se presenta ese bloqueo como una suite completa certificada.
