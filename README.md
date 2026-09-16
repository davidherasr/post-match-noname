# No Name · Área Técnica 4.4.3

Aplicación interna para el cuerpo técnico de No Name. Navegación: **Inicio · Jornada · Jugadores · Informes · Dirección Deportiva · Administración**, según permisos.

## Novedades 4.4.3 · Lectura breve y peticiones deportivas

- Lectura breve **predeterminada**, misma tabla de informes que el modo detallado: dos notas colectivas de pulsación completa, comentario opcional, hasta tres jugadores identificados y entrega con regreso inmediato a Inicio. Las notas históricas decimales y el informe completo se conservan. La falta de evaluación no equivale a cero.
- Seguimiento formal únicamente por **check explícito** del Informador que tenga permiso independiente: ningún ocho preselecciona ni inicia seguimiento. La nota es la misma que en su postpartido.
- Dirección Deportiva incorpora mesa, jugadores de interés y **peticiones de opinión voluntarias** a uno o varios Informadores, con identidad, temporada, pregunta, prioridad y partido objetivo opcional. Inicio y Match Hub muestran avisos contextualizados; respuestas con procedencia, vinculación a valoración original y estados/auditoría; no se reintroducen misiones Scout.
- «Informes» ya está conectado al menú de Informador/DD. Las notas en partidos neutrales también son botones completos, y editar su lectura preserva el ID de una señal ya enlazada a una respuesta.
- Corrección de mapeo del rol del modelo: no inventa estado «Observado», preserva la decisión y los datos anteriores. DD puede retirar, con auditoría y motivo, una observación independiente errónea sin borrar la nota original del postpartido.
- Migración nueva, aditiva y no destructiva: **0015_observation_requests_4_4_3**. Respaldo PostgreSQL y bucket antes de desplegar; instrucciones completas en `UPGRADE_4_4_3.md` y alcance de pruebas en `VALIDACION_4_4_3.md`.

## Historial 4.4.2 · Evidencia unificada y seguimiento visible

- El informe de No Name sigue incorporándose directamente al entregarlo. Si el Informador tiene permiso individual de seguimiento, a continuación se ofrece **un paso opcional** con los rivales ya puntuados; se sugieren notas ≥8, pero **nunca se crea un seguimiento sin selección y guardado explícitos**. El usuario puede terminar sin añadir ninguno.
- Para el mismo futbolista, partido y autor, la valoración del postpartido es la **nota única de referencia**. El seguimiento amplía comentario, fortalezas, riesgos y recomendación enlazándose a esa valoración en lugar de capturar una segunda nota. En Player Report 360 y su PDF aparece **una sola línea lógica «Postpartido + seguimiento»**.
- Reabrir un seguimiento del mismo partido reutiliza el registro existente; también se protegen los guardados por APIs históricas. Los duplicados anteriores **no se eliminan durante el despliegue**: DD puede examinarlos y eliminar un duplicado específico con confirmación, auditoría y protección del registro vinculado al postpartido.
- Dirección Deportiva dispone de un área **Seguimiento** con actividad real del staff (quién ha documentado a quién, partido y nota), filtro, acceso al jugador, decisiones por temporada y revisión excepcional de duplicados. No se restauran misiones Scout ni permisos heredados.
- Nuevo enlace opcional y restricción única en `scout_observations.player_evaluation_id`, mediante migración aditiva `0014_unified_player_evidence_4_4_2`. Consulta `UPGRADE_4_4_2.md` y `VALIDACION_4_4_2.md`; requiere **respaldo completo de PostgreSQL y del bucket** antes de desplegar.

# Historial: versión 4.4.1

Aplicación interna de No Name para postpartido, lectura compartida del staff, Dirección Deportiva y seguimiento individual de jugadores externos. La capa visible se organiza en **Inicio · Jornada · Jugadores · Dirección Deportiva · Administración**.

## Novedades 4.4.1

- Notas de jugadores y equipos por pulsación directa de 1 a 10 o «Sin evaluar», preservando notas históricas decimales.
- Entrega de informe vuelve a Inicio con confirmación y acceso al partido; el editor no permanece abierto tras entregar.
- Informadores pueden rechazar tareas opcionales; el motivo se audita, los borradores se preservan y Administración puede reactivar la asignación.
- DD puede asumir voluntariamente un postpartido publicado únicamente cuando su cuenta tiene también rol Informador.
- Sin nueva migración; consultar `UPGRADE_4_4_1.md` y `VALIDACION_4_4_1.md`.

