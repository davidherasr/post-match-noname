# ESPECIFICACIÓN COMPLETA · NO NAME · ÁREA TÉCNICA 4.5

**Base obligatoria:** `NoName_Area_Tecnica_4.4.4.1.zip`  
**Naturaleza de la release:** simplificación operativa + inteligencia deportiva “masticada” para DD  
**Objetivo:** que la aplicación siga generando mucho conocimiento aunque Administración haga poco trabajo previo y aunque los Informadores solo quieran aportar una parte mínima del partido.

---

## 0. PRINCIPIO CENTRAL DE 4.5

La aplicación debe asumir la complejidad interna para que el cuerpo técnico no tenga que asumirla.

### Entrada

Muy fácil, parcial y voluntaria.

### Procesamiento

Relaciones, contexto, histórico, tamaño de muestra, identidad, posición, procedencia, agregados y detección de señales.

### Salida para Dirección Deportiva

Rica y “masticada”: qué merece atención, por qué, con cuánta evidencia, quién lo vio, en qué contexto y cuál es la siguiente acción posible.

**Criterio de aceptación principal:** si el Administrador no entra en Administración durante dos semanas, el resto del cuerpo técnico debe poder seguir aportando valoraciones sobre los partidos oficiales normalmente.

---

# 1. QUÉ SE CONSERVA DE 4.4.4.1

No se rehace la aplicación desde cero. Se conservan:

- PostgreSQL/Supabase y Alembic.
- identidad de usuarios y roles acumulables.
- equipo propio por ID.
- gobierno de datos test/archivados.
- Jornada y Match Hub como concepto.
- informes y `PlayerEvaluation`.
- lecturas neutrales.
- incorporación directa de informes.
- Player Report 360.
- seguimiento formal enlazado a la nota del partido.
- peticiones DD.
- Modelo No Name.
- pesos del staff.
- decisiones por temporada.
- PDFs y Storage.
- histórico y tablas legacy.

No se hace reset, migración destructiva ni limpieza automática de datos históricos.

---

# 2. CAMBIO DE FILOSOFÍA OPERATIVA

## 2.1 Antes

Calendario → confirmar hora → preparar → completar datos → seleccionar Informadores → publicar → Informador puede trabajar.

## 2.2 4.5

**El partido oficial existe → cualquier persona autorizada puede aportar lo que realmente haya visto.**

La preparación Admin pasa a ser una mejora de contexto, no una condición de entrada.

Las asignaciones pasan a ser una petición/prioridad, no una llave de acceso.

Los datos incompletos son válidos cuando reflejan la realidad.

---

# 3. ROLES: SEGURIDAD VS PERFIL DE PARTICIPACIÓN

## 3.1 Roles de seguridad que se mantienen

- Administrador.
- Dirección Deportiva.
- Informador.
- `can_track_players` separado.

## 3.2 Admin en 4.5

El Administrador debe poder **ver y gestionar cualquier área** para resolver incidencias y datos, pero no debe falsificar autoría deportiva.

Regla:

- Admin puede corregir datos y abrir pantallas.
- Si Admin quiere emitir una opinión deportiva que cuente como opinión de staff, debe hacerlo bajo su propia capacidad Informador.
- Una corrección administrativa de una nota ajena se registra como corrección/auditoría, no como si la hubiera firmado el Admin originalmente.

## 3.3 Nuevo perfil operativo por usuario

Añadir un campo/configuración independiente de roles, por ejemplo `participation_profile`.

Perfiles propuestos:

### `own_only` · No Name

Para quien solo quiere valorar nuestro equipo.

- Inicio centrado en el partido de No Name.
- Puede aportar sobre No Name.
- El rival queda oculto/segundo nivel por defecto.
- No se le cargan neutrales como tarea.

### `full` · Completo

Para quien suele observar No Name y rivales.

- Puede aportar sobre ambos lados del partido propio.
- Puede realizar lecturas neutrales.
- Recibe peticiones DD cuando corresponda.

### `free` · Libre

Para quien quiere explorar por iniciativa propia.

- calendario completo de liga,
- aportación voluntaria en cualquier partido permitido,
- pocas “tareas” automáticas,
- mantiene peticiones DD.

### `viewer` · Consulta

Para quien principalmente consulta.

- Inicio limpio,
- partidos, jugadores e información relevante,
- sin presión de tareas.

No hardcodear nombres de miembros del staff. Administración asigna el perfil.

