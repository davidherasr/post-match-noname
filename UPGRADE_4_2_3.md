# No Name PostMatch 4.2.3 — despliegue y uso

**Estado:** release candidata completa. El ZIP sustituye íntegramente al árbol de código anterior. Se comprobó en bases SQLite aisladas; no se conectó a Supabase ni se verificó arranque Streamlit Cloud. El repositorio proporcionado por el usuario seguía en 4.2.1; el origen del código de esta entrega es el ZIP íntegro 4.2.2.

## Antes de desplegar (obligatorio)

1. Guarda una copia íntegra, consistente y recuperable de PostgreSQL/Supabase mediante las herramientas de respaldo de PostgreSQL; verifica su posibilidad de restauración en una base aislada. Guarda por separado el contenido del bucket privado y conserva Secrets en un gestor seguro. **El botón «backup técnico» de versiones anteriores no incluye las 39 tablas ORM y NO sirve por sí solo para respaldar la producción**. No uses SQLite local como copia de Supabase.
2. Conserva ZIP y commit actuales como punto de retorno. No copies únicamente `app.py`: sustituye el árbol del repositorio por la release completa, sin carpetas `pages/` residuales, pero sin borrar Secrets de Streamlit Cloud ni la instancia Supabase.
3. Comprueba que el objetivo de `DATABASE_URL` corresponde al PostgreSQL correcto, sin mostrar la contraseña. Si `alembic current` indica `SQLiteImpl`, **no es Supabase**: detente.
4. Confirma que tu único Admin haya recuperado el acceso tras el bloqueo temporal antes de depender de los controles administrativos nuevos.

## Migración

- Head nuevo: `0013_data_governance_4_2_3`, desde `0012_sporting_reading_4_2`. Si el despliegue real permanece en 4.2.1 / head `0012`, solo es necesaria la nueva revisión `0013`; si está atrasado, Alembic encadena las revisiones existentes. No hay operación de reset ni destrucción de tablas.
- Añade `teams.is_test`, `teams.archived_at`, `matches.is_test`, `matches.archived_previous_status` sin modificar el estado de ningún equipo o partido por nombre.
- Cambia el ajuste de base de datos `require_report_approval` a `false` de acuerdo con la decisión explícita de incorporación directa. **No cambia los registros de informes históricos**, estados, fechas, revisores, participaciones ni resultados.
- Para ejecutar migraciones automáticamente desde Streamlit, revisa la configuración autorizada `RUN_MIGRATIONS`. Si está desactivada y el esquema está atrasado, el arranque debe detenerse con diagnóstico; no ejecutes SQL improvisado. Prueba primero el upgrade sobre una copia aislada de PostgreSQL y no uses `alembic stamp` para disfrazar un esquema incompleto.

## Qué cambia

### Administración → Club → Identidad deportiva y datos de prueba

- Selecciona el registro real **C.D. Noname por su ID verificado**. El guardado sincroniza `app_settings.own_team_id` y `teams.is_own_team`; el sistema impide elegir un equipo de prueba/inactivo/archivado. No crea equipos nuevos ni convierte antiguos partidos.
- En «Equipos de prueba / archivados», inspecciona `Noname Club` **por su ID y dependencias**. Primero márcalo explícitamente como prueba; después podrás archivarlo con confirmación. El equipo propio está protegido.
- En «Partidos de prueba / archivados», inspecciona individualmente los **dos partidos ficticios contra Santa Marta**; no se marcan por nombre. Marca cada ID como prueba, comprueba fecha, rival, participaciones, informes y demás dependencias y confirma el archivado. La restauración devuelve el estado anterior registrado por esta operación, manteniendo inicialmente la etiqueta de prueba. No se fusiona `Noname Club` con el club real.
- Los filtros de calendario, Inicio, datos oficiales, inteligencia DD, rankings y catálogo de jugadores excluyen las pruebas y los archivados. Los registros permanecen en la base; administración puede acceder a ellos.

### Jugadores

