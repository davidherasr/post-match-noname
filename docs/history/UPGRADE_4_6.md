# Actualización 4.6 — lectura y consulta primero

**Base de código:** 4.5.1.1, desplegar el ZIP íntegro. **Alembic head:** `0017_lowlight_compact_4_5_1` (sin migración nueva).

## Cambios
- Inicio de actividad compartida para todos los permisos; DD + Informador ve primero decisiones y datos, el informe es voluntario.
- Decisiones de DD como hechos con estado actual sin filtrar `director_note`; informes incorporados y neutrales con acceso a fuente.
- Editor «Completo» utilizable sin XI; muestra la lectura global y ampliaciones individuales opcionales.
- Si falta XI, selección de plantilla de temporada etiquetada como **no confirmada**. Nunca genera participación del partido.
- Mesa DD más contenida y navegación compacta de Administración.

## Despliegue
1. Guardar backup restaurable de PostgreSQL y Storage; no basta con exportar CSV/Excel.
2. Confirmar `public.alembic_version`. La captura anterior mostraba `0015_observation_requests_4_4_3`. Si se mantiene, deben aplicarse **0016 y 0017** con el mecanismo Alembic existente; no modificar manualmente `alembic_version`.
3. Rotar las credenciales que se compartieron durante el soporte. Confirmar `DEMO_MODE=false`, `RUN_MIGRATIONS=true`, URL de pooler y permisos de base.
4. Reemplazar íntegramente el repositorio; no combinar módulos de la versión anterior.
5. Reiniciar Streamlit Cloud y probar con usuarios de distintos roles. **No asumir que los tests locales prueban Cloud.**

No ejecutar en `supabase_migrations.schema_migrations`. Los avisos 42P01 del dashboard de Supabase no equivalen a un error de `public.alembic_version`.
