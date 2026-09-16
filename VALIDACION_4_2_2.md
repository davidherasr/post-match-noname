# Validación 4.2.2

- `VERSION = 4.2.2`.
- `APP_VERSION = 4.2.2`.
- `REPORTS_PAGE_API_VERSION = 4.2.2`.
- Alembic head: `0012_sporting_reading_4_2` (sin migración nueva).
- El arranque omite `alembic upgrade` cuando la base ya está exactamente en el head y valida después el esquema físico.
- Recuperación defensiva de `KeyError` solo si la base termina realmente en el head y pasa el contrato físico.
- Diagnóstico de arranque por fase y traceback en logs.
- Arquitectura 4.2.1 preservada: No Name/postpartido separado de neutrales, DD transversal, pesos de staff, discrepancias, señales repetidas, seguimiento individual por permiso, sin rol Scout activo.
- Roles estrictos: Admin administra; DD lee/decide; Informador puntúa/postpartido.
- Contraseñas: cualquier valor no vacío.
- Sin `pages/`, sin SQLite de usuario y sin Secrets reales en el paquete.
- Suite automatizada: 109 tests.
- `compileall`: OK.
- `check_release_consistency.py`: OK.
- Migración fresh hasta `0012`: OK.
- Upgrade específico `0011 -> 0012`: OK.
