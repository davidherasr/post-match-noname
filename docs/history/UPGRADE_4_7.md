# Instalación segura · No Name Área Técnica 4.7

## Advertencia y contexto real

La última evidencia facilitada sobre la base productiva era `public.alembic_version = 0015_observation_requests_4_4_3`, con 43 tablas/461 columnas. **No se ha conectado a tu Supabase ni se ha aplicado ninguna migración allí.** No asumas que este sigue siendo su estado hoy: consulta antes de actuar.

La 4.7 distribuye el historial **íntegro** de Alembic y fija la nueva revisión final `0018_workspaces_4_7`. Si sigues realmente en 0015, la actualización debe ejecutar secuencialmente `0016_partial_reading_4_5`, `0017_lowlight_compact_4_5_1` y `0018_workspaces_4_7`. La última migración crea **siete tablas nuevas**, añade índices, y registra de forma **idempotente** referencias a informes/lecturas antiguas dentro de la nueva bandeja. No borra ni recrea informes históricos. Las referencias de archivo histórico quedan en Todos, no como notificaciones recientes falsas.

**Contrato de esquema esperado al terminar:** 51 tablas y 566 columnas, **incluida** `public.alembic_version`, bajo el esquema usado por la aplicación y sin incluir objetos internos de Supabase. El resultado puede diferir si se añadieron otras tablas o columnas propias: valida los campos de la aplicación, no hagas limpieza de supuestos «extras».

## Pasos de despliegue

1. Haz una **copia completa restaurable** de PostgreSQL de Supabase antes de actualizar y conserva una copia de los archivos del sistema que estén en Storage. Comprueba que puedes restaurarla a un destino aislado.
2. Ejecuta sobre la BD real únicamente consultas de inspección de lectura, empezando por `SELECT version_num FROM public.alembic_version;` y por el inventario de tablas/columnas. Si la revisión no corresponde a un ancestro conocido de `0018`, **detente**: no estampes versiones a mano.
3. Despliega **el ZIP completo**, no sobreescribas solo `app.py` o una pantalla. Mantén las variables de entorno/Secrets de Streamlit Cloud existentes fuera del repositorio. **No incluyas contraseñas en código o documentación.**
4. Si has creado un respaldo y la revisión de Alembic es la prevista, configura `RUN_MIGRATIONS=true`, `DEMO_MODE=false` y reinicia la aplicación con el proveedor conectado. El arranque verifica la revisión y las columnas físicas antes de renderizar pantallas deportivas.
5. Recomprueba `public.alembic_version`: debe quedar en `0018_workspaces_4_7`. Comprueba también que existen `sporting_contributions_47`, `activity_events_47`, `activity_states_47`, `player_proposals_47`, `staff_requests_47`, `data_corrections_47` y `match_priorities_47`.
6. Prueba manualmente **todas** las rutas de `VALIDACION_4_7.md` con cuentas reales o de pruebas de cada perfil antes de anunciar la versión al staff. En particular: cambios DD, sesiones separadas, notas privadas, ediciones y vuelta atrás.
7. Si detectas un fallo de migración, **no** intentes repararlo tocando `supabase_migrations.schema_migrations` ni el número de Alembic. Conserva logs y utiliza el respaldo/restauración controlada.

## Datos y permisos

- Los datos existentes de `reports`, `player_evaluations`, `match_opinions`, `players`, `teams`, calendarios y usuarios permanecen. No conviertas automáticamente informes antiguos a los nuevos tipos sin una estrategia de identidad y deduplicación.
- Roles: `director`, `reporter`, `admin` son **acumulables**; `participation_profile` solo organiza el entorno. Para que un DD realice informes voluntarios necesita también rol `reporter`.
- La valoración de un usuario no se publica al resto del staff por el hecho de que comparta el partido. DD y Admin pueden leer aportaciones expresamente compartidas.
- Operaciones de roster oficial delegadas a director, admin y analista `full/free`. La importación explícita de titulares/suplentes queda bloqueada si modificaría participaciones de un encuentro con informes legados cerrados. En esos casos comunica una incidencia y revisa la integridad antes de proceder.

## Verificación/rollback

La migración 0018 tiene `downgrade()` deliberadamente **no destructivo**. No es un botón de reversión automática de UI; para una restauración segura de tablas históricas usa el respaldo previo y una ventana de mantenimiento. Mantén juntos la versión de código, el esquema y las copias. No elimines las tablas `_47` para «volver» a 4.6 después de haber empezado a introducir información real.

## Qué NO hemos probado

No se ha ejecutado el arranque contra PostgreSQL/Supabase productivo ni se ha podido instalar Streamlit para validar visualmente el navegador en este entorno. Las migraciones y pruebas se han ejecutado en SQLite aislado; no debe considerarse una certificación de producción.
