# CONTEXTO MAESTRO · NO NAME · ÁREA TÉCNICA 4.4.4.1

**Fecha de corte:** 28 de octubre de 2026  
**Versión de código de referencia:** 4.4.4.1  
**Alembic head incluido:** `0015_observation_requests_4_4_3`  
**Objeto de este documento:** entregar a otro chat/desarrollador todo el contexto necesario para continuar el proyecto sin reconstruirlo de memoria, sin mezclar releases y sin perder decisiones funcionales ya tomadas.

---

## 0. INSTRUCCIONES PARA EL CHAT NUEVO — LEER ANTES DE TOCAR CÓDIGO

1. **Usar el ZIP completo `NoName_Area_Tecnica_4.4.4.1.zip` como única base de código.** No reconstruir la aplicación desde conversaciones, recuerdos o versiones anteriores. Los documentos históricos sirven para entender decisiones, no para sustituir los archivos actuales.
2. **No mezclar releases.** Si se modifica la aplicación, partir de la 4.4.4.1 completa y entregar siempre un ZIP completo de la nueva versión.
3. **No tocar Supabase de forma destructiva para “arreglar” un error.** No resetear, no recrear tablas, no borrar datos por intuición. Toda migración debe ser aditiva/no destructiva salvo una operación administrativa explícita de borrado definitivo.
4. **No declarar una versión validada sin ejecutar realmente** `pytest`, `compileall`, consistencia de release y las migraciones que correspondan en bases aisladas. El hecho de que los tests locales pasen no equivale a haber validado Streamlit Cloud, PostgreSQL real, Secrets, navegador o Storage.
5. **Preservar autoría, procedencia y tamaño de muestra.** Una nota sabe quién la hizo, en qué partido y con qué fuente. Una única opinión no es consenso. Dato desconocido no debe convertirse en cero, titular inventado, hora inventada ni identidad inventada.
6. **No recuperar el organigrama Scout antiguo.** Los roles operativos actuales son Administrador, Dirección Deportiva e Informador, acumulables. El seguimiento individual profundo es una capacidad separada (`can_track_players`). Las tablas Scout antiguas siguen existiendo por compatibilidad/histórico y no deben eliminarse a ciegas.
7. **El equipo propio se resuelve por identidad estable, no por nombre.** El club real es `C.D. Noname`. Históricamente existió un equipo ficticio `Noname Club` y dos partidos de prueba contra Santa Marta. La aplicación dispone de gobierno de datos para marcar/archivar; no se debe fusionar el club ficticio con el real ni inferir IDs por el texto del nombre.
8. **La 4.5 se diseñará para quitar trabajo al Administrador y al Informador, no para empobrecer DD.** Dirección Deportiva debe recibir más información “masticada”: contexto, muestra, señales, discrepancias, preguntas sugeridas y siguiente acción, manteniendo métricas y profundidad en segundo nivel.

---

# 1. QUÉ ES LA APLICACIÓN

**No Name · Área Técnica** es una aplicación interna en Streamlit para el cuerpo técnico de No Name. Su finalidad es centralizar calendario, postpartido, lecturas de liga, evaluaciones de jugadores, seguimiento individual, inteligencia de Dirección Deportiva, Modelo No Name, documentación y gobierno del dato.

No pretende ser un proveedor estadístico externo ni un sistema de scouting profesional genérico. No calcula xG, GPS, eventos Opta/Wyscout ni valoración económica salvo que alguien los introduzca explícitamente. Su activo principal es el **conocimiento humano del staff** y su trazabilidad.

La aplicación ha evolucionado desde un producto de scouting más genérico hacia una herramienta específica de No Name. El diseño correcto actual distingue:

- **Partidos de No Name:** postpartido y evolución del equipo propio y del rival.
- **Partidos neutrales:** lectura ligera de liga, señales sobre equipos y jugadores externos.
- **Seguimiento individual:** ampliación deliberada sobre futbolistas externos; no se inicia automáticamente por una nota alta.
- **Dirección Deportiva:** interpreta evidencia agregada, detecta discrepancias, gestiona decisiones, necesidades, Modelo No Name y peticiones de opinión.
- **Administración:** usuarios, identidad del club, datos, catálogos, correcciones y mantenimiento.

Principios del producto que ya están asentados:

- Una sola identidad por partido real.
- Capturar una vez y reutilizar muchas veces.
- No inventar conocimiento.
- No confundir plantilla, convocatoria, titularidad, formación y participación.
- No confundir señal ligera con seguimiento formal.
- No tratar jugadores de No Name como candidatos de mercado.
- Roles reales, acumulables, con autorización en backend.
- Integridad histórica y migraciones no destructivas.
- Interfaz orientada a la realidad de un cuerpo técnico amateur/semiamateur con poco tiempo.

---

# 2. ESTADO VERIFICADO DE LA 4.4.4.1

La fuente revisada es el ZIP completo de 4.4.4.1. En esta auditoría se ha ejecutado:

- `pytest -q`: **167 pruebas superadas**.
- `python -m compileall -q .`: **correcto**.
- `python scripts/check_release_consistency.py`: **correcto**.
- Consistencia informada por el script: **No Name · Área Técnica 4.4.4.1 · Alembic `0015_observation_requests_4_4_3`**.

Esto valida el paquete local y sus contratos automatizados. **No prueba por sí solo**:

- arranque de Streamlit Cloud,
- compatibilidad con todos los datos reales de PostgreSQL,
- Secrets actuales,
- conectividad real con Supabase,
- comportamiento visual en navegador/móvil,
- concurrencia real,
- restauración completa desde backup,
- almacenamiento de PDFs en bucket.

### Último incidente de arranque conocido

La 4.4.4 falló en Streamlit Cloud durante `migraciones / validación de esquema` con `ModuleNotFoundError`. La 4.4.4.1 es un hotfix de arranque:

- fuerza `postgresql+psycopg` para URLs PostgreSQL sin driver explícito,
- incluye `psycopg[binary]` y `psycopg2-binary`,
- valida dependencias de runtime antes de entrar en migraciones,
- muestra el nombre del módulo si falta,
- mantiene Alembic en 0015, sin migración nueva.

También se observaron logs de **Supabase Realtime** con `queue_timeout` y `Database supervisor not found`. Esos logs pertenecen al servicio Realtime/Ecto de Supabase y no deben confundirse automáticamente con una migración Alembic de la aplicación. Nunca ejecutar `mix ecto.drop/create` sobre el proyecto de la app por ese mensaje genérico.

Si el siguiente chat no tiene confirmación posterior, debe considerar **pendiente** la validación final de 4.4.4.1 en Cloud.

---

# 3. INFRAESTRUCTURA Y DESPLIEGUE

## 3.1 Stack

- Python.
- Streamlit `>=1.49,<2`.
- SQLAlchemy 2.x.
- Alembic 1.17+.
- PostgreSQL/Supabase en producción.
- SQLite solo para demo/tests/local.
- Psycopg 3 binario como driver preferente; psycopg2 binario permanece por compatibilidad.
- Pandas/OpenPyXL para exportaciones.
- ReportLab para PDF.
- Cliente Supabase para Storage privado de PDFs.

## 3.2 Secrets / variables importantes

- `DATABASE_URL` — en Streamlit Cloud se recomienda **Session pooler** de Supabase.
- `DEMO_MODE`.
- `RUN_MIGRATIONS` — normalmente `true`.
- `REQUIRE_REPORT_APPROVAL` — heredado; el producto actual usa incorporación directa y el default es `false`.
- `BOOTSTRAP_ADMIN_NAME`.
- `BOOTSTRAP_ADMIN_EMAIL`.
- `BOOTSTRAP_ADMIN_PASSWORD`.
- `LOGIN_MAX_ATTEMPTS` — default 5.
- `LOGIN_LOCK_MINUTES` — default 15.
- `SUPABASE_URL`.
- `SUPABASE_SERVICE_ROLE_KEY`.
- `SUPABASE_BUCKET` — default histórico `postmatch-reports`.
- `LOCAL_STORAGE_DIR`.

En producción no se permite contraseña bootstrap predeterminada. La app detecta placeholders `PROJECT_REF`, `PASSWORD`, `REGION`.

## 3.3 Arranque

`app.py` ejecuta, en este orden conceptual:

1. `st.set_page_config` antes de imports internos.
2. Validación de que `core/config.py` pertenece a la misma release.
3. `validate_production_settings()`.
4. `init_db()`.
5. `bootstrap_application()`.
6. carga de `app_settings`.
7. estilos.
8. login / sesión / navegación.

`init_db()`:

- valida dependencias,
- prueba conectividad con reintentos,
- reutiliza la misma conexión para Alembic,
- si PostgreSQL ya está exactamente en el head incluido, evita entrar innecesariamente en Alembic y valida el esquema físico,
- ejecuta `alembic upgrade head` si procede,
- valida un contrato explícito de columnas físicas antes de renderizar workspaces.

Este diseño existe por incidentes anteriores donde la tabla `alembic_version` podía no reflejar un esquema físico completo y por un `KeyError` de Alembic en una versión anterior.

## 3.4 Backup y restauración

La aplicación tiene una **exportación técnica tabular** de todas las entidades ORM. No es un backup restaurable de producción.

Para recuperación real se necesita:

- `pg_dump` / respaldo PostgreSQL restaurable,
- copia separada del bucket/documentos,
- prueba de restauración en entorno aislado.

El ZIP del repositorio no contiene la base productiva. La exportación JSON/XLSX tampoco sustituye un dump SQL.

---

# 4. ESTRUCTURA DEL REPOSITORIO

