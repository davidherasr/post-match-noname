# Perfil Scout 3.5 · especificación completa

## Propósito

El perfil Scout cubre partidos de la liga en los que No Name puede no participar. Su trabajo alimenta al mismo expediente de jugador que el postpartido, pero queda identificado como **observación específica** o **espontánea**.

## Accesos

```text
SCOUT
├── Inicio Scout
├── Calendario de liga
├── Misiones
├── Jugadores ojeados
└── Jugadores
```

Dentro de `Misiones` dispone de:

```text
Mi jornada
Misiones
Observar partido
Mis observaciones
Modelo No Name
```

## Inicio Scout

Muestra:

- misiones pendientes;
- observaciones entregadas;
- próximos partidos del calendario;
- prioridad de trabajo;
- tareas cuyo horario exacto todavía está pendiente;
- acceso al calendario completo.

## Mi jornada

Combina partidos de los próximos diez días con tareas asignadas. El Scout puede abrir cualquier encuentro y comenzar una observación aunque no exista misión previa.

## Misiones

Una misión es creada por Dirección Deportiva/Admin y contiene:

- partido;
- tipo;
- equipo foco;
- uno o varios jugadores si procede;
- scout asignado;
- prioridad;
- objetivo/pregunta a resolver;
- focos de observación;
- estado;
- resultado.

Tipos:

- Jugador concreto.
- Varios jugadores.
- Equipo.
- Análisis de rival.

## Observación específica

Cada clic en `Observar` crea una observación independiente. No hay restricción de una ficha por scout/jugador: puede existir una serie de observaciones a lo largo de la temporada.

Campos:

- posición observada;
- técnico;
- táctico;
- físico;
- mental;
- nivel actual;
- proyección;
- encaje No Name;
- rol del Modelo No Name;
- criterios específicos ponderados del rol;
- fortalezas;
- riesgos;
- resumen;
- recomendación.

Puede guardarse como borrador y recuperarse desde `Mis observaciones`.

## Observación espontánea

El Scout selecciona cualquier partido del calendario y cualquier jugador de las plantillas. Si el jugador todavía no existe puede añadirlo rápidamente a ese equipo/temporada y abrir una observación espontánea.

### Barrido rápido

Para partidos neutrales completos puede seleccionar varios jugadores y registrar en una única pantalla una **nota de visionado** + apunte opcional. Cada fila se guarda como evidencia Scout independiente (`match_scan`) y puede profundizarse más adelante si DD lo considera necesario.

## Análisis rival/equipo

Formulario específico:

- estructura/sistema;
- comportamiento con balón;
- comportamiento sin balón;
- transiciones;
- ABP relevantes;
- jugadores clave;
- claves para No Name;
- conclusión.

Permite guardar avance y completar la misión.

## Modelo No Name

El Scout ve en modo consulta:

- posiciones/roles definidos por DD;
- descripción;
- necesidad actual;
- criterios;
- peso de cada criterio;
- definición de lo que debe observar.

La edición del modelo sigue reservada a DD/Admin.

## Evidencia

El expediente distingue siempre:

- número de informes postpartido;
- número de observaciones Scout específicas;
- scouts distintos;
- partidos específicos;
- fortaleza de la evidencia.

El scouting específico aumenta el contexto de decisión, no la nota media de forma artificial.

## Multirol

El perfil Scout es una capacidad. Un mismo usuario puede tener simultáneamente Scout + Informador + Administrador + Dirección Deportiva, según sus responsabilidades. El menú lateral permite cambiar el perfil operativo.
