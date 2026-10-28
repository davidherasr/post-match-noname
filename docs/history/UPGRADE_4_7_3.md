# Actualización a 4.7.3 · Comprobar antes de utilizar con el staff

1. Crear **copia de seguridad PostgreSQL/Supabase restaurable**. Conservar el ZIP anterior y todos los Secrets fuera del repositorio. No publicar contraseñas ni cadenas de conexión.
2. Sustituir todos los archivos del código por el **ZIP completo 4.7.3**, nunca solo `app.py`, `views/experience47.py` o el parser.
3. Mantener `RUN_MIGRATIONS=true` con su configuración existente. Alembic avanza desde el head anterior `0018_workspaces_4_7` hasta **`0019_rating_release_4_7_3`**, creando únicamente `match_rating_releases_473`. Si vienes de un head anterior, se ejecutarán las migraciones históricas pendientes. No modificar manualmente `public.alembic_version` ni `supabase_migrations.schema_migrations`.
4. Reiniciar la aplicación tras actualizar dependencias. La interfaz v2 mantiene requisito `streamlit>=1.51,<2`.
5. Antes de dar acceso al staff, ensayar en una copia de la BD los cuatro perfiles: Admin, Analista full, Informador own_only y DD. Confirmar que **ningún partido antiguo aparece como abierto** sin publicación expresa.
6. Iniciar sesión como Admin, abrir un partido ya disputado y pegar ambas alineaciones de 11 jugadores. Revisar el campo, confirmar y comprobar que se habilita en «Mis partidos» para Informadores.
7. Validar notas privadas, posibles favoritos y la ficha de Jugadores de DD. Revisar especialmente cambios de nombre duplicado, transferencias y suplentes; detener el despliegue si una identidad se resuelve de forma ambigua.

**Importante:** las correcciones de identidad tras publicar un XI permanecen protegidas. Existe la vía de comunicar una incidencia; no se ha desarrollado todavía una pantalla para remapear valoraciones existentes entre identidades.

**Estado:** candidata para validación, no probada contra la base real de Supabase ni una sesión completa de Streamlit Cloud.