- `app.py`: arranque, login, sidebar, router principal.
- `core/`: configuración, permisos, autenticación, base de datos, calendario, reglas de evaluación, formaciones, navegación, seguridad, presentación y utilidades.
- `models/entities.py`: modelo SQLAlchemy completo.
- `repositories/`: acceso a datos y lógica de dominio por áreas.
- `views/`: pantallas Streamlit.
- `ui/`: componentes visuales compartidos, campograma y Player 360.
- `reports/`: generación de PDFs.
- `services/`: bootstrap, exportación, almacenamiento, importación, salud y report service.
- `alembic/versions/`: migraciones.
- `tests/`: 37 ficheros de pruebas en esta release.
- documentación histórica `ANALISIS_*`, `UPGRADE_*`, `VALIDACION_*`, etc.

La release contiene 139 archivos Python en total contando aplicación, tests y migraciones.

---

# 5. NAVEGACIÓN ACTUAL

El menú visible depende de permisos:

- **Inicio** — todos.
- **Jornada** — todos.
- **Jugadores** — todos.
- **Informes** — Informador o Dirección Deportiva.
- **Dirección Deportiva** — rol DD.
- **Administración** — rol Admin.

No existe selector de “perfil activo”. Los roles son acumulables.

---

# 6. ROLES Y AUTORIZACIÓN ACTUAL

## 6.1 Roles organizativos

- `admin` → Administrador.
- `reporter` → Informador.
- `director` → Dirección Deportiva.

Se almacenan tanto el rol primario legado (`users.role`) como los roles acumulables en `user_roles`.

## 6.2 Capacidad separada

`users.can_track_players` controla seguimiento individual profundo de jugadores externos. No es un rol Scout.

## 6.3 Reglas importantes de 4.4.4.1

- Admin **no hereda automáticamente** Informador.
- DD **no hereda automáticamente** Informador.
- Para firmar/escribir una valoración de postpartido hay que tener rol Informador.
- Para seguimiento formal hace falta `can_track_players`.
- Para crear peticiones de opinión hace falta DD.
- Operaciones administrativas destructivas requieren Admin.

En la 4.5 se quiere revisar la experiencia de roles, pero **no debe perderse la separación de autoría deportiva**. Admin puede ser superusuario de gestión/consulta, pero una corrección administrativa no debe fingir ser una opinión deportiva de otra persona.

---

# 7. SEGURIDAD DE USUARIOS Y SESIÓN

- Login con hash de contraseña.
- Cuenta bloqueada temporalmente tras varios intentos fallidos.
- Default: 5 fallos → 15 minutos.
- Los intentos se auditan.
- No se puede desactivar/eliminar el último Administrador activo.
- Un usuario no puede desactivarse/eliminarse a sí mismo durante la sesión.
- Eliminación de usuario es **soft delete** para preservar histórico.
- Restauración de usuario conserva identidad histórica.
- `session_revision` invalida sesiones tras cambios sensibles.
- La sesión se revalida con TTL aproximado de 90 segundos para no golpear PostgreSQL en cada rerun.
- Cambio de contraseña es opcional.

---

# 8. MODELO DE DATOS ACTUAL — 42 ENTIDADES

Las tablas actuales deben tratarse como histórico válido. No borrar tablas “legacy” sin trazar dependencias.

## 8.1 Usuarios y auditoría

1. `users` — identidad, acceso, rol primario legado, bloqueo, `can_track_players`.
2. `user_roles` — roles acumulables.
3. `login_attempts` — auditoría de acceso.
4. `audit_logs` — acciones sobre datos y administración.
5. `app_settings` — ajustes globales, identidad visual y `own_team_id`.
6. `staff_sporting_weights` — pesos de cada miembro para partidos propios y neutrales.

## 8.2 Catálogo deportivo

7. `seasons`.
8. `competitions`.
9. `teams` — incluye `is_own_team`, `is_test`, `archived_at`, `active`.
10. `players` — identidad global, posición primaria, alias textual, foto.
11. `player_aliases` — alias normalizados.
12. `player_merge_logs` — trazabilidad de fusiones.
13. `team_rosters` — pertenencia jugador/equipo/temporada y dorsal. **En 4.4.4.1 no guarda posición habitual por equipo/temporada.**

## 8.3 Partido y participación

14. `matches` — jornada, fecha, ventanas, kickoff, estado horario, tipo, equipos, resultado, campo, formaciones, vídeo, estado, test/archivo, revisión.
15. `participations` — partido/equipo/jugador, dorsal, titular, posición del partido, minutos, capitán. **`player_id` es obligatorio en 4.4.4.1; no existe todavía un “jugador desconocido por posición”.**

## 8.4 Postpartido de No Name

16. `report_assignments` — asignación de Informadores, required, due, estado.
17. `reports` — una lectura por partido/autor con equipo propio, rival, notas colectivas, textos, estado y versión.
18. `player_evaluations` — valoraciones individuales own/rival por informe/jugador.
19. `report_versions` — snapshot de versiones de informe.
20. `documents` — metadatos de PDFs/Storage.
21. `postmatch_drafts` — borradores de preparación.
22. `consolidated_reports` — histórico/compatibilidad de agregados antiguos.
23. `consolidated_player_evaluations` — histórico/compatibilidad de consensos antiguos.