### Ejemplo organizativo conceptual

- miembros que solo valoran No Name → `own_only`.
- miembros que ven No Name + rival → `full`.
- personas con libertad para mirar cualquier partido → `free`.
- miembros que casi solo consultan → `viewer`.

---

# 4. CALENDARIO: EL FIN DE SEMANA ES SUFICIENTE

## 4.1 Eliminar hora exacta como requisito operativo

Si la jornada tiene una ventana sábado/domingo, eso basta para:

- mostrarla,
- abrir el partido,
- valorar,
- crear lectura,
- generar señales,
- responder peticiones.

La hora exacta se mantiene como dato opcional cuando se conozca.

## 4.2 Semántica

- `window_start/window_end`: ventana oficial/operativa de la jornada.
- `kickoff_at`: opcional.
- `schedule_status`: no debe bloquear un informe por ser provisional si el partido oficial existe.

## 4.3 Quitar tareas administrativas inútiles

Inicio Admin deja de crear como tarea prioritaria “Confirmar horario” salvo que exista una necesidad real específica.

No se debe exigir rellenar un horario ficticio para desbloquear nada.

## 4.4 Jornada actual

Nueva prioridad para elegir jornada:

1. jornada cuya ventana contiene hoy;
2. si ninguna, jornada de No Name temporalmente más cercana;
3. si no hay No Name, jornada oficial más cercana;
4. fallback última conocida.

No usar simplemente “primer match_date futuro”.

---

# 5. PARTIDO OFICIAL = INFORME POTENCIALMENTE DISPONIBLE

## 5.1 Eliminar “Publicar postpartido” como gate

El asistente Admin puede seguir existiendo para enriquecer:

- resultado,
- formaciones,
- XI,
- suplentes,
- campo,
- vídeo,
- asignaciones prioritarias.

Pero el partido de No Name debe ser valorable aunque Admin no lo haya preparado.

## 5.2 Estado de partido

La UI puede seguir distinguiendo “sin preparar / enriquecido / con datos completos”, pero ese estado no impide aportar.

## 5.3 Autocreación del contexto de informe

Cuando un Informador abre por primera vez un partido propio oficial:

- si no existe `Report`, se crea;
- si no existe `ReportAssignment`, puede crearse una asignación automática voluntaria (`required=False`, `assigned_by=self`) solo para mantener trazabilidad de estado, o el repositorio debe aceptar ausencia de assignment;
- no debe exigirse status `published` ni kickoff exacto.

Preferencia: reutilizar `ReportAssignment` para trazabilidad, pero **no tratarlo como autorización**.

---

# 6. ASIGNACIONES: DE PERMISO A PRIORIDAD

## 6.1 Nueva semántica

Asignar a alguien significa:

> “Me interesa especialmente que tú aportes aquí.”

No significa:

> “Solo tú puedes abrir el informe.”

## 6.2 Bandeja

Las asignaciones aparecen destacadas en Inicio como prioridad.

## 6.3 Rechazo

- Si era asignación explícita: puede rechazarse y desaparecer de tareas.
- Si el usuario simplemente abrió voluntariamente un partido: no necesita “rechazar” nada.

## 6.4 DD y peticiones

Las peticiones sobre jugadores siguen separadas de las asignaciones de informe. No recuperar ScoutMission.

---

# 7. APORTACIÓN PARCIAL: REQUISITO EXPLÍCITO DE 4.5

Este punto es obligatorio.

Un Informador debe poder elegir libremente qué valorar:

- **solo No Name**;
- **solo el rival**;
- **ambos equipos**;
- **solo uno o varios jugadores**;
- **solo sus tres destacados**;
- **solo una nota colectiva**;
- **solo una señal/apunte individual**;
- cualquier combinación anterior.

El resto puede quedar vacío.

## 7.1 UI

No mostrar dos equipos como dos obligaciones consecutivas.

Propuesta de lectura básica:

### ¿Qué quieres valorar hoy?

- `[ ] No Name`
- `[ ] Rival`
- `[ ] Jugadores/destacados`

La selección puede inferirse de la acción inicial del perfil, pero siempre editable.

Ejemplo `own_only`:

- abre directamente No Name;
- rival detrás de “Añadir rival” opcional.

## 7.2 Campos vacíos

- No generar warning “pendiente”.
- No mostrar `0/11` ni `0/30`.
- No convertir vacío en 0.
- No penalizar métricas por ausencia.

