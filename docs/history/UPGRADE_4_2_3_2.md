# No Name · Área Técnica — actualización 4.2.3.2

## Qué corrige

Esta versión parte del ZIP **4.2.3.1 íntegro** y mantiene lo ya desarrollado: gestión del equipo propio y datos de prueba, catálogo de jugadores, postpartidos con incorporación directa y asignaciones a Informadores. Añade:

1. **Administración → Datos → Eliminación definitiva de datos.** Pestañas Temporadas, Partidos, Equipos y Jugadores, búsqueda, 40 resultados por página, casillas individuales, «Seleccionar todos los de esta página», «Quitar selección de esta página» y «Quitar toda la selección». Se conserva la selección al cambiar de pestaña/página. No se muestran claves internas en el listado.
2. **Vista previa obligatoria de impacto.** Antes de ejecutar, el administrador ve recuentos por tabla, referencias que se desvincularán, ajustes (equipo propio o temporada activa) afectados y documentos cuyo registro desaparecerá. Si se elimina un equipo, sus partidos e informes vinculados aparecen en la misma vista previa. Los jugadores NO se eliminan por defecto con un equipo: pueden estar compartidos o tener historial independiente. Se sugieren solo jugadores sin otras referencias y su inclusión es una decisión explícita; si hay más de 50, solo se incorporan los 50 nombres que se muestran.
3. **Borrado definitivo de filas seleccionadas y dependencias:** se ejecuta en una única transacción SQL con comprobación de rol Admin, verificación de existencia, bloqueo de filas raíz en PostgreSQL, comparación del plan con huella de integridad, desvinculación únicamente de relaciones opcionales y eliminación de hijos antes de padres. Se conserva una entrada en `audit_logs` con resumen de cantidades afectadas. Sin truncar tablas ni eliminar cuentas de usuario.
4. **Interfaz pública:** marca visible «No Name · Área Técnica», sin el nombre PostMatch, numeración de versión en barra lateral ni textos internos explicativos. Los datos de los selectores se muestran con nombres, no con IDs; los controles de asignación usan casillas y botones en español.
5. **Selección reactiva de Informadores:** «Guardar asignaciones y activar tareas» ya no depende de un botón deshabilitado cuyo formulario impedía actualizar el estado. Se selecciona fuera de `st.form` y se valida al guardar. Se aplica también al paso de preparación de un postpartido nuevo.
6. **Exportación técnica mejor identificada:** incluye todas las entidades ORM declaradas, con advertencia explícita de que NO es un dump SQL restaurable y NO incorpora los bytes del bucket.

## MUY IMPORTANTE: antes de eliminar datos

**El despliegue del ZIP no borra ninguna fila por sí mismo.** El borrado solo se ejecuta cuando un Administrador selecciona registros, analiza dependencias, declara disponer de backup completo, escribe `ELIMINAR DEFINITIVAMENTE` y confirma la operación.

- Obtener y verificar previamente un respaldo íntegro de **PostgreSQL** mediante el procedimiento de Supabase o `pg_dump` para el proyecto correcto, y una copia separada del **bucket documental**. Guardar también el ZIP anterior y los Secrets en su gestor seguro. El botón de exportación técnica de la app NO sirve como único backup ni hay que restaurarlo con `scripts/restore_backup.py` (herramienta legada para otro formato).
- Si eliminas la temporada activa o el equipo propio, esos ajustes quedarán sin configurar; después deberás seleccionar otros desde Administración. El resto de equipos/jugadores se mantiene si no está seleccionado ni depende forzosamente de los registros eliminados.
- La eliminación de filas `documents` **no elimina los archivos físicos de Supabase Storage o disco**. La vista previa enumera esas rutas para revisión documental posterior. No prometer borrado integral del almacenamiento externo sin una operación específica, autorizada y validada.
- La base guarda auditoría de cantidades y selección, pero **no guarda una copia de los datos borrados**. Solo un backup previo permite recuperarlos.
- El borrado de un equipo elimina sus partidos dependientes (incluidos partidos reales si estaban vinculados): revisar siempre la vista previa. El nombre «Noname Club» no activa ningún borrado automático; se selecciona el registro exacto desde la pantalla.

## Despliegue

1. Conserva copia íntegra del repositorio desplegado 4.2.3.1, PostgreSQL y bucket. Comprueba que accedes al Administrador.
2. Sustituye el árbol completo del código por este ZIP y haz commit/push. No sustituyas ni publiques `.streamlit/secrets.toml`, las contraseñas ni bases `.db` locales. Comprueba que no exista `pages/` en la raíz del repositorio.
3. Mantén `DATABASE_URL` apuntando al **mismo** proyecto PostgreSQL. No ejecutes `DROP`, `TRUNCATE`, `alembic stamp` ni operaciones SQL manuales para actualizar.
4. El head Alembic esperado es **`0013_data_governance_4_2_3`**, ya incluido en 4.2.3/4.2.3.1; **no hay migración 0014 ni nuevas columnas**. Deja el arranque de 4.2.3.2 validar el esquema; aplica la revisión 0013 solo si la base todavía estuviera detrás y de forma controlada.
5. Reinicia Streamlit Cloud; verifica Inicio, Jornada → partido publicado → Asignaciones → seleccionar un Informador → Guardar; luego entra como Informador y revisa su tarea.
6. Como Administrador revisa las cuatro pestañas de eliminación, el seleccionador masivo y el preview **sin pulsar confirmar borrado**. Para una eliminación real, analiza y confirma exactamente los registros elegidos y verifica que ya no aparecen en el catálogo ni en indicadores.

## Pruebas y limitaciones

`VALIDACION_4_2_3_2.md` recoge la compilación, 128 tests, consistencia, comprobación de ZIP y migraciones fresh/0012→0013 en bases SQLite **aisladas**. No se ha conectado ni alterado la instancia productiva ni ejecutado interacción de navegador en Streamlit Cloud. La prueba de render y el flujo final siguen pendientes en tu despliegue.
