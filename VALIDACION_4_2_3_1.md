# Validación release No Name PostMatch 4.2.3.1

- **Fuente única de código:** ZIP completo 4.2.3 distribuido previamente. No se mezclaron versiones 4.2.1/4.2.2.
- **Motivo:** permitir publicar sin Informador dejaba `published` con 0 asignaciones; Inicio y Jornada dependían de `report_assignments` y no ofrecían el informe al staff.
- `python -m compileall -q .`: OK.
- `python scripts/check_release_consistency.py`: OK, VERSION / APP_VERSION / REPORTS_PAGE_API_VERSION `4.2.3.1`, head 0013.
- `python -m pytest -q --disable-warnings`: **117 passed**, incluidas 4 regresiones nuevas sobre publicación obligatoriamente asignada, recuperación de asignaciones de partido publicado sin duplicados, rechazo de usuarios inválidos y rutas visibles.
- Primera ejecución de los tests nuevos detectó una discrepancia de la sesión ORM: el valor predeterminado `status` de una asignación recién creada no era visible en memoria hasta flush; se corrigió asignándolo explícitamente a `pending`, y se repitió la suite completa hasta obtener 117/117. La validación final es la posterior a la corrección.
- Alembic fresh → `0013_data_governance_4_2_3` en SQLite temporal: OK, columnas de gobierno de datos presentes.
- Alembic 0012 → 0013 en SQLite temporal: OK, columnas presentes. **Sin cambio de esquema respecto a 4.2.3**.
- En este entorno no está instalado Streamlit y no hay acceso autorizado al PostgreSQL real: **no se ha comprobado render Cloud ni se ha intervenido en Supabase**. No se afirma que el incidente esté resuelto en producción antes de probar con las cuentas y datos reales.
