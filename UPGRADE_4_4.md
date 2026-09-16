# No Name · Área Técnica — instalación 4.4

## Alcance
Esta release toma como base íntegra la 4.2.3.2. Reorganiza Inicio en torno a tareas del usuario y último/próximo partido; destaca una acción operativa en Jornada; admite publicar postpartidos con alineaciones parciales documentadas sin inventar once jugadores y preserva participaciones existentes cuando no se reemplaza el XI completo. Se clarifican el guardado y la entrega del informe, manteniendo su incorporación directa y una corrección excepcional versionada. Se corrige Player Report 360 para separar rendimiento propio y rival, se evita atribuir consenso a cero o un solo informador y se propaga la temporada seleccionada al comparador. Las tarjetas de Jugadores distinguen evidencia propia/externa, DD sustituye selectores horizontales extensos y Administración sitúa operaciones irreversibles en Mantenimiento avanzado. Se conservan las funciones y protecciones previas.

## Integridad y despliegue
1. Antes de desplegar, conserva el ZIP 4.2.3.2 actualmente operativo y haz una copia íntegra **restaurable** del PostgreSQL de Supabase (y, por separado, del bucket documental). El exportador técnico de la aplicación no sustituye `pg_dump` ni incluye ficheros del bucket.
2. Sustituye el código **completo** por el ZIP 4.4, con `app.py` en la raíz. No copies archivos aislados entre releases y elimina cualquier directorio `pages/` heredado. No subas `secrets.toml`, bases `.db`, credenciales ni datos productivos al repositorio.
3. Conserva exactamente el proyecto Supabase, `DATABASE_URL`, y Secrets existentes. La revisión Alembic sigue siendo `0013_data_governance_4_2_3`: **no hay migraciones nuevas**. Si la base productiva aún no está en 0013, sigue el procedimiento supervisado de actualización de 4.2.3, sin ejecutar `alembic stamp`, `DROP` o `TRUNCATE` por intuición.
4. Haz commit y push, reinicia Streamlit Cloud, verifica el código desplegado en logs y comprueba el circuito con Admin, Informador y DD.
5. No se eliminan registros ni se reasigna el equipo propio de forma automática al desplegar. El borrado físico sigue siendo una acción independiente de Administración que exige backup y confirmación.

## Pruebas funcionales de aceptación en Cloud
- Admin: último partido pasado no preparado aparece en Mi trabajo aunque exista una jornada futura; uno publicado sin Informadores ofrece asignación; horarios pendientes solo si corresponde.
- Informador: el partido asignado aparece en Mi trabajo, abre directamente el editor, permite continuar borrador y entregar. El estado incorporado se refleja en DD y en los historiales oficiales.
- Postpartido con datos parciales: la falta de titulares genera advertencias sin rellenar nombres ni eliminar los ya confirmados; los duplicados y un XI de más de 11 se rechazan.
- Jugadores: ficha propia refleja evaluaciones `own`; ficha externa, `rival`, con fuentes separadas; cero observaciones = sin datos, una persona = consenso no comparable; comparador mantiene temporada.
- Partido y equipo de prueba/archivados: excluidos de Inicio, Jornada, DD y estadísticas, con datos no destruidos.
- Móvil/escritorio: controles y botones legibles, permisos correctos, ninguna navegación duplicada.

## Limitaciones de validación
Las pruebas automatizadas y migraciones se ejecutaron en SQLite aislado. No se ha conectado esta entrega a la base Supabase productiva ni comprobado visualmente en el navegador del usuario. La aceptación en Streamlit Cloud sigue pendiente.