## 7.3 Validación de entrega

Debe existir **al menos una aportación real**:

- nota de equipo >0,
- señal/destacado,
- nota de jugador,
- comentario/apunte suficiente.

Un formulario completamente vacío no debe crear ruido.

---

# 8. INFORME BÁSICO 4.5

Objetivo: una persona que no quiera perder tiempo puede terminar sin navegar por un formulario largo.

## 8.1 Bloques

### No Name — opcional

- nota 1–10 / Sin evaluar;
- hasta 3 destacados propios opcionales;
- comentario opcional.

### Rival — opcional

- nota 1–10 / Sin evaluar;
- hasta 3 destacados rivales opcionales;
- comentario opcional.

### Conclusión general — opcional

Una frase si quiere.

### Entregar

Una sola confirmación breve y vuelta a Inicio.

## 8.2 Modo detallado

Se conserva como “Ampliar informe”.

Debe permitir plantilla completa, notas, comentarios y seguimiento, pero nunca ser el camino obligatorio.

---

# 9. DESTACADOS 1.º / 2.º / 3.º

Añadir ranking estructurado de destacados.

Por cada lado del partido, opcionalmente:

- 1.º destacado.
- 2.º destacado.
- 3.º destacado.

Puede coexistir con nota individual, pero no la exige.

## 9.1 Semántica

Un jugador puede ser 1.º destacado sin tener una nota numérica si el observador no quiere cuantificar.

## 9.2 Datos

Añadir `highlight_rank` nullable (1–3) a:

- `player_evaluations`,
- `match_opinion_players`.

La restricción debe garantizar rango válido y evitar dos jugadores con el mismo puesto dentro del mismo autor/partido/equipo cuando proceda.

## 9.3 DD

Mostrar:

- nº de veces top 3,
- nº de veces top 1,
- partidos,
- autores,
- nota media solo si hay notas.

No mezclar “ranking de destacados” con “interés DD”.

---

# 10. SEÑAL LIGERA SIN NOTA

En 4.4.4.1 seleccionar jugador en lectura breve obliga a nota o texto. En 4.5 debe existir un gesto explícito:

**👁 Me llamó la atención**

Sin nota obligatoria.

Esto crea evidencia ligera, no seguimiento formal.

Puede acompañarse de:

- posición,
- dorsal,
- apunte,
- ranking top 3.

---

# 11. JUGADOR NO IDENTIFICADO

Requisito crítico de 4.5.

## 11.1 Caso

> “Me gustó el extremo izquierdo del River. No sé cómo se llama.”

Debe poder guardarse sin inventar un `Player`.

## 11.2 Nueva entidad recomendada

Crear una tabla aditiva, por ejemplo `unidentified_player_signals`:

- `id`.
- `match_id`.
- `team_id`.
- `user_id`.
- `position` nullable.
- `shirt_number` nullable.
- `label` opcional, generado de forma humana (“EI · dorsal 11”).
- `rating` nullable.
- `highlight_rank` nullable.
- `note` nullable.
- `source` (`own_report`, `neutral`, etc.).
- `resolved_player_id` nullable.
- `resolved_by` nullable.
- `resolved_at` nullable.
- created/updated.

## 11.3 Reconciliación

Cuando se descubre la identidad:

- seleccionar jugador existente o crear/resolver identidad con flujo habitual;
- asignar `resolved_player_id`;
- la evidencia pasa a agregados del jugador;
- **no crear otra nota duplicada**;
- conservar el registro original y la trazabilidad de que inicialmente era anónimo.

## 11.4 No crear jugadores basura

Nunca crear `Player(full_name="Extremo izquierdo Cubillos")` para resolver este caso.

---

# 12. CAMPORAMA CLICABLE COMO ENTRADA RÁPIDA

Si se conoce una estructura, por ejemplo 4-3-3, aunque no se conozcan nombres:

- renderizar posiciones;
- cada posición es clicable;
- al pulsar EI, abrir mini ficha:
  - nombre si se sabe,
  - dorsal opcional,
  - nota opcional,
  - 👁 señal,
  - top 1/2/3 opcional,
  - apunte opcional.

Si posteriormente se identifica al jugador, reconciliar.

El campograma no debe exigir un XI nominal completo.

---

# 13. MEMORIA DE POSICIÓN POR EQUIPO/TEMPORADA

Añadir a `team_rosters` un campo como:

- `usual_position` nullable.