## Novedades 4.4.0

- Inicio se convierte en centro operativo por roles con tareas reales, ultimo y proximo partido, actividad DD y accesos directos.
- Jornada prioriza la accion correcta segun estado y permiso; postpartido admite alineaciones parciales verificadas sin inventar titulares.
- Player Report 360 separa rendimiento propio y rival, respeta temporada en el comparador y distingue datos insuficientes del consenso.
- DD reorganiza accesos y evita controles segmentados extensos; Administracion separa mantenimiento avanzado del trabajo ordinario.
- No hay nueva migracion: sigue `0013_data_governance_4_2_3`.

## Cambios anteriores 4.2.3.2

- Administración → Datos → Eliminación definitiva: selección con casillas y controles en español por temporadas, partidos, equipos y jugadores; simulación de dependencias, confirmación irreversible y borrado SQL transaccional con auditoría. Los jugadores ligados a un equipo eliminado solo se proponen para selección explícita; nunca se borran automáticamente por similitud de nombre.
- Asignaciones de Informadores con selección reactiva y botón guardar operativo, sin esperar al envío de un formulario.
- Marca visible «No Name · Área Técnica», interfaz limpia de textos de desarrollo, nombres legibles sin IDs y selección masiva en español.
- Exportación tabular técnica de todas las tablas ORM. NO es un respaldo SQL restaurable y NO contiene los ficheros del bucket. Antes de un borrado permanente obtener `pg_dump` y guardar el bucket por separado.
- Mantiene la migración 0013 de 4.2.3 y NO añade cambios de esquema. No se borra ni altera ninguna fila productiva durante el despliegue; el borrado requiere acción expresa del Administrador.

## Flujo diario

- **Inicio**: partido de hoy/próximo partido y acciones pendientes.
- **Jornada**: distingue de forma explícita entre partidos de No Name y partidos neutrales.
- **Jugadores**: Player Report 360, evolución y seguimiento individual cuando exista evidencia real.
- **Dirección Deportiva**: lectura agregada del staff, pesos de opinión, Modelo No Name, plantilla y candidatos.
- **Administración**: usuarios, roles, calendario, equipos, plantillas, calidad de datos y configuración.

Los roles organizativos son **Administrador · Dirección Deportiva · Informador**. El seguimiento individual de jugadores **no es un rol Scout**: es un permiso adicional `Puede realizar seguimiento individual de jugadores`, activable solo para quienes realmente hagan ese trabajo.

## 4.2 · Lectura deportiva real

4.2 elimina el flujo artificial de `DD → asignar Scout → misión`. El trabajo se adapta a la estructura real del staff:

- **Partidos de No Name**: son postpartidos. Cada Informador puntúa el rendimiento colectivo de No Name, el rival y los jugadores que realmente haya podido valorar. Dirección Deportiva obtiene consensos ponderados, discrepancias y evolución. Los jugadores propios se tratan siempre como **rendimiento de plantilla**, nunca como objetivos de mercado.
- **Partidos neutrales**: cada miembro del staff deja una lectura ligera del partido, puntúa a ambos equipos y puede señalar jugadores que le hayan llamado la atención. Señalar un jugador genera una **señal**, no un seguimiento automático.
- **Dirección Deportiva**: dispone de un centro propio con tres áreas: `Lectura deportiva`, `Plantilla y modelo` y `Criterio del staff`. Puede dar más o menos peso a cada persona según se trate de partidos de No Name o partidos neutrales.
- **Seguimiento individual**: solo aparece a usuarios con el permiso especial. Desde una señal de DD o desde un partido se puede iniciar seguimiento de un jugador externo y alimentar su Player Report 360. El sistema impide abrir como objetivo de mercado a un jugador de No Name.
- **Administración**: ya no reparte trabajo deportivo. Prepara usuarios, datos, plantillas, calendario y horarios.

La migración no destructiva `0012_sporting_reading_4_2` añade el permiso individual, los pesos deportivos del staff, las lecturas de partidos neutrales y las notas colectivas No Name/rival. Los antiguos registros Scout se conservan como histórico y los usuarios con rol Scout heredado se convierten a **Informador + permiso de seguimiento individual**.

Las contraseñas siguen siendo deliberadamente libres para este entorno interno: cualquier valor no vacío es válido y cambiarlo es opcional.

## 4.0.7 · XI observado reactivo

