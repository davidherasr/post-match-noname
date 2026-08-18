# No Name PostMatch 3.7.0 · Calendario operativo + Scouting continuo

Aplicación interna de **No Name** para postpartido, inteligencia de nuestra liga, planificación de observaciones y scouting continuo sobre PostgreSQL/Supabase.

La 3.5 añade tres capas conectadas sin hacer más pesado el informe semanal:

1. **Calendario completo de toda la liga**: No Name y partidos entre rivales, incluso cuando solo se conoce la fecha federativa orientativa de la jornada y todavía no existe una hora definitiva.
2. **Perfil Scout completo**: agenda, misiones de DD, partidos neutrales, observaciones específicas, scouting espontáneo e informes de equipo/rival.
3. **Modelo No Name**: roles propios, criterios ponderados, necesidades de plantilla, plantilla sombra, decisiones por temporada y planificación automática de nuevos visionados.


## Novedad 3.6 · Player Report 360

La 3.6 mantiene íntegro el calendario, Scout y Modelo No Name de la 3.5 y añade una capa profesional de presentación para jugadores, inspirada en informes de scouting visuales pero limitada estrictamente a los datos que el club realmente ha recogido.

- cabecera con rendimiento, encaje y confianza;
- resumen ejecutivo, fortalezas, riesgos y recomendación;
- radar construido solo con criterios reales del Modelo No Name;
- separación entre rendimiento postpartido y perfil Scout;
- evolución conjunta de postpartidos y scouting específico;
- posiciones observadas;
- comparación con nuestra plantilla y perfiles conocidos de la liga;
- decisión DD por temporada con nivel actual, proyección y criterios;
- Ficha Scout Ejecutiva y Dossier Player Report 360 bajo demanda.

**No se inventan** valor de mercado, altura, estadísticas, nacionalidad, comparables externos ni atributos no evaluados.

## Flujo de producto

```text
CALENDARIO COMPLETO DE LA LIGA
              ↓
   DIRECCIÓN DEPORTIVA PLANIFICA
              ↓
 ┌───────────────────────────────┐
 │ Postpartido de No Name        │
 │ Observación individual        │
 │ Varios jugadores              │
 │ Análisis de equipo/rival      │
 │ Scouting espontáneo           │
 └───────────────────────────────┘
              ↓
      INFORMADOR / SCOUT
              ↓
       EVIDENCIA ACUMULADA
              ↓
      MODELO NO NAME / DD
              ↓
 SEGUIMIENTO · PLANTILLA SOMBRA
```

## Perfiles y accesos

Los perfiles ya no son excluyentes. Un usuario puede ser, por ejemplo, **Administrador + Dirección Deportiva + Scout**, o **Informador + Scout**. El usuario selecciona su perfil operativo en el menú lateral y la aplicación mantiene los permisos reales en base de datos.

### Informador

- Inicio de informes de No Name.
- Calendario de los partidos de No Name.
- Valoración rápida de No Name y rival.
- Mis informes.
- Jugadores.
- Jugadores ojeados en modo de consulta.

### Scout

- Inicio Scout.
- Calendario completo de la liga.
- Mi jornada.
- Misiones de Dirección Deportiva.
- Observación de cualquier partido de la competición.
- Observación específica de jugador.
- Observación espontánea.
- Informe estructurado de equipo/rival.
- Historial de mis observaciones y recuperación de borradores.
- Jugadores y Jugadores ojeados.
- Consulta de los roles, criterios y necesidades del **Modelo No Name**.

### Dirección Deportiva

- Panorama de nuestra liga.
- Calendario completo.
- Creación de misiones de scouting sobre cualquier partido.
- Jugadores 360 y evidencia específica.
- Rankings por posición observada.
- Equipos rivales.
- Seguimientos.
- Comparador orientado al Modelo No Name.
- XI de la liga.
- Consenso.
- Listas.
- Modelo No Name, necesidades, plantilla sombra y planificación de observaciones.

### Administrador

Acceso a todos los módulos anteriores más:

- importación masiva del calendario;
- confirmación rápida de horarios;
- incidencias de partidos sin horario;
- nuevo postpartido / preparación desde partido ya programado;
- usuarios y perfiles múltiples;
- calidad de datos;
- backups y rendimiento;
- Base de datos y mantenimiento.

## Calendario completo de liga