Opcionalmente `position_source` si se considera útil.

Resolución de posición:

1. `Participation.position` de ese partido.
2. `TeamRoster.usual_position` de esa temporada/equipo.
3. `Player.primary_position`.
4. desconocida.

Si el jugador juega una posición distinta un día, la posición del partido no debe sobrescribir automáticamente la habitual.

La UI puede preguntar “¿Actualizar posición habitual?” solo cuando tenga sentido.

---

# 14. MEMORIA DE FORMACIONES

No añadir una “formación fija” al club como verdad automática.

Al abrir un nuevo partido:

> Última estructura observada: 4-3-3

Botón:

**Usar como punto de partida**

Eso copia slots al contexto del partido actual, pero mantiene la formación como “pendiente de confirmar” hasta que alguien la valide.

Se puede calcular desde el último partido oficial del equipo; no requiere necesariamente una nueva tabla.

---

# 15. INICIO POR PERFIL

## 15.1 Informador `own_only`

Arriba:

**Esta semana · C.D. Noname – Rival**  
Ventana de fin de semana  
`Hacer mi lectura`

Si ya entregó:

`Tu lectura está entregada ✓`

Debajo:

- anteriores de No Name,
- nº de aportaciones del staff,
- búsqueda de jugador,
- peticiones DD relevantes.

No cargar el resto de la liga de entrada.

## 15.2 `full`

Además:

- partido de No Name,
- rival,
- neutrales relevantes,
- peticiones DD.

## 15.3 `free`

- partido de No Name visible,
- calendario completo accesible,
- ninguna obligación de completar tareas que no le hayan solicitado.

## 15.4 `viewer`

- próximo/último partido,
- resultados,
- búsqueda,
- información compartida;
- sin bloques de tareas si no tiene ninguna responsabilidad.

## 15.5 Admin

No debe recibir una lista de “pijadas” semanales por defecto.

Mostrar solo:

- incidencias reales,
- errores de datos,
- duplicados/problemas,
- peticiones administrativas explícitas.

---

# 16. JORNADA 4.5

## 16.1 Cabecera

- temporada activa,
- jornada actual por ventana,
- anterior / siguiente,
- selector rápido,
- buscador de equipo.

## 16.2 Orden

Primero siempre el partido de No Name si existe.

Tarjeta:

- equipos,
- ventana/fecha/hora si se conoce,
- resultado si existe,
- nº de aportaciones,
- “Tu lectura: pendiente/entregada” si aplica,
- CTA contextual.

## 16.3 Resto de jornada

Lista compacta:

- partido,
- nº de aportaciones,
- señal DD si hay petición relevante,
- botón “Aportar” para perfiles permitidos.

## 16.4 Mantenimiento

Importación/horarios siguen disponibles para Admin, pero fuera del flujo principal.

---

# 17. DIRECCIÓN DEPORTIVA: NO SIMPLIFICAR, “MASCAR”

Este es el segundo eje central de 4.5.

DD debe conservar la profundidad, pero la portada debe responder:

- ¿qué ha pasado?
- ¿qué merece atención?
- ¿por qué?
- ¿con qué muestra?
- ¿qué puedo hacer ahora?

---

# 18. NUEVA PORTADA DD: “LO QUE MERECE TU ATENCIÓN”

No guardar necesariamente estas tarjetas en DB. Se pueden calcular desde evidencia existente y reglas transparentes.

Ejemplos:

### Nueva señal fuerte

**EI · Cubillos**  
David · Cubillos–Vallesina · 8/10  
Muestra: 1 partido · 1 autor  
“Primera señal fuerte; evidencia inicial.”

Acciones:

- `Pedir a David que amplíe`
- `Abrir partido`
- `Añadir a interés`

### Repetición

**Pedro Fernández · LD**  
3 partidos · 2 autores · media 8,1  
2 veces top 3.

Acciones:

- `Abrir evidencia`
- `Añadir a interés`
- `Pedir otra opinión`

### Discrepancia

**Juan García**  
David 8 · Roma 5 · mismo partido.

Acciones:

- `Ver comentarios`
- `Preguntar qué vieron diferente`

### Identidad pendiente

**EI · dorsal 11 · River**  
Señalado por 2 personas.

Acciones:

- `Identificar jugador`
- `Ver partidos`

### Respuesta DD

**David respondió sobre Pedro Fernández**  
Abrir respuesta y evidencia original.

---

