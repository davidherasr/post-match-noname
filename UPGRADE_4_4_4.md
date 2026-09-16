# Actualización controlada · No Name · Área Técnica 4.4.4

## Qué es esta release

Se construye **exclusivamente desde el ZIP íntegro 4.4.3**. Corrige la navegación de Dirección Deportiva que lanzaba `StreamlitWidgetAlreadyInstantiatedError`, diferencia una selección deportiva expresa de un buscador de candidatos de media ≥8/10 (por defecto, al menos dos partidos), habilita lectura neutral voluntaria para cualquier Informador sin asignación administrativa, mejora la navegación de jornadas y aplica cambios concretos de jerarquía visual a Inicio, Informes, DD, Jugadores/Player 360, ficha de equipo, campograma, formularios y PDF. Conserva el informe propio asignado y el circuito de incorporación directa sin nueva aprobación. No contiene borrados ni actualizaciones automáticas de datos.

**Esquema:** sin migración nueva. La revisión Alembic permanece en `0015_observation_requests_4_4_3`; no ejecutar `stamp`, borrar tablas ni reinstalar Supabase. El nuevo código incluye cambios en consultas pero no altera modelos ORM ni scripts Alembic.

## Despliegue con seguridad

1. Confirmar que el repositorio en Cloud sirve realmente 4.4.3 y que la BD está en la revisión 0015; si no coincide, resolver antes de actualizar. Guardar copia del repositorio y los secretos en su entorno seguro (no dentro del ZIP).
2. Obtener `pg_dump` completo y verificar restauración en PostgreSQL aislado, además de preservar los documentos/PDF del bucket. El backup técnico de la app no sustituye ambas copias.
3. Sustituir **todo el código** por el contenido del ZIP 4.4.4. No copiar `postmatch_scout.db`, `secrets.toml`, `.env` o archivos de prueba del equipo local al repositorio.
4. Comprobar `VERSION=4.4.4` y cabecera de la aplicación, reiniciar Cloud y verificar logs de arranque. El esquema debe continuar en 0015.
5. Con DD, entrar en «Mi mesa de trabajo» y pulsar «Consultar jugadores seleccionados» y «Pedir o revisar opiniones»: ambos deben cambiar de vista **sin excepción StreamlitWidgetAlreadyInstantiatedError**. Volver a la mesa con el selector de áreas.
6. «Jugadores de interés» muestra solamente jugadores seleccionados expresamente, con seguimiento formal o peticiones abiertas. El modo «Descubrir candidatos por nota» usa media ≥8/10 y muestra muestra mínima, de dos partidos por defecto; sólo «Añadir a selección» crea una decisión DD. Un jugador descartado no se reactiva automáticamente.
7. En Jornada, usar «Primera jornada», «Ir a la jornada actual», flechas, selector y búsqueda. Abrir un partido neutral entre dos equipos distintos de No Name sin asignación y como Informador pulsar «Realizar lectura voluntaria». Confirmar en el formulario que realmente se vio; si no se confirma, no debe guardar. Verificar que editar la lectura reutiliza el registro del mismo autor/partido.
8. En un partido de **No Name** el postpartido sigue el flujo propio y sus asignaciones existentes. No convertir un partido propio en una lectura neutral ni dar permisos de Informe a DD por ser DD.
9. En Informes, consultar la lista y abrir directamente sin dos selecciones. Verificar filtro por «Jornada 1» frente a «Jornada 10», paginación por consulta y un informe histórico con sus datos intactos.
10. Revisar PDF 360 con comentario largo: observaciones en párrafos a página completa y nombres largos dentro de tablas, sin solapamiento.

## Casos no cubiertos por el entorno de construcción

No se ha probado la UI real con Streamlit Cloud, un navegador, un móvil ni el PostgreSQL productivo, ni se han modificado sus datos. Las pruebas automáticas y la migración SQLite aislada no equivalen a aceptación de producción. Probar con cuentas separadas Admin/Informador/DD, datos representativos de temporadas, jugadores de prueba/archivados y tamaños 320, 375, 768, 1024 y 1440 px antes de compartir masivamente.

En caso de fallo, conservar traceback completo sin secretos; comparar el commit activo y la revisión Alembic antes de decidir un rollback de código. No revertir migraciones 0014/0015 ni restaurar producción sin un procedimiento específico.