En el editor de alineaciones con formación conocida, cada jugador seleccionado se elimina automáticamente de los desplegables de las demás posiciones. Esto hace más rápida la identificación del XI y evita duplicados desde la propia interfaz. El botón **Guardar XI** conserva además la validación de servidor que impide guardar un jugador dos veces.

4.0.7 no introduce cambios de esquema. Mantiene el mismo Supabase y el head Alembic `0010_core_workspace_schema_repair_4_0_4`.

## 4.0.3 · Hotfix de esquema real

4.0.3 corrige el fallo observado en producción donde PostgreSQL llegaba a `Inicio` con una revisión Alembic aparente compatible pero faltaban columnas físicas que el ORM de `Match` intentaba seleccionar. La nueva revisión `0009_schema_repair_4_0_3` es idempotente y no destructiva: comprueba y restaura únicamente columnas aditivas esperadas, y después valida el contrato físico antes de renderizar cualquier workspace.

No cambia de Supabase ni reinicia datos. Mantén `RUN_MIGRATIONS = true` para que el hotfix se aplique automáticamente al reiniciar Streamlit Cloud.

## 4.0.1 · Match Study + hotfix de despliegue

La 4.0 convierte los partidos neutrales en una ficha de estudio flexible. El vídeo se marca como disponible/no disponible y cada equipo puede tratarse de forma independiente: **formación conocida → campograma**; **formación desconocida → plantilla de Federación ordenada por dorsal**. Ya no es necesario inventar un sistema para poder estudiar a un rival.

También añade pegado rápido de plantillas federativas, XI observado sobre campograma, filtro Scout por equipo, contexto visible desde Jornada y una migración no destructiva `0008_match_study_4_0`.

**4.0.2** endurece el despliegue real en Streamlit Cloud: el paquete se entrega con raíz plana y el arranque detecta archivos mezclados antes de importar la aplicación. 4.0.1 ya corrigió: elimina físicamente el directorio especial `pages/`, mueve las vistas a `views/`, robusteciendo la conexión PostgreSQL/Supabase y mostrando un diagnóstico seguro si `DATABASE_URL` no es accesible. Consulta `UPGRADE_4_0_1.md`.

## 3.9 · Matchday y fiabilidad

La 3.9 se centra en empezar a usar la aplicación con datos reales con menos riesgo operativo. El día de trabajo se calcula en `Europe/Madrid`, Jornada prioriza automáticamente la ronda de No Name, Inicio destaca el partido del día y Administración permite comprobar en segundos si temporada, calendario y plantilla están preparados.

También se corrigen dos restos importantes de la arquitectura antigua: Informes respeta todos los roles del usuario y la herramienta secundaria de calendario ya no propone una hora ficticia ni navega a módulos retirados.

Para la prueba de Jornada 1 consulta `PRUEBA_REAL_J1.md`.

## Datos y Supabase

4.2.2 mantiene el mismo Supabase, `DATABASE_URL` y Secrets. El head Alembic esperado sigue siendo `0012_sporting_reading_4_2`; **4.2.2 no añade una migración nueva**. En PostgreSQL la columna `alembic_version.version_num` debe admitir los identificadores largos de 4.x (la aplicación la prepara a 128 caracteres cuando Alembic necesita ejecutarse). No se incluyen datos deportivos demo ni credenciales reales.

El hotfix 4.2.2 evita volver a ejecutar Alembic cuando la base ya está exactamente en el head de la release y el contrato físico del esquema es correcto. Esto reduce trabajo en cada arranque de Streamlit Cloud y protege frente al `KeyError` observado en 4.2.1 durante el arranque de base de datos. Si aparece otro error inesperado, la pantalla y los logs indican ahora la fase exacta: configuración, migraciones/esquema, bootstrap o carga de ajustes.

## Validación

Consulta `VALIDACION_4_2_2.md`. La release se valida con `compileall`, suite automatizada, consistencia interna y migraciones fresh/upgrade hasta `0012`.
## 4.0.5 · Hotfix de navegación

4.0.5 corrige la navegación desde tarjetas y tareas: las vistas ya no escriben directamente en el estado del widget `main_navigation` después de que Streamlit haya creado el radio lateral. La navegación se solicita mediante un estado pendiente y se aplica en el siguiente rerun antes de construir el widget. También protege PostgreSQL ampliando automáticamente la columna de versión de Alembic a 128 caracteres.