# 19. MOTOR DE SEÑALES DD — REGLAS TRANSPARENTES

No es IA predictiva. Son reglas explicables.

Propuestas:

- primera nota ≥8 → “señal fuerte inicial”;
- ≥8 repetido en ≥2 partidos → “se repite”;
- ≥2 autores → “coincidencia de staff”;
- top 3 repetido → “destacado recurrente”;
- dispersión alta → “criterio dividido”;
- jugador de interés vuelve a aparecer → “nueva evidencia sobre interés DD”;
- petición respondida → “respuesta nueva”;
- señal anónima repetida → “identidad pendiente relevante”;
- candidato compatible con necesidad abierta → “evidencia en posición necesaria”.

Cada tarjeta debe mostrar **la regla que la hizo aparecer**.

Nunca afirmar “buen fichaje”, “debe ficharse”, etc.

---

# 20. TRES NIVELES DE INTERÉS

Semántica uniforme:

### 👁 Señalado

Alguien del staff lo destacó. Puede ser una sola evidencia.

### ⭐ Interés DD

DD decidió expresamente tenerlo controlado.

Puede mapearse a `PlayerSeasonDecision.status = Interesante`.

### 🎯 Prioritario

DD ha decidido que merece prioridad real.

Mapear a `Prioritario`/necesidad correspondiente.

Una nota alta no promueve automáticamente de 👁 a ⭐.

---

# 21. COBERTURA DE CONOCIMIENTO

Mostrar una tarjeta descriptiva, no una cifra opaca.

Ejemplo:

**Conocimiento actual**

- 3 partidos.
- 2 informadores.
- 4 señales.
- 1 seguimiento ampliado.
- última observación hace 14 días.

Etiqueta:

- Inicial.
- Limitada.
- Razonable.
- Amplia.

La etiqueta debe derivar de reglas documentadas y mostrar siempre sus componentes.

No ocultar que una media 8,5 con 1 partido/1 autor tiene muestra inicial.

---

# 22. DD: PREGUNTAR SOBRE UNA EVIDENCIA CONCRETA

Desde cualquier señal:

> “David le dio 8 al EI del Cubillos.”

DD puede pulsar:

**¿Por qué te llamó la atención?**

Se crea/abre una `PlayerObservationRequest` contextualizada, vinculando el jugador y, cuando sea posible, el partido. La respuesta debe reutilizar la evidencia original.

No crear:

- otra nota,
- otra observación formal,
- otra misión Scout.

---

# 23. FICHA DE EQUIPO / RIVAL 4.5

Convertirla en lectura preparada.

## Resumen

- partidos observados,
- autores,
- última observación,
- valoración reciente con muestra.

## Estructuras observadas

- formaciones y frecuencia,
- fecha de última vez,
- campograma de la última/seleccionada.

## Campograma de conocimiento

Sobre posiciones:

- nombre si está identificado,
- dorsal si existe,
- 👁 señales,
- media si hay nota,
- identidad pendiente si no se conoce.

## Jugadores que merecen atención

- top 3 repetidos,
- medias con muestra,
- DD interest.

## Discrepancias

- miembros del staff que valoraron diferente.

## Partidos

Acceso a fuentes originales.

---

# 24. DD SOBRE LA PLANTILLA DE NO NAME

No convertir jugadores propios en mercado.

DD debe ver:

- rendimiento reciente,
- tendencia,
- nº de apariciones evaluadas,
- nº de autores,
- rol del Modelo No Name,
- necesidad vinculada,
- evolución.

Ejemplo:

**Rol lateral derecho**  
Necesidad: Media  
2 jugadores propios asociados  
Rendimiento reciente: 6,4  
3 externos observados compatibles.

Esto conecta planificación con evidencia sin sugerir automáticamente un fichaje.

---

# 25. MODELO NO NAME EN 4.5

Mantener:

- roles,
- criterios,
- pesos,
- necesidades,
- encaje.

Mejorar conexión:

- desde necesidad → jugadores propios;
- desde necesidad → externos con evidencia;
- mostrar criterios pendientes de evaluar;
- no inventar fit si no hay puntuaciones de criterios.

Configuración de roles/criterios queda en segundo nivel, no en portada diaria DD.

---

# 26. PLAYER REPORT 360 EN 4.5

Mantener toda la profundidad.

Añadir/ajustar:

- top 3 / destacados,
- cobertura de conocimiento,
- señales anónimas ya resueltas con trazabilidad,
- próxima acción real de DD,
- petición abierta,
- evidencia agrupada por evento lógico,
- muestra visible junto a cualquier media.

No mezclar own y rival.

---

# 27. PETICIONES DD EN 4.5

Mantener modelo 0015.

Mejoras:

- crear desde evidencia concreta con jugador/partido preseleccionados;
- respuestas rápidas;
- no obligar comentario para “No pude verlo”;
- DD ve línea temporal petición → destinatarios → respuesta → decisión;
- evitar solicitudes equivalentes duplicadas;
- posible coincidencia no significa participación confirmada.

---

# 28. SEGUIMIENTO FORMAL EN 4.5

Mantener reglas actuales:

- externo;
- permiso independiente;
- opt-in explícito;
- no automático por nota;
- una nota por jugador/partido/autor;
- observación formal amplía, no duplica;
- DD puede corregir duplicados/errores de forma auditada.

En la interfaz básica no debe aparecer seguimiento salvo que el usuario decida ampliar.

---

# 29. ADMINISTRACIÓN 4.5

Objetivo: mantenimiento, no logística semanal.

## Portada Admin

Mostrar solo:

- problemas de integridad,
- datos sin resolver,
- identidades anónimas pendientes de reconciliar,
- duplicados,
- usuarios/permisos,
- importaciones y correcciones.

No convertir “hora pendiente” en incidencia por defecto.

## Mantener

- usuarios,
- equipo propio,
- test/archivo,
- borrado definitivo,
- backups/exportación,
- auditoría,
- catálogos.

---

# 30. CAMBIOS DE MODELO PROPUESTOS — MIGRACIÓN 0016

La migración debe ser **aditiva y no destructiva**.

## 30.1 `users`

Añadir:

- `participation_profile` nullable/default seguro.

Backfill recomendado: usuarios Informador existentes → `full` salvo decisión explícita posterior. Admin puede cambiarlo.

## 30.2 `team_rosters`

Añadir:

- `usual_position` nullable.

No rellenar automáticamente desde un único partido histórico salvo una regla de backfill muy conservadora. Preferible dejar null y aprender desde uso futuro.

## 30.3 `player_evaluations`

Añadir:

- `highlight_rank` nullable 1–3.
- opcionalmente un flag explícito de señal si no se reutiliza `standout` para evitar semánticas ambiguas.

Preferencia: mantener `standout` histórico y añadir `highlight_rank`; `standout` puede derivarse si rank existe, pero no reescribir histórico masivamente.

## 30.4 `match_opinion_players`

Añadir:

- `highlight_rank` nullable 1–3.

## 30.5 Nueva tabla

`unidentified_player_signals` según apartado 11.

## 30.6 No necesaria

No crear una tabla `dd_attention_feed`: las alertas pueden calcularse. Solo persistir una alerta si en el futuro se necesita marcarla leída/archivada; no añadirlo inicialmente sin necesidad.

---

# 31. REPOSITORIOS / LÓGICA A MODIFICAR

## `core/schedule.py`

Separar:

- “partido operativo”
- “hora exacta confirmada”.

No usar `is_schedule_confirmed()` como gate genérico.

## `repositories/reports.py`

- `get_or_create_report()` sin dependencia de kickoff exacto.
- autorización por rol/perfil, no assignment.
- autoclaim voluntario.
- validación parcial explícita.

## `repositories/workspaces.py`

- `default_round()` por ventana.
- tareas por perfil.
- retirar tareas Admin de horario salvo excepción.
- contar aportaciones, no solo asignaciones.

## `repositories/sporting_reading.py`

- integrar top 3.
- integrar señales anónimas resueltas.
- producir campos para motor de atención DD.
- conservar muestra/autores/dispersión.

## `repositories/player_report.py`

- top 3,
- cobertura de conocimiento,
- eventos resueltos.

## `repositories/observation_requests.py`

- creación contextual desde evidencia.

## Nuevo repositorio

`repositories/unidentified_players.py` o nombre equivalente para:

- crear señal temporal,
- listar pendientes,
- resolver identidad,
- incluir en agregados una vez resuelta.

---

# 32. PANTALLAS A MODIFICAR

## `views/home.py`

Rediseño por perfil.

## `views/jornada.py`

Jornada por ventana, No Name primero, aporte libre, campograma/slots anónimos.

## `views/reports.py`

