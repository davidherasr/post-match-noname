# Validación · No Name · Área Técnica 4.4.4.1

## Ejecutado localmente

- `pytest -q`: **167 pruebas superadas**.
- `python -m compileall -q .`: correcto.
- `python scripts/check_release_consistency.py`: correcto.
- Alembic desde base vacía → `0015_observation_requests_4_4_3`: correcto en SQLite aislado.
- Alembic `0014 → 0015`: correcto en SQLite aislado.
- Ejecución repetida estando ya en `0015`: correcta en SQLite aislado.
- Pruebas específicas: identidad 4.4.4.1, requirements con ambos drivers, normalización de `postgresql://` a Psycopg 3 y diagnóstico de dependencia ausente.

## No validado aquí

- Instalación real de paquetes desde PyPI dentro de Streamlit Community Cloud. El entorno de construcción local no tiene salida de red para `pip`.
- Conexión con tu PostgreSQL/Supabase productivo.
- Ejecución de Alembic contra tu base real.
- Navegador/Streamlit Cloud tras el nuevo build.

Por tanto, la release está validada como código/paquete, pero el cierre del incidente requiere un arranque real en Cloud.
