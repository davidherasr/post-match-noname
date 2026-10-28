# Actualización controlada · No Name · Área Técnica 4.4.4.1

## Motivo

La 4.4.4 desplegada llegó a `init_db()` y se detuvo con `ModuleNotFoundError` en la fase **migraciones / validación de esquema**. Esa fase solo carga de forma diferida el driver PostgreSQL y Alembic. El hotfix no modifica tablas ni datos.

## Antes de desplegar

1. Conserva el ZIP/código 4.4.4 y una copia restaurable de PostgreSQL/Supabase.
2. No borres ni recrees la base de datos. No ejecutes SQL manual para este error.
3. Sustituye **todo el contenido del repositorio** por este ZIP; no copies solo `app.py` o `requirements.txt`.
4. Mantén tus Secrets existentes (`DATABASE_URL`, credenciales, bucket, etc.).

## Dependencias

La release declara:

- `alembic>=1.17,<2`
- `psycopg[binary]>=3.2,<4`
- `psycopg2-binary>=2.9.11,<3`

Una URL normal `postgresql://...` se usa con Psycopg 3. Una URL explícita `postgresql+psycopg2://...` mantiene Psycopg 2.

## Despliegue Streamlit Cloud

1. Commit/push del paquete completo.
2. En **Manage app**, reinicia la aplicación para forzar el nuevo entorno/dependencias. Si Cloud conserva un build antiguo, vuelve a desplegar/reboot tras confirmar que `requirements.txt` del repositorio es el de 4.4.4.1.
3. Verifica en la barra lateral `Versión 4.4.4.1`.
4. El head Alembic esperado continúa en `0015_observation_requests_4_4_3`; no existe `0016`.

## Si vuelve a fallar

La pantalla ya no debe limitarse a `Tipo de error: ModuleNotFoundError`. Debe mostrar `Módulo: ...`. Copia ese nombre y el traceback de **Manage app → Logs**. No pegues contraseñas ni Secrets.