Lectura parcial explícita, top 3, señal sin nota, rival opcional.

## `views/postmatch.py`

Deja de ser gate. Se convierte en enriquecimiento Admin.

## `views/squad.py`

Portada DD “Lo que merece atención”. Mantener profundidad como subáreas.

## `views/team_hub.py`

Ficha de equipo masticada.

## `views/player_hub.py` / `ui/player_report.py`

Cobertura, destacados, next action, peticiones.

## `views/admin.py` / `admin_hub.py`

Perfil operativo de usuario y limpieza de trabajo cotidiano.

---

# 33. COMPORTAMIENTO EXACTO DEL CASO “SOLO QUIERO VALORAR NO NAME”

Partido: **C.D. Noname – La Bañeza**.

Usuario `own_only` entra.

Ve:

### No Name

Nota opcional 1–10.  
Destacados propios opcionales.  
Comentario opcional.

Botón:

**Entregar mi lectura**

Debajo, discretamente:

`+ Añadir algo del rival`

Si no lo pulsa:

- `rival_team_rating = NULL`;
- cero evaluaciones rivales es válido;
- no aparece warning “te falta La Bañeza”;
- no afecta medias del rival;
- el informe cuenta como aportación de No Name.

Caso inverso: una persona puede valorar solo La Bañeza si es su aportación real.

También puede valorar solo un jugador o top 3 si eso es lo único que observó.

---

# 34. CASO “NO SÉ EL NOMBRE”

Partido: River – No Name.

El usuario pulsa EI del campograma del River.

Guarda:

- posición EI,
- dorsal 11 si lo vio,
- 8/10 opcional,
- top 1 opcional,
- “me llamó la atención”,
- apunte opcional.

DD recibe:

> EI · River · dorsal 11 · identidad pendiente  
> David · partido X · 8/10 · top 1

Posteriormente Admin/DD identifica al jugador como Pedro Fernández.

La misma evidencia pasa a Pedro Fernández, conservando:

- origen anónimo,
- autor,
- partido,
- posición,
- dorsal,
- nota,
- rank,
- fecha de resolución.

No duplicar.

---

# 35. CASO DD “¿POR QUÉ LE DISTE UN 8?”

1. David valora EI Cubillos 8.
2. Feed DD muestra primera señal fuerte, muestra 1/1.
3. Aarón pulsa “Pedir ampliación”.
4. Petición se crea para David, ligada al jugador/partido/evidencia.
5. David ve pregunta en Inicio.
6. Responde texto breve.
7. DD ve respuesta enlazada.
8. La nota sigue siendo una sola.
9. DD puede añadir a ⭐ interés o cerrar.

---

# 36. CASO DE SEÑAL REPETIDA

Jugador identificado aparece:

- partido A: 8, top 2, David;
- partido B: 8, Roma;
- partido C: señalado sin nota, Viti.

DD debe ver:

- 3 partidos,
- 3 autores,
- 2 notas,
- media de notas válida,
- top 3 una vez,
- una señal sin nota,
- última fecha,
- nivel de conocimiento razonable según regla,
- si existe o no interés DD.

No promediar la señal sin nota como cero.

---

# 37. CASOS DE PRUEBA OBLIGATORIOS 4.5

1. Informador `own_only`, partido propio sin horario exacto: puede valorar solo No Name y entregar.
2. Rival completamente vacío: no warning, no cero.
3. Solo rival: válido.
4. Solo un jugador propio: válido.
5. Solo un jugador rival: válido.
6. Solo top 3 sin nota: válido si existe señal real.
7. Informe completamente vacío: no entregar.
8. Informador no asignado: puede aportar en partido permitido por perfil.
9. Asignación explícita: aparece prioritaria pero no cambia autorización base.
10. Rechazo: solo de tarea asignada, no de partido voluntario.
11. Partido con ventana sábado-domingo y sin kickoff: operativo.
12. Jornada actual seleccionada por ventana.
13. Jugador desconocido EI sin dorsal.
14. Jugador desconocido con dorsal y nota.
15. Resolver identidad sin duplicar evidencia.
16. Posición habitual se recuerda en siguiente partido.
17. Posición diferente del partido no sobrescribe habitual automáticamente.
18. Última formación sugerida, no confirmada.
19. Nota ≥8 no crea interés DD.
20. Repetición ≥8 genera tarjeta de atención, no decisión automática.
21. Una sola observación muestra muestra inicial, no consenso.
22. Discrepancia de dos autores genera atención.
23. DD pide “por qué” desde señal y respuesta enlaza a evidencia.
24. Jugador propio nunca aparece como objetivo de mercado.
25. Test/archivados excluidos de feeds y métricas.
26. Transferencia entre equipos/temporadas mantiene identidad y posición contextual.
27. Usuario multirol.
28. Admin ve/corrige todo, pero no falsifica autoría deportiva.
29. Seguimiento formal sigue requiriendo permiso.
30. PDFs y Player 360 no duplican nota postpartido+seguimiento.
31. PostgreSQL migration 0015→0016 en copia aislada.
32. Instalación desde cero hasta 0016.
33. Reejecución de migraciones en head.
34. Streamlit Cloud real.
35. móvil 375 px y escritorio.

