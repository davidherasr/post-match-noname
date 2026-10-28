# Base de datos

La fuente de verdad son los modelos de `models/entities.py` y las migraciones de `alembic/`.

- `alembic upgrade head`: aplica el esquema actual.
- `alembic current`: muestra la revisión instalada.
- `schema_postgresql.sql`: referencia legible generada desde SQLAlchemy; no sustituye a Alembic.

Antes de cualquier migración en producción, crea un backup técnico y pruébalo en una copia de la base.