## 8.5 Lectura neutral

24. `match_opinions` — una lectura por partido neutral/usuario; nota local, visitante y resumen.
25. `match_opinion_players` — señales de jugadores dentro de esa lectura.

## 8.6 Seguimiento / scouting histórico y actual

26. `follow_ups`.
27. `follow_up_history`.
28. `league_player_profiles`.
29. `scouting_lists`.
30. `scouting_list_items`.
31. `scouted_player_profiles` — expediente externo por jugador; sigue usándose como puente de identidad para seguimiento.
32. `scout_reviews` — legado.
33. `scout_missions` — legado del organigrama Scout retirado; no reactivar como flujo normal.
34. `scout_mission_targets` — legado.
35. `scout_observations` — observación formal actual/compatibilidad; puede enlazarse a `player_evaluation_id` para ampliar una nota sin duplicarla.

## 8.7 Modelo No Name y planificación

36. `game_model_roles` — roles deportivos configurados por DD.
37. `game_model_criteria` — criterios por rol y peso.
38. `squad_needs` — necesidad de plantilla por temporada/rol.
39. `player_season_decisions` — estado, prioridad, rol, encaje, nivel, proyección, criterios y conclusión DD.

## 8.8 Peticiones voluntarias de DD

40. `player_observation_requests` — pregunta de DD sobre jugador externo/temporada/partido opcional.
41. `player_observation_recipients` — destinatarios Informador y estado.
42. `player_observation_responses` — respuesta, partido y enlaces a evidencia existente.

---

# 9. IDENTIDAD DEL EQUIPO PROPIO Y DATOS DE PRUEBA

La aplicación dispone de dos referencias históricas:

- `teams.is_own_team`.
- `app_settings['own_team_id']`.

La lógica actual permite sincronizarlas desde Administración. El equipo real es **C.D. Noname**. No resolver por texto “Noname”; usar ID configurado.

Gobierno del dato:

- equipos pueden marcarse `is_test`, archivarse reversiblemente y restaurarse;
- partidos pueden marcarse `is_test`, archivarse reversiblemente y restaurarse;
- el equipo propio está protegido frente a archivo/test;
- `official_match_clause()` excluye partidos archivados, borrados, test y partidos de equipos test/archivados;
- `official_team_clause()` excluye equipos test/archivados.

Histórico de negocio a recordar: existió `Noname Club` como club de prueba y dos encuentros de prueba contra Santa Marta. No fusionar ese club con C.D. Noname. No asumir que siguen existiendo en producción; comprobar por ID si se necesita intervenir.

Además existe **borrado definitivo** desde Mantenimiento avanzado para temporadas, partidos, equipos y jugadores con selección múltiple, preview de dependencias, confirmación fuerte, transacción y auditoría. Es una operación consciente e irreversible, distinta del archivado.

---

# 10. FLUJO ACTUAL DE INICIO

`Inicio` intenta ser un workspace por rol.

## 10.1 Informador

- tareas de postpartido asignadas;
- botón directo para rellenar;
- rechazo de asignación opcional;
- peticiones de DD;
- último y próximo partido de No Name.

## 10.2 Administrador

El workspace todavía genera trabajo administrativo de:

- partidos propios pasados en `scheduled/draft` → “Preparar postpartido”;
- partidos publicados sin asignados → “Asignar Informadores”;
- horarios pendientes → “Confirmar horario”.

Esta carga administrativa es uno de los motivos principales para la 4.5.

## 10.3 Dirección Deportiva

- tablero compacto de peticiones;
- métricas de jugadores señalados, necesidades altas y jugadores en evaluación;
- seguimiento reciente;
- informes incorporados recientemente;
- lecturas neutrales recientes.

Problema de producto: los datos existen pero aparecen como secciones separadas; DD todavía tiene que interpretar demasiado manualmente qué merece atención.

---

# 11. JORNADA ACTUAL

Jornada es el centro de navegación por encuentros.

## 11.1 Selección de jornada

- lista de jornadas de temporada activa;
- “Primera jornada”;
- “Ir a la jornada actual”;
- anterior/siguiente;
- filtro Todos / No Name / Otros equipos;
- buscador de equipo.

`default_round()` en 4.4.4.1 busca principalmente el **siguiente partido por `match_date >= hoy`**, preferentemente de No Name. No usa de forma prioritaria `window_start/window_end`, por lo que puede colocarse en una jornada que no corresponde al fin de semana operativo real. Debe corregirse en 4.5.

## 11.2 Tarjetas

- No Name aparece primero.
- Para neutrales se indica vídeo y formaciones conocidas.
- Se muestran asignaciones si existen.
- Informador puede pulsar “Realizar lectura voluntaria” en neutrales sin asignación.

## 11.3 Herramientas de calendario

Para Admin están escondidas bajo “Importar calendario / mantenimiento excepcional”. Incluyen importación, listado y confirmación de horarios.

En 4.4.4.1 el concepto de horario exacto todavía tiene demasiado peso operativo.

