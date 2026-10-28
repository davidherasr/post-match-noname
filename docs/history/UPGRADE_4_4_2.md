# Actualización segura · No Name Área Técnica 4.4.2

## Alcance

4.4.2 une la **nota de rival del postpartido** con una observación individual complementaria. La entrega del postpartido sigue incorporándose directamente a DD y estadísticas. Solo si el Informador dispone de permiso individual de seguimiento y hay rivales evaluados, se ofrece una pantalla **opcional** posterior: la sugerencia 8/10 no inicia nada automáticamente. Puede guardar detalles seleccionados o finalizar sin seguimiento.

Se crea un enlace nullable entre `scout_observations.player_evaluation_id` y `player_evaluations.id`, con FK `ON DELETE SET NULL` e índice único. Es la migración **NUEVA** `0014_unified_player_evidence_4_4_2`, posterior a `0013_data_governance_4_2_3`. No cambia ninguna observación histórica ni desduplica durante el despliegue.

## Antes de desplegar

1. Verifica que el código efectivamente desplegado es **4.4.1** y toma copia íntegra de ese repositorio/commit. Evita mezclar archivos entre versiones; sustituye el código por **todo el contenido** del ZIP 4.4.2, cuya raíz contiene `app.py` y `VERSION`.
2. Realiza **backup SQL restaurable de PostgreSQL** y copia separada de documentos del bucket. El ZIP de código y la exportación tabular de la aplicación NO sustituyen a `pg_dump`. Prueba recuperación en un PostgreSQL aislado antes de depender de esa copia. No compartas `DATABASE_URL`, claves ni logs con secretos.
3. En una réplica aislada de la base, verifica que el head previo es `0013_data_governance_4_2_3`, prueba la migración a 0014 y verifica sus FKs, índices e informes históricos. No ejecutes scripts sobre la base productiva suponiendo que un SQLite local reproduce Supabase.
4. Mantén Secrets productivos fuera del repositorio. Si `RUN_MIGRATIONS` se utiliza para ejecutar Alembic en el arranque, autoriza la ventana de mantenimiento y supervisa el resultado; si está desactivado, actualiza el esquema siguiendo el procedimiento autorizado antes de abrir la nueva app. No emplees `alembic stamp` para saltarte revisiones.
5. Confirma en Streamlit Cloud `VERSION=4.4.2`, arranque, lectura real en PostgreSQL y disponibilidad de cuentas de Admin, Informador con y sin permiso especial y DD. No se cambia de Supabase ni se reinicializa la BD.

## Operativa del usuario

1. Un Informador con permiso `can_track_players` elabora un postpartido propio con al menos un rival puntuado; **entrega**. El informe ya queda oficial y se abre la ampliación opcional.
2. Los rivales con nota ≥8 aparecen **sugeridos**, pero puede seleccionar otros rivales puntuados o desmarcarlos. Si no quiere hacer seguimiento, pulsa **Finalizar sin añadir seguimientos**. Nunca se crea un expediente solo por nota 8.
3. Al guardar detalles se reutiliza **la misma nota del postpartido**, misma identidad de autor, jugador y partido. La observación especializada tiene referencia directa a la valoración y añade conclusiones, fortalezas, riesgos o próxima acción. Si ya había una observación de ese autor sobre ese jugador en ese partido, se reutiliza, sin crear otra.
4. DD entra en **Dirección Deportiva → Seguimiento**: ve actividad atribuida (autor y jugador), origen, nota, decisión y enlace a ficha; puede documentar su decisión de temporada. No necesita aprobar informes ni repartir misiones Scout.
5. Si hay duplicados anteriores, DD puede seleccionar y eliminar **solo uno de los duplicados** bajo confirmación y auditoría. No se borra el último evento, ni la observación vinculada al postpartido, ni la valoración original. Un Informador no puede ejecutar este borrado. Un `pg_dump` completo y documentos son requisitos previos para operaciones destructivas.

## Casos de aceptación obligatorios (Cloud / réplica PostgreSQL)

- Al entregar, el postpartido permanece incorporado aunque se pulse «Finalizar sin añadir seguimientos»; para un usuario sin permiso extra no aparece el paso.
- Sugerencia ≥8: sin guardar NO genera seguimiento. Elegir un rival con nota inferior también está permitido si fue evaluado y es externo; jugador propio no se puede seguir.
- Ampliar dos veces mismo autor/jugador/partido reutiliza el evento y su nota postpartido; Player 360 y PDF muestran **una línea lógica** combinada, no filas idénticas. No existen dos promedios independientes por una sola valoración.
- DD puede localizar la actividad por nombre y autor, abrir ficha, documentar decisión y revisar un grupo duplicado histórico. Al borrar solo la copia seleccionada se conserva el evento restante y el postpartido; la acción queda auditada.
- Verifica partidos archivados/de prueba, cambios de temporada, pantalla móvil, permisos combinados DD/Informador y que la actualización no altera opiniones anteriores ni documentos.

## Limitaciones de la validación entregada

Se han realizado pruebas automatizadas, compilación, consistencia y migraciones **sobre SQLite aislado**. No se ha ejecutado el frontend en un navegador, migrado una instancia PostgreSQL real ni accedido al Supabase/Streamlit del usuario. La ausencia de pruebas productivas debe resolverse antes de declarar el despliegue validado. Los duplicados históricos permanecen físicamente hasta la selección manual de DD.
