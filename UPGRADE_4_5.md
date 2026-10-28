# Actualización 4.4.4.1 → 4.5 · despliegue no destructivo

## Alcance

Se conserva el proyecto PostgreSQL/Supabase y su histórico. **No importar ningún ZIP antiguo sobre la release nueva ni ejecutar un reset de Supabase.** La migración `0016_partial_reading_4_5.py` es aditiva. El ZIP contiene aplicación completa, tests, scripts, documentos y cadena Alembic original.

## Antes del despliegue

1. Confirmar en la instalación actual la versión, el head de Alembic y la conectividad del Session Pooler de Supabase, sin revelar secretos.
2. Obtener **respaldo restaurable** de PostgreSQL con `pg_dump` y copia separada de los objetos del bucket Supabase. La exportación tabular interna no sustituye esas copias. Comprobar una restauración aislada antes de migrar producción.
3. Restaurar el backup en una **instancia PostgreSQL aislada**, probar `alembic upgrade head` desde `0015_observation_requests_4_4_3` y comparar cuentas de filas e integridad referencial antes/después. No ejecutar migraciones reales sin autorización y backup válido.
4. Verificar permisos de rol Informador, el ID de C.D. Noname y los perfiles `own_only/full/free/viewer` asignados por Administración. El default `full` es conservador para Informadores existentes.
5. Probar un partido oficial de No Name **sin hora ni asignación**, una lectura solo rival, una señal sin nota, una señal anónima y su resolución, una petición contextual DD y un PDF. Verificar que ningún registro test o archivado aparece en feed.

## Ejecución local

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q .
python scripts/check_release_consistency.py
```

Para migraciones desde cero y desde 0015 utilizar una copia de base de datos **aislada**. Las pruebas automáticas están en `tests/test_release_4_5_migrations.py` y `tests/test_release_4_5*.py`.

## Cloud

El despliegue a Streamlit Cloud y Supabase productivo **no se ha ejecutado en esta entrega**. Desplegar primero a entorno de ensayo; después de validar visualmente, conexión, permisos, importación, Storage y proceso de restauración, decidir promoción a producción. Ante cualquier anomalía, detener la migración y analizar sin modificar destructivamente la base.