---

# 12. MATCH HUB ACTUAL

Al abrir un partido:

- cabecera con equipos, competición y jornada;
- programación provisional/confirmada;
- resultado si existe;
- acceso a ficha de cada club;
- acción principal según estado/permiso;
- asignaciones/informes si es partido propio;
- estudio/lectura neutral si no participa No Name;
- peticiones de DD contextualizadas;
- DD puede consultar lectura agregada;
- seguimiento individual opcional según permisos.

## 12.1 Problema central actual

Para un partido propio en `scheduled/draft`, el botón Admin “Preparar partido” solo aparece si el horario está confirmado. Para un Informador, el informe propio depende de asignación activa, salvo el caso especial DD+Informador que puede reclamarse voluntariamente tras publicación.

Esto significa que el administrador sigue siendo un **gatekeeper operativo** para el postpartido propio. La 4.5 debe eliminar esa dependencia.

---

# 13. CALENDARIO Y HORARIOS ACTUALES

El calendario acepta importación textual:

- `jornada;fecha;local;visitante`
- opcionalmente hora.

Existe `window_start` y `window_end` en el modelo, pero el flujo actual mantiene una semántica muy centrada en fecha orientativa + hora definitiva.

`is_schedule_confirmed(match)` exige:

- `schedule_status == 'confirmed'`
- `kickoff_at` no nulo.

`get_or_create_report()` bloquea un informe nuevo para partidos `draft/scheduled` sin hora confirmada.

`validate_postmatch_draft()` exige hora definitiva antes de publicar.

La 4.5 debe convertir la **ventana de fin de semana** en programación operativamente suficiente y relegar la hora exacta a metadato opcional.

---

# 14. PREPARACIÓN DEL POSTPARTIDO ACTUAL

Solo Administración puede preparar.

Asistente de cuatro pasos:

1. Partido.
2. No Name.
3. Rival.
4. Publicar.

Características:

- trabaja sobre el Match existente cuando procede;
- resultado puede ser desconocido;
- alineaciones pueden ser parciales;
- no debe inventar XI;
- conserva participantes ya verificados;
- puede importar/pegar listas;
- permite seleccionar Informadores;
- al publicar pone el partido en `published` y crea asignaciones.

Validación actual de publicación:

- **hora definitiva obligatoria**;
- XI propio puede ser parcial, con warning;
- XI rival puede ser parcial, con warning;
- al menos un Informador obligatorio.

Estas dos obligaciones —hora y asignación— son precisamente dos de las piezas que la 4.5 debe retirar como requisitos para que el resto del staff pueda trabajar.

---

# 15. INFORMES DE NO NAME ACTUALES

## 15.1 Incorporación directa

Desde 4.2.3, entregar un informe lo lleva a estado `incorporated`. No existe aprobación obligatoria de DD para que sus datos entren en agregados.

Los estados históricos `submitted/approved/final` se conservan y no se reescriben masivamente.

## 15.2 Lectura breve actual

Es el modo predeterminado.

Permite:

- nota de No Name del 1 al 10 o “Sin evaluar”;
- nota del rival del 1 al 10 o “Sin evaluar”;
- conclusión opcional;
- seleccionar hasta 3 jugadores **identificados en las participaciones del partido**;
- nota y/o apunte por jugador;
- check explícito de seguimiento formal para rival si el usuario tiene permiso;
- guardar borrador;
- entregar y volver a Inicio.

Las notas se eligen mediante `st.pills` con botones enteros; las notas decimales históricas se preservan como opción sin redondearlas.

## 15.3 Tolerancia actual a informe parcial

El backend de 4.4.4.1 ya permite entregar si existe **cualquier aportación sustantiva**, por ejemplo:

- una sola nota colectiva de cualquiera de los dos equipos;
- una valoración individual válida;
- un apunte individual de longitud suficiente;
- contexto textual suficiente.

Por tanto, **ya es técnicamente posible puntuar solo No Name y dejar el rival sin evaluar**, o viceversa.

Sin embargo, la interfaz todavía presenta ambos equipos de forma simétrica y el flujo detallado sigue teniendo pasos No Name → Rival → Entregar. La 4.5 debe hacer explícita la libertad de elegir:

- solo No Name,
- solo rival,
- ambos,
- solo jugadores concretos/destacados,
- o combinación de los anteriores.

Los campos vacíos deben ser normales, no “pendientes”.

## 15.4 Modo detallado

Existe como opción secundaria y permite recorrer jugadores propios y rivales, comentarios, estados de observación y documentos.

No debe desaparecer en 4.5, pero debe quedar claramente detrás del modo básico.

---

# 16. ASIGNACIONES Y RECHAZO ACTUALES

`ReportAssignment` contiene:

- partido,
- usuario,
- quién asignó,
- required,
- due,
- estado.

El Informador puede rechazar una asignación pendiente; la tarea desaparece y un borrador existente se conserva. Admin puede reactivarla.

