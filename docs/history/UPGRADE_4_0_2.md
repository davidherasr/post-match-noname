# Actualización No Name PostMatch 4.0.2

## Motivo

4.0.2 corrige un `ImportError` provocado por despliegues donde `app.py` y `core/config.py` pertenecían a versiones distintas.

## Regla de despliegue

No mezcles archivos. Borra el código de la versión anterior (conservando `.git` y, si lo deseas, `.devcontainer`) y copia **todo el contenido** de este paquete en la raíz del repositorio.

Al extraer el ZIP deben aparecer directamente `app.py`, `core/`, `views/`, `alembic/`, etc. No debe crearse una carpeta contenedora adicional.

No debe existir `pages/`. Tampoco deben subirse `postmatch_scout.db`, `*.db-shm`, `*.db-wal`, `__pycache__` ni `.pytest_cache`.

## Base de datos

No hay migración nueva. Se mantiene `0008_match_study_4_0`, el mismo Supabase, la misma `DATABASE_URL` y los mismos Secrets.
