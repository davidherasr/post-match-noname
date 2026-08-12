# No Name PostMatch 3.4.0

## Qué cierra 3.4

- Modo rápido real de valoración mediante `st.fragment`: mover nota/comentario no recarga la aplicación completa ni consulta Supabase.
- Estado **cambios sin guardar** real por equipo, con bloqueo de navegación hasta guardar o deshacer.
- Desambiguación de homónimos rivales: equipo+temporada, alias, fecha de nacimiento si existe y confirmación humana cuando hay varias coincidencias.
- XI de la liga con filtros de confianza y estado DD.
- Tendencias por ventanas no solapadas y muestra mínima de cuatro observaciones.
- Confianza 0–100 explicada por muestra, informadores, consenso y recencia.
- Bandeja DD con seguimientos vencidos/prioritarios sin observación.
- Dossier rival con último XI conocido, jugadores de interés y futbolistas más observados.
- Backup únicamente bajo demanda.
- Archivo de informes con filtro por jornada.
- Instrumentación SQL real: tiempo total, DB, render y número de queries.
- Prueba de aceptación contra la base configurada con `SAVEPOINT` y rollback desde Administración.
- Repositorios separados (`users`, `players`, `matches`, `reports`) y PDF dividido en `payload`, `summary_pdf`, `full_pdf`.


Aplicación interna de **No Name** para preparar el postpartido, valorar en segundos a jugadores propios y rivales y convertir cada jornada en una base de conocimiento de **nuestra liga**.

La versión **3.4.0** cierra la auditoría de producción de la 3.3 y mantiene cuatro objetivos: **postpartido rápido, informes de un minuto, Dirección Deportiva de liga y scouting de segundo nivel**. PostgreSQL/Supabase continúa siendo la fuente de verdad, pero la interfaz trabaja primero en memoria y sincroniza solo cuando tiene sentido.

## Filosofía de producto

- Si la aplicación ya conoce un dato, no se lo vuelve a pedir al usuario.
- Si diez cambios pueden guardarse juntos, no se hacen diez viajes a Supabase.
- La administración prepara un partido como piensa un entrenador, no como piensa una base de datos.
- El informador solo puntúa y, si quiere, comenta.
- Dirección Deportiva no intenta ser una plataforma internacional: explota a fondo **los jugadores, equipos e informes de nuestra propia competición**.

## Administración · Nuevo postpartido

El flujo principal se prepara casi íntegramente en `st.session_state`:

1. Temporada, competición, rival, jornada, fecha, resultado y sistemas.
2. La formación seleccionada genera automáticamente las 11 posiciones.
3. Para No Name se propone el XI a partir de la plantilla y del último partido.
4. El administrador cambia únicamente los nombres necesarios.
5. Los cambios se escriben como `minuto · sale · entra`; la aplicación calcula los minutos de cada jugador.
6. Para el rival puede reutilizarse la última alineación, pegarse una lista o escribirse directamente sobre los 11 slots.
7. Los jugadores rivales nuevos se resuelven/crean al publicar, sin exigir una plantilla previa.
8. Solo `Guardar borrador en nube` o `Publicar postpartido` escriben el flujo completo en PostgreSQL.

Se puede crear competición o rival dentro del propio proceso. La Base de datos queda como zona de mantenimiento, no como requisito para operar cada semana.

## Formaciones automáticas

Incluye estructuras predefinidas para:

- 4-3-3
- 4-2-3-1
- 4-4-2
- 4-1-4-1
- 4-3-1-2
- 4-4-1-1
- 3-4-3
- 3-4-2-1
- 3-5-2
- 3-1-4-2
- 5-4-1
- 5-3-2

Ejemplo **4-4-2**: `POR · LD · DFC · DFC · LI · ED · MC · MC · EI · DC · DC`. El administrador no vuelve a introducir posición, titularidad ni minuto inicial de esos once.

## Informador · informe de un minuto

- Carga conjunta del partido, participantes y evaluaciones existentes.
- No se escribe en Supabase mientras se mueven sliders o se escriben comentarios.
- Un formulario para No Name y otro para el rival.
- Datos deportivos bloqueados: dorsal, posición, minutos y titular/suplente ya vienen del postpartido.
- Nota 0–10, comentario opcional, Destacado e Incluir en PDF.
- `0` significa **sin valorar**.
- Guardado masivo por equipo.
- Entrega independiente del guardado de cada jugador.
- PDF **Resumen** automático; PDF **Completo** bajo demanda.

## Dirección Deportiva · inteligencia de nuestra liga

La navegación está orientada a decisiones:

### Panorama

- jugadores rivales observados;
- jugadores vistos dos o más veces;
- seguimientos activos;
- perfiles prioritarios;
- equipos observados;
- informes pendientes de revisión;
- bandeja de jugadores que necesitan una decisión;
- destacados recientes;
- tendencias de evolución;
- radiografía de equipos de la liga.

### Jugadores

Ranking de futbolistas observados con filtros por posición, equipo, edad, muestra, nota, estado y destacados. Cada jugador tiene una ficha **360** con:

- media y tamaño de muestra;
- número de informadores;
- última nota;
- dispersión;
- nivel de confianza;
- evolución temporal;
- todos los comentarios aprobados;
- estado de Dirección Deportiva;
- prioridad;
- conclusión acumulada;
- seguimiento;
- inclusión en listas.