---

# 38. ORDEN DE IMPLEMENTACIÓN RECOMENDADO

## Fase A · Esquema y contratos

- migración 0016;
- perfiles de participación;
- posición habitual;
- highlight rank;
- señales no identificadas;
- tests de integridad.

## Fase B · Desbloquear flujo

- quitar kickoff como gate;
- quitar assignment como gate;
- autoclaim voluntario;
- tareas Admin reducidas;
- jornada por ventana.

## Fase C · Informador

- lectura parcial explícita;
- top 3;
- señal sin nota;
- campograma clicable;
- anónimos.

## Fase D · DD masticada

- feed de atención;
- cobertura;
- preguntas contextuales;
- equipo/rival enriquecido;
- conexión con Modelo No Name.

## Fase E · Pulido y validación

- Player 360;
- PDFs;
- UX móvil;
- pruebas Cloud/PostgreSQL;
- documentación.

---

# 39. COSAS QUE NO DEBEN ENTRAR EN 4.5

Para evitar volver a inflar la aplicación:

- chat interno,
- push notifications externas,
- scraping automático no fiable,
- xG inventado,
- valoración de mercado inventada,
- IA que “recomienda fichar” sin datos,
- organigrama Scout,
- misiones obligatorias complejas,
- ranking automático de “mejores fichajes” con muestra mínima,
- obligación de completar XI,
- obligación de completar ambos equipos,
- obligación de horarios exactos,
- dashboards decorativos sin acción.

---

# 40. DEFINITION OF DONE DE 4.5

La 4.5 está terminada cuando:

- un partido oficial puede recibir aportaciones sin preparación Admin;
- la ventana de jornada es suficiente;
- Informador puede aportar solo una parte real del partido;
- campos vacíos no se convierten en deuda ni cero;
- usuarios `own_only` tienen una experiencia casi trivial;
- existe observación correcta de jugador desconocido;
- posiciones habituales se recuerdan por equipo/temporada;
- destacados top 3 tienen estructura y agregados;
- DD ve un feed explicado de señales y siguiente acción;
- DD puede pedir ampliación desde evidencia concreta;
- el sistema distingue 👁 señal, ⭐ interés y 🎯 prioridad;
- ficha de equipo muestra información procesada y campograma útil;
- No Name propio permanece separado del mercado;
- histórico 4.4.4.1 se conserva;
- migración es aditiva;
- tests, compileall, consistencia y migraciones pasan;
- se prueba Streamlit Cloud con datos representativos;
- no se exige a Administración hacer trabajo semanal de aprovisionamiento para que los demás participen.

---

# 41. INSTRUCCIÓN FINAL PARA EL CHAT QUE IMPLEMENTE

Implementar 4.5 **sobre el ZIP 4.4.4.1 completo**. Antes de tocar código:

1. leer `CONTEXTO_MAESTRO_4.4.4.1.md`;
2. inventariar archivos y head Alembic;
3. ejecutar baseline de tests;
4. comprobar que la base es exactamente 4.4.4.1;
5. crear migración 0016 aditiva si el diseño final requiere los campos anteriores;
6. implementar por fases sin borrar histórico;
7. ampliar pruebas antes de modificar UI destructivamente;
8. entregar ZIP completo de 4.5 con `UPGRADE_4_5.md`, `VALIDACION_4_5.md`, `CHANGELOG.md` y contexto actualizado;
9. no afirmar validación de producción hasta arrancar realmente Cloud contra una base autorizada.

La prioridad no es añadir más funciones. La prioridad es que **aportar sea trivial, el sistema recuerde y relacione, y DD reciba conocimiento ya preparado para decidir**.