- Buscador, temporada, equipo por ID, posición, ámbito propio/externo, decisión deportiva, evidencia, ordenación, paginación SQL real y total de resultados. Los filtros quedan en selectores estables, en lugar de una fila horizontal recortada.
- Tarjetas separan rendimiento de postpartidos (nota/partidos/autores), menciones neutrales (menciones/partidos/autores) y observaciones formales. `Sin decisión` es distinto de `Observado`; se muestra `Sin nota` si no existe nota válida. Comparador plegado y accesos a Player Report 360.

### Postpartido y circulación a DD

- Admin: Jornada → partido **propio con horario confirmado** → Preparar partido. El asistente anuncia **1 Partido → 2 No Name → 3 Rival → 4 Publicar** y mantiene visible el acceso al último paso, inactivo cuando faltan requisitos, con explicación individual de errores. En el paso 4 aparece `PUBLICAR POSTPARTIDO`.
- Se reutiliza el **mismo Match** de Jornada. Si el mismo encuentro tiene once titulares verificados por equipo, se precargan para revisión; **no** se deduce XI del orden de plantillas o del partido anterior. Las formaciones admiten «Desconocida» sin asignar un sistema ficticio. Se requieren XI propios y rivales reales completos antes de publicar con el flujo de postpartido vigente.
- Admin selecciona usuarios con rol **Informador** explícito y publica. Cada Informador asignado encuentra el trabajo en Inicio / partido, guarda No Name y rival, y entrega.
- La entrega crea estado `incorporated`, versión y auditoría; se incluye inmediatamente en las estadísticas oficiales y lectura DD. No inventa un revisor ni una fecha de aprobación. DD ve informes incorporados desde Inicio y puede abrir el partido de origen. Los neutrales mantienen su lectura ligera y las señales no crean un seguimiento automáticamente.
- **Corrección excepcional desde la app:** Administración → Datos → Corrección excepcional de informes incorporados. Selecciona el ID de un informe entregado, introduce motivo obligatorio y confirma. Queda reabierto como `returned`, asignado de nuevo al Informador, con la versión ya entregada conservada y auditoría. Durante la corrección no cuenta como informe vigente en estadísticas; al volver a entregarse genera nueva versión `incorporated` y solo se cuenta una vez. No es aprobación obligatoria ni una tarea para DD.
- Informes históricos `submitted/approved/final/returned` se conservan sin conversión masiva; los históricos `submitted` no se incorporan silenciosamente como aprobados. Existe lógica legada de revisión para recuperación de historial, pero **no hay una nueva bandeja de aprobación obligatoria**.

## Prueba de aceptación después de desplegar

1. Confirmar versión `4.2.3`, commit y head PostgreSQL real `0013_data_governance_4_2_3`; no confundir con SQLite. Confirmar que no aparece otro menú automático `pages/` y que el Admin inicia sesión.
2. En Administración → Club, seleccionar **ID real C.D. Noname** y comprobar que ya no hay marcadores propios inconsistentes; NO seleccionar el registro ficticio.
3. Revisar por ID el equipo de prueba y sus dos partidos; probar marca de prueba, exclusión de estadísticas, archivado, restauración, persistencia de informes/participaciones y auditoría. No ensayar mutaciones contra producción sin backup válido.
4. Como Admin, abrir partido propio real con hora confirmada y avanzar los cuatro pasos; verificar que «Publicar» se localiza y que no se crean partidos duplicados ni titulares inferidos.
5. Con usuario Informador **asignado**, guardar un informe con valoración rival, entregar y comprobar inclusión inmediata en DD, estadísticas y ficha jugador; `reviewer_id` y `approved_at` nulos; prueba de consulta con DD puro sin permiso para puntuar.
6. Probar Jugadores con equipo y temporada combinados, múltiples páginas, archivo de pruebas y tres tipos de evidencia; comprobar diseño en móvil.

**Límites de la validación:** pruebas automatizadas y migraciones ejecutadas en SQLite temporal; no se ha podido ejecutar Streamlit en este entorno ni arrancar la app contra PostgreSQL real. La corrección del antiguo `KeyError` sigue pendiente de comprobación real en Cloud. En caso de fallo remitir traceback completo de `Manage app → Logs` sin Secrets.