Problema de 4.4.4.1: en partidos propios, la escritura sigue siendo **assignment-driven**. Si existen asignaciones y el usuario no está entre ellas, no puede crear el informe normal salvo rutas especiales.

En 4.5 las asignaciones deben pasar a significar **prioridad o petición**, no permiso de acceso al partido.

---

# 17. LECTURA NEUTRAL ACTUAL

Un Informador puede realizar voluntariamente una lectura de un partido donde no juega No Name, sin asignación Admin.

Permite:

- nota del local o “Sin evaluar”;
- nota del visitante o “Sin evaluar”;
- resumen;
- seleccionar jugadores identificados;
- nota/apunte de jugadores;
- confirmación de que ha visto el encuentro.

Se almacena una lectura por partido/usuario. Editarla reutiliza el mismo registro y preserva IDs de señales ya enlazadas a respuestas DD cuando corresponde.

La lógica ya tolera una nota de un solo equipo. En 4.5 debe homogeneizarse con la filosofía general de aportación parcial y evitar registros completamente vacíos que no añadan conocimiento.

---

# 18. JUGADORES DESCONOCIDOS: LIMITACIÓN ACTUAL

En 4.4.4.1 la evaluación individual requiere un `player_id` real:

- `Participation.player_id` no es nullable.
- `PlayerEvaluation.player_id` y `MatchOpinionPlayer.player_id` son identidades reales.

Por tanto, hoy no se puede expresar correctamente:

> “Me gustó el extremo izquierdo del River, no sé cómo se llama.”

Sin inventar un jugador ficticio, que no se debe hacer.

Esta carencia es crítica para el uso real en fútbol regional y debe resolverse en 4.5 con una entidad de señal temporal/no identificada, reconciliable posteriormente.

---

# 19. POSICIONES Y MEMORIA DE PLANTILLA: LIMITACIÓN ACTUAL

- `players.primary_position` guarda posición global del jugador.
- `participations.position` guarda posición en un partido concreto.
- `team_rosters` guarda dorsal y pertenencia, **pero no posición habitual para ese equipo/temporada**.

Resultado: si se aprende que Pedro Fernández es LD del Cubillos, la aplicación no tiene todavía un sitio correcto para recordar “LD habitual en Cubillos 26/27” sin confundirlo con una posición global eterna.

La 4.5 debe añadir memoria de posición por plantilla/temporada y usar prioridad:

1. posición del partido si está documentada,
2. posición habitual equipo/temporada,
3. posición primaria global,
4. desconocida.

---

# 20. CAMPOS Y FORMACIONES ACTUALES

El modelo de partido ya guarda por separado:

- `home_formation` / `away_formation`,
- `home_formation_known` / `away_formation_known`.

El sistema dispone de editor de formación/campograma y no obliga a conocer ambos equipos.

La 4.5 puede aprovechar esto para que una formación conocida genere **slots posicionales clicables** aunque no se conozcan nombres. La última formación observada debe poder sugerirse como punto de partida, nunca marcarse automáticamente como formación confirmada del partido nuevo.

---

# 21. SEGUIMIENTO INDIVIDUAL ACTUAL

El seguimiento formal:

- es solo para futbolistas externos;
- requiere `can_track_players`;
- no se crea automáticamente por nota ≥8;
- puede enlazarse a una `PlayerEvaluation` de postpartido;
- la nota de referencia sigue siendo la misma del partido;
- el seguimiento añade contexto, fortalezas, debilidades, recomendación, etc.;
- el enlace `scout_observations.player_evaluation_id` es único;
- existen defensas para reutilizar observación del mismo contexto y DD puede revisar duplicados históricos.

No reintroducir un segundo registro de nota para “seguimiento” del mismo jugador/partido/autor.

---

# 22. PETICIONES DE OPINIÓN DE DIRECCIÓN DEPORTIVA

Desde 4.4.3 existe un flujo voluntario separado de las antiguas misiones Scout.

DD puede:

- elegir jugador externo,
- temporada,
- uno o varios Informadores,
- pregunta concreta,
- prioridad Normal/Alta,
- partido objetivo opcional.

El Informador puede responder:

- Lo vi.
- No pude verlo.
- No jugó (según informador).
- Ahora no.
- Prefiero no responder.

La petición puede enlazar a evidencia ya existente (`PlayerEvaluation` o señal neutral) en lugar de crear otra nota.

El sistema distingue:

- participación confirmada,
- posible coincidencia por roster,
- ausencia de evidencia.

No inferir que jugó por estar en plantilla.

En 4.5 este mecanismo debe volverse más contextual: desde una señal concreta DD debe poder preguntar, por ejemplo, **“¿Por qué le diste un 8?”**, manteniendo el vínculo con esa misma evidencia.

---

# 23. JUGADORES DE INTERÉS ACTUALES

Después del fix 4.4.4, “Jugadores de interés” no son todos los jugadores señalados.

Hay dos conceptos separados:

### Selección DD

Un jugador entra por decisión expresa (`Interesante`, `Seguimiento`, `Prioritario`), petición abierta o seguimiento formal.