Administración puede pegar toda la competición en una operación usando **una sola fecha orientativa de jornada**:

```text
1;13/09/2026;Ciudad Rodrigo C.F.;C.D.F. Mojados
1;13/09/2026;La Cistérniga C.F.;C.D. Noname
```

La fecha publicada por Federación no se interpreta como día definitivo. Hasta que Administración confirme hora, el encuentro queda como:

- **Fecha orientativa · horario pendiente** (`provisional`).
- **Fecha y hora confirmadas** (`confirmed`).
- **Aplazado**.
- **Suspendido**.

DD puede planificar misiones Scout sobre un partido provisional. Sin embargo, el postpartido, las observaciones Scout y los informes operativos requieren fecha y hora confirmadas.

Los avisos de calendario se vuelven urgentes al acercarse la jornada. Administración confirma fecha/hora desde la incidencia sin editar todo el partido.

Los partidos de No Name importados **no se vuelven a crear** al llegar la jornada. Una vez confirmado el horario, desde Calendario se pulsa `Preparar postpartido desde este partido`, se añade resultado/alineaciones/cambios y el mismo registro pasa a publicado.

Una reimportación posterior del calendario provisional nunca sobrescribe un horario que Administración ya haya confirmado.

## Perfil Scout

### Mi jornada

Resume:

- misiones activas;
- partidos próximos de toda la liga;
- qué encuentros tienen tarea de DD;
- incidencias de horario en tareas asignadas;
- acceso directo a observar un partido.

### Misiones DD

Dirección Deportiva puede asignar cuatro tipos principales:

1. **Jugador concreto**.
2. **Varios jugadores**.
3. **Equipo**.
4. **Análisis de rival**.

Cada misión guarda partido real, scout, prioridad, propósito, focos de observación, equipo objetivo y jugadores objetivo.

### Observación individual

Cada observación Scout es independiente. El mismo scout puede ver al mismo jugador varias veces durante la temporada y se conserva todo el histórico.

Campos disponibles:

- posición observada;
- técnico;
- táctico;
- físico;
- mental;
- nivel actual;
- proyección;
- encaje preliminar No Name;
- fortalezas;
- riesgos/debilidades;
- resumen;
- recomendación;
- rol del Modelo No Name a contrastar;
- puntuación opcional de los criterios ponderados de ese rol.

El Scout solo puntúa lo que puede sostener con lo visto.

### Scouting espontáneo

Cualquier partido del calendario puede abrirse aunque DD no haya creado una misión. El Scout puede seleccionar un futbolista existente o añadir rápidamente un jugador que todavía no esté en la plantilla de ese equipo y registrar el hallazgo.

Además existe **Barrido rápido del partido**: el Scout selecciona varios futbolistas del encuentro, deja una nota de visionado y un apunte opcional para cada uno y guarda todo en una sola operación de trabajo. Sirve para aprovechar partidos neutrales completos sin obligar a abrir una ficha avanzada por cada jugador.

### Análisis de equipo/rival

Una misión de equipo dispone de formulario específico:

- estructura/sistema;
- con balón;
- sin balón;
- transiciones;
- ABP relevantes;
- jugadores clave;
- claves para No Name;
- conclusión.

Puede guardarse como avance o entregarse como tarea completada.

## Evidencia: postpartido vs scouting específico

La aplicación distingue:

- **observaciones postpartido**, que nacen de jugar contra ese futbolista;
- **observaciones Scout específicas**, creadas de forma intencionada sobre un partido concreto.

Una observación específica **no multiplica artificialmente la nota media**. En el expediente DD se muestra como evidencia adicional: número de observaciones específicas, scouts distintos, partidos y fortaleza de esa evidencia.

## Modelo No Name

Dirección Deportiva configura los perfiles reales del equipo, no una taxonomía internacional genérica.

Ejemplo:

```text
MCD · Base
- Salida limpia · peso 5
- Defensa de espacios · peso 5
- Juego de cara · peso 4
- Desplazamiento · peso 3
```

Cada rol tiene:

- posición;
- nombre;
- descripción;
- criterios;
- bloque técnico/táctico/físico/mental;
- peso 1–5.

El Scout puede contrastar esos criterios dentro de una observación.

## Necesidades y plantilla sombra

Por temporada, DD marca cada rol como:

- necesidad Alta;
- necesidad Media;
- Cubierta / No prioritaria.