### Por posiciones

Rankings específicos de porteros, laterales, centrales, mediocentros, extremos, delanteros, etc. Siempre se muestra el tamaño de muestra junto a la nota.

### Equipos

Ficha de cada rival de la competición: partidos observados, jugadores vistos, destacados, media, última observación, última alineación conocida y jugadores que más interés han generado.

### Seguimiento

Agenda práctica dividida en vencidos, esta semana y próximos. Incluye responsable, prioridad, próxima revisión, partido objetivo, nota e historial cargado solo cuando se solicita.

### Comparador

Comparación de 2–4 jugadores usando únicamente información real disponible: media, observaciones, informadores, destacados, dispersión, confianza y estado de seguimiento/decisión.

### XI de la liga

Selecciona una formación y un mínimo de observaciones. La aplicación construye el mejor XI observado por posición. Puede guardarse como una lista editable de Dirección Deportiva.

### Consenso

Agrupa valoraciones de varios informadores para el mismo jugador/partido, muestra media, dispersión y nivel de acuerdo y permite guardar una conclusión consolidada.

### Informes

Bandeja de revisión cargada en bloque, evitando consultas N+1 por informe. Permite aprobar o devolver informes.

### Listas

Listas cortas, selecciones por posición, jugadores a revisar en segunda vuelta, XI objetivo y cualquier lista personalizada de la liga.

## Jugadores ojeados · scouting de segundo nivel

El postpartido sigue siendo rápido. Solo los perfiles que Dirección Deportiva decide profundizar pasan a una ficha scout avanzada:

1. **Observado** por los informes normales.
2. **Candidato** abierto por DD.
3. **Ficha solicitada** a un informador/scout.
4. **En revisión**, con análisis más completo y atributos opcionales por posición.
5. **Ojeado**, cuando DD fija posición/rol en nuestro modelo, encaje, nivel, proyección y decisión final.

Esto permite responder no solo “¿nos gustó?”, sino también **“¿dónde jugaría en No Name y qué rol le pediríamos?”** sin hacer más pesado el informe semanal.

## Rendimiento 3.4

- Borrador de postpartido en memoria; escritura solo al guardar/publicar.
- Catálogos del flujo de postpartido cacheados en sesión.
- Plantilla propia y última alineación cacheadas durante el flujo.
- Última alineación rival cargada una vez y reutilizada.
- Borradores remotos cargados de forma lazy/cached.
- Alineación rival guardada con precarga de jugadores y sincronización masiva de plantilla.
- Evaluaciones guardadas por equipo y no por jugador.
- Workspace del informe cargado como un payload conjunto.
- Rankings agregados en SQL (`AVG`, `COUNT`, muestra, informadores, destacados) en vez de agrupar miles de filas en Python.
- Bandeja de revisión cargada en bloque.
- Historiales y seguimiento detallado solo bajo demanda.
- Sin `st.tabs` en las pantallas principales.
- PDF Completo únicamente bajo demanda.
- Revalidación de sesión con TTL y bootstrap de aplicación memorizado.
- Base de datos relegada a mantenimiento con búsqueda global y edición masiva de plantilla.

## PDF

### Resumen

Documento diario de 1–2 páginas: partido, resultado, No Name, rival, notas y observaciones relevantes.

### Completo

Dossier detallado con alineaciones, contexto, fichas seleccionadas, trazabilidad y versión documental.

## Accesibilidad y simpleza

- controles táctiles amplios;
- foco visible por teclado;
- contraste reforzado;
- etiquetas claras;
- responsive móvil;
- respeto a `prefers-reduced-motion`;
- una acción primaria clara por bloque;
- lenguaje deportivo en lugar de lenguaje de base de datos;
- información conocida bloqueada para evitar trabajo redundante.

## Base de datos y actualización

3.4.0 mantiene como revisión actual **`0004_scout_workflow_3_3`**; no necesita una migración nueva porque las mejoras 3.4 son de interfaz, consultas, diagnóstico y arquitectura. La 0004 sigue siendo no destructiva y añade soporte para: Ambas son no destructivas. La nueva migración añade soporte para:

- expedientes scout avanzados;
- revisiones scout asignadas a informadores;
- ubicación del jugador dentro del modelo de No Name;
- índices compuestos de rendimiento para los flujos más utilizados.

Mantiene la misma `DATABASE_URL` y el mismo proyecto Supabase. No elimina jugadores, partidos, usuarios, informes ni evaluaciones existentes.

La release **no contiene datos deportivos, bases SQLite, jugadores, equipos, partidos ni informes de demostración**.

## Despliegue

`Main file path`:

```text
app.py
```

Los Secrets actuales se mantienen:

```toml
DATABASE_URL = "..."
DEMO_MODE = false
RUN_MIGRATIONS = true
REQUIRE_REPORT_APPROVAL = true
```

Antes de una actualización con cambio de esquema se recomienda descargar un backup técnico. Consulta `UPGRADE_3_3.md`.

## Validación

La release se valida con compilación completa, suite automatizada y pruebas de migración tanto en instalación nueva como desde la revisión 0003. Consulta `VALIDACION.md`.