### Descubrimiento por nota

Filtro independiente:

- media ponderada ≥ 8,
- muestra mínima configurable, por defecto 2 partidos,
- no se incorpora automáticamente a la selección.

DD debe pulsar “Añadir a selección”.

Esta distinción se debe mantener en 4.5.

---

# 24. CATÁLOGO DE JUGADORES ACTUAL

La pantalla Jugadores dispone de:

- temporada,
- equipo,
- posición,
- ámbito,
- estado,
- evidencia,
- orden,
- búsqueda,
- paginación,
- comparador.

Las tarjetas agregan:

- equipo actual conocido,
- estado DD,
- prioridad,
- media de postpartido,
- nº de evaluaciones/partidos/autores,
- última evaluación,
- destacados,
- menciones neutrales,
- seguimiento formal.

Propio y externo se distinguen conceptualmente, aunque la 4.5 puede hacer esa diferencia aún más clara.

---

# 25. PLAYER REPORT 360 ACTUAL

La ficha reúne:

- identidad y equipo,
- edad,
- temporada,
- rendimiento postpartido separado own/rival,
- confianza/muestra,
- posiciones observadas,
- seguimiento formal,
- criterios del Modelo No Name,
- encaje, nivel actual y proyección,
- fortalezas/debilidades,
- decisión DD,
- timeline,
- mensual/temporada,
- comparación,
- documentos PDF.

Para jugadores propios, la cabecera usa evidencia de rendimiento propio, no scouting rival.

Observaciones duplicadas históricas se deduplican lógicamente para métricas sin borrar físicamente el histórico.

---

# 26. DIRECCIÓN DEPORTIVA ACTUAL

La navegación DD contiene:

1. Mi mesa de trabajo.
2. Jugadores de interés.
3. Peticiones de opinión.
4. Lectura deportiva.
5. Seguimiento.
6. Plantilla y modelo.
7. Criterio del staff.

## 26.1 Mi mesa de trabajo

Es principalmente un acceso a peticiones y botones hacia otras áreas. Todavía no es un feed realmente “masticado”.

## 26.2 Lectura deportiva

`league_intelligence()` ya combina:

- señales de jugadores en neutrales,
- valoraciones de rivales en postpartidos No Name,
- medias ponderadas por staff,
- nº de menciones,
- nº de partidos,
- nº de miembros del staff,
- dispersión,
- consenso,
- tendencia,
- notas,
- procedencia neutral/postpartido,
- equipos,
- discrepancias por partido.

Es decir: **la materia prima para una DD mucho más inteligente ya existe**.

## 26.3 Seguimiento

Muestra actividad formal, autor, partido, nota, conclusión, recomendación, ficha, decisión y duplicados.

## 26.4 Plantilla y modelo

- roles del Modelo No Name,
- criterios ponderados,
- necesidades,
- jugadores propios mapeados,
- candidatos externos,
- encaje,
- próxima oportunidad.

## 26.5 Criterio del staff

DD puede configurar pesos distintos de cada persona para:

- partidos de No Name,
- partidos neutrales.

La ponderación no cambia la nota original ni la autoría.

## 26.6 Problema de producto

DD tiene mucha información, pero repartida en cajones. La 4.5 no debe “simplificarla” eliminando contenido; debe **mascarla**: detectar qué merece atención, explicar por qué, mostrar muestra/procedencia y ofrecer la siguiente acción.

---

# 27. FICHA DE EQUIPO ACTUAL

Es todavía una vista contextual relativamente pequeña:

- próximo partido contra No Name si existe,
- número de jugadores conocidos,
- algunos estados DD,
- último XI documentado,
- plantilla con buscador,
- lectura acumulada reciente.

No es todavía un dossier de rival completo. En 4.5 debe convertirse en una ficha “masticada” con estructuras observadas, jugadores señalados, evidencia, discrepancias y acceso a partidos.

---

# 28. ADMINISTRACIÓN ACTUAL

Secciones:

- Usuarios.
- Club.
- Datos.
- Configuración.
- Mantenimiento avanzado.

## Usuarios

- alta/edición,
- roles múltiples,
- capacidad de seguimiento,
- activar/desactivar,
- contraseña,
- eliminar/restaurar,
- protección último Admin.

## Club

- equipo propio,
- datos de prueba/archivo,
- identidad visual/documentos.

## Datos

- estado de datos reales,
- búsquedas,
- calidad y duplicados.

## Configuración

- temporadas,
- competiciones,
- equipos,
- plantillas.

## Mantenimiento avanzado

- correcciones excepcionales de informes,
- borrado físico,
- herramientas técnicas/exportación/auditoría.

Problema de 4.4.4.1: Admin sigue recibiendo tareas operativas que no deberían depender de él semanalmente. La 4.5 debe convertir Admin en **mantenimiento y corrección**, no aprovisionador obligatorio.

---

# 29. PDF Y DOCUMENTOS

