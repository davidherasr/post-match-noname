# Actualización No Name PostMatch 4.0.5

No requiere una nueva migración de negocio. El head Alembic continúa siendo `0010_core_workspace_schema_repair_4_0_4`.

La release corrige el cambio de navegación de Streamlit y prepara automáticamente `alembic_version.version_num` como `VARCHAR(128)` en PostgreSQL antes de ejecutar Alembic.

Despliegue recomendado: sustituir el código completo, mantener los Secrets y reiniciar la app.