Después ubica candidatos de nuestra liga en ese rol con:

- estado de temporada;
- prioridad;
- encaje DD;
- conclusión.

Las decisiones son históricas por temporada. Un jugador puede ser `Prioritario` en 2026/27 y `Seguimiento` en 2027/28 sin borrar la decisión anterior.

## Planificación automática de scouting

La aplicación cruza:

- necesidades abiertas;
- candidatos de la plantilla sombra;
- equipo actual conocido;
- calendario futuro;
- evidencia postpartido;
- evidencia Scout específica.

Así puede proponer:

```text
Necesidad Alta · MCD Base
Jugador X · Rival A
Próximo partido: Rival A - Rival B
Evidencia específica: 0
→ Planificar observación
```

Al pulsar, DD crea la misión y queda vinculada al Scout y al partido real.

## Postpartido rápido

Se mantienen las optimizaciones de 3.4/3.4.1:

- último XI propuesto automáticamente;
- formaciones estructurales;
- posición del suplente editable al entrar;
- trabajo local antes de publicar;
- evaluaciones por equipo con UPSERT SQL masivo;
- estado real de cambios sin guardar;
- botones rápidos 5/6/7/8/9;
- `0` con pocos minutos se clasifica como minutos insuficientes y no como valoración;
- PDF Resumen cotidiano y Completo bajo demanda;
- carga lazy de históricos y documentos.

## Dirección Deportiva

La inteligencia sigue centrada exclusivamente en nuestra liga:

- panorama y bandeja de decisiones;
- tendencias robustas;
- confianza 0–100 explicable;
- rankings por posición realmente observada;
- dossier por rival;
- seguimiento operativo con partido objetivo;
- comparador para roles del Modelo No Name;
- XI de liga;
- listas;
- expediente 360;
- evidencia Scout específica;
- observaciones recurrentes.

Las búsquedas densas de jugadores se filtran y paginan desde PostgreSQL para evitar cargar cientos de filas en Streamlit y filtrarlas después.

## Calidad y privacidad operativa

- Cerrar sesión elimina todo `st.session_state` operativo del navegador.
- Administración dispone de centro de Calidad de datos para detectar duplicados probables, jugadores sin posición, jugadores activos sin roster y dorsales duplicados.
- No se incluyen equipos, jugadores, partidos, informes ni bases SQLite de demostración en la release.

## Base de datos

3.7.0 mantiene el mismo esquema de la 3.6. No añade una migración nueva:

```text
0004_scout_workflow_3_3
          ↓
0005_planning_scout_3_5
          ↓
0006_player_report_360_3_6
```

La 3.5 añadió:

- capacidades múltiples por usuario (`user_roles`);
- planificación del calendario en `matches`;
- `scout_missions`;
- `scout_mission_targets`;
- `scout_observations`;
- `game_model_roles`;
- `game_model_criteria`;
- `squad_needs`;
- `player_season_decisions`;
- índices para calendario, misiones, scouting y planificación.

La 3.6 añadió `current_level`, `potential_score` y `criteria_json` a `player_season_decisions` para consolidar el Player Report 360. La 3.7 cambia únicamente la lógica operativa del calendario y conserva el esquema `0006`. Las migraciones conservan usuarios, jugadores, equipos, partidos, informes, evaluaciones, seguimientos, listas, observaciones y expedientes existentes.

## Despliegue

`Main file path` continúa siendo:

```text
app.py
```

Se mantienen los mismos Secrets y el mismo proyecto Supabase. Con:

```toml
RUN_MIGRATIONS = true
```

la aplicación aplica Alembic hasta `0006_player_report_360_3_6` al arrancar.

Antes de desplegar una versión con cambio de esquema se recomienda descargar un backup técnico.

## Validación

La release se valida mediante:

- compilación completa Python;
- **42 pruebas automatizadas**;
- instalación Alembic desde base vacía hasta 0006;
- actualización Alembic 0005 → 0006;
- calendario completo;
- multirol;
- misiones Scout;
- múltiples observaciones del mismo jugador;
- Modelo No Name y plantilla sombra;
- oportunidades de observación;
- búsquedas filtradas en SQL;
- comprobación de consistencia de release.

La latencia exacta de Streamlit Community Cloud ↔ Supabase depende de red/proveedor y se mide después del despliegue mediante las herramientas de rendimiento existentes.