Existen PDFs de informe y Player 360. Los documentos guardan checksum y pueden almacenarse localmente y/o en Supabase Storage.

La 4.4.4 corrigió un problema de nombres largos y notas extensas en Player 360. El PDF sigue siendo un producto compartible y debe preservar:

- autoría,
- fecha,
- fuente,
- tamaño de muestra,
- una sola evidencia lógica cuando postpartido y seguimiento están enlazados.

---

# 30. MIGRACIONES ALEMBIC — HISTORIAL RELEVANTE

- `0001_initial_2_0` — esquema inicial 2.0.
- `0002_noname_3_0` — edición No Name.
- `0003_league_intelligence_3_2` — inteligencia y borradores.
- `0004_scout_workflow_3_3` — scouting avanzado histórico.
- `0005_planning_scout_3_5` — calendario, multirrol y planificación.
- `0006_player_report_360_3_6` — Player 360.
- `0007_product_consolidation_3_8` — consolidación.
- `0008_match_study_4_0` — estudio de partidos neutrales.
- `0009_schema_repair_4_0_3` — reparación física.
- `0010_core_workspace_schema_repair_4_0_4` — reparación workspace.
- `0011_user_lifecycle_4_1_1` — ciclo de vida usuarios.
- `0012_sporting_reading_4_2` — lectura deportiva/pesos.
- `0013_data_governance_4_2_3` — test/archivo reversible.
- `0014_unified_player_evidence_4_4_2` — enlace postpartido-seguimiento.
- `0015_observation_requests_4_4_3` — peticiones/respuestas DD.

4.4.4 y 4.4.4.1 no añaden migración.

---

# 31. DEUDAS Y LIMITACIONES CONFIRMADAS DE 4.4.4.1

Estas son importantes para que el chat nuevo no las vuelva a “descubrir” de cero:

1. **Horario exacto como gate:** todavía bloquea preparación/informe en varios caminos.
2. **Asignación como gate del postpartido propio:** un Informador normal no puede simplemente abrir cualquier partido propio y aportar.
3. **Publicación manual:** el Admin todavía debe preparar/publicar para generar el flujo propio.
4. **Admin como cuello de botella:** Inicio le genera horarios, preparación y asignación.
5. **Jornada actual:** se resuelve por próxima fecha, no por ventana de fin de semana como criterio principal.
6. **Jugador no identificado:** no existe una entidad correcta para valorar “EI del Cubillos” sin nombre.
7. **Posición habitual equipo/temporada:** no existe en `team_rosters`.
8. **Top 3/ranking personal:** existe destacado booleano, pero no ranking 1.º/2.º/3.º estructurado.
9. **Lectura breve todavía muestra ambos equipos simétricamente:** aunque backend permita solo uno.
10. **Jugador seleccionado en lectura breve requiere nota o apunte:** no existe todavía un gesto autónomo “me llamó la atención” sin nota/texto.
11. **DD no tiene feed de atención realmente procesado:** tiene datos y módulos, pero no una capa de “qué merece atención / por qué / qué hacer”.
12. **Ficha de equipo todavía es ligera.**
13. **No existe perfil de participación por usuario** que permita experiencias No Name / Completo / Libre / Consulta sin crear roles artificiales.
14. **Admin no es superusuario visual de todas las áreas** por rol; el router actual sigue permisos separados.
15. **UI productiva no está certificada en todos los breakpoints.**
16. **Backup técnico no es restaurable.**
17. **Producción 4.4.4.1 necesita confirmación real** si no se ha realizado después de este corte.

---

# 32. DECISIONES QUE NO SE DEBEN DESHACER EN 4.5

- Nombre visible: **No Name · Área Técnica**.
- No volver a “PostMatch” como nombre de producto.
- No recuperar rol Scout normal.
- No hacer que DD apruebe cada informe; incorporación directa.
- No crear seguimiento automático por sacar 8.
- No duplicar nota al ampliar seguimiento.
- No convertir una señal en interés DD automáticamente.
- No mostrar IDs técnicos en UI normal.
- No depender del color para explicar estados.
- No borrar histórico automáticamente al desplegar.
- No fusionar jugadores/equipos por similitud de nombre sin decisión humana.
- No inventar formación, XI, titularidad, nombre, dorsal, hora o resultado.
- No tratar “Sin evaluar” como 0.
- No usar un único observador como “consenso”.
- No mezclar propios y externos en semántica de mercado.

---

# 33. QUÉ DEBE LLEVARSE EL CHAT NUEVO

Para implementar 4.5, el chat nuevo necesita como mínimo:

1. `NoName_Area_Tecnica_4.4.4.1.zip` completo.
2. Este documento.
3. `ESPECIFICACION_COMPLETA_4.5.md`.
4. Si existe, una copia/backup antes de desplegar migraciones.
5. Logs reales si el arranque Cloud vuelve a fallar.

**Regla final:** la 4.4.4.1 es la base. La 4.5 es una evolución aditiva, centrada en quitar gates y trabajo manual, no un reinicio del proyecto.
