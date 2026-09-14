# No Name PostMatch 4.0.0 · Match Study

## Objetivo de producto

4.0 resuelve un problema real del scouting de partidos neutrales: **no siempre disponemos del mismo nivel de información para los dos equipos**. Un partido puede tener vídeo o no; puede conocerse la estructura del local y no la del visitante; puede existir una plantilla federativa completa aunque no exista un XI fiable.

La aplicación deja de obligar a fingir una formación para poder trabajar. El principio nuevo es:

> **registrar únicamente lo que sabemos y adaptar la interfaz a esa evidencia.**

## Cambios principales

1. **Vídeo Sí/No a nivel de partido neutral.** Se guarda como contexto real del visionado, con referencia opcional.
2. **Formación conocida Sí/No por equipo**, de forma independiente para local y visitante.
3. **Modo campograma** cuando una formación es conocida.
4. **Modo plantilla/dorsal** cuando la formación no se conoce.
5. **Importación rápida de plantilla Federación** pegando una lista de jugadores; no crea falsas participaciones en el partido.
6. **XI observado editable por posiciones del sistema** cuando existe formación fiable.
7. **Campograma visual responsive** con dorsal y jugador.
8. **Un partido puede mezclar modos**: por ejemplo local 4-3-3 en campograma y visitante como lista federativa.
9. **Notas generales de estudio** y referencia de vídeo sin convertirlas en datos tácticos inventados.
10. **Filtro Scout por equipo** en partidos neutrales para no buscar entre 40-50 futbolistas a la vez.
11. **Jornada informa del contexto**: vídeo disponible/no disponible y número de formaciones conocidas (0/2, 1/2, 2/2).
12. **Permiso Scout más natural**: un Scout puede capturar un XI de un partido neutral, pero no modificar la alineación de No Name.
13. **Exportación analítica enriquecida** con contexto de vídeo, formación conocida y notas de estudio.
14. **Migración no destructiva 0008**: las formaciones ya existentes se reconocen automáticamente como conocidas.
15. **No se inventa información**: si no conocemos formación, posición o dorsal, el dato permanece vacío.

## Flujo ideal · Sarego - Cubillos

```text
JORNADA
  ↓
SAREGO - CUBILLOS
  ↓
ESTUDIO DEL PARTIDO
  Vídeo: Sí / No
  Sarego: Formación Sí → 4-3-3 → XI → campograma
  Cubillos: Formación No → plantilla Federación por dorsal
  ↓
SCOUTING
  Equipo: Sarego / Cubillos / Ambos
  Barrido · Observación · Dossier
```

No hace falta crear una formación ficticia de Cubillos para poder tener a sus jugadores identificados y preparados para futuras observaciones.

## Modelo de datos

La migración `0008_match_study_4_0` añade a `matches`:

- `video_available`;
- `video_reference`;
- `home_formation_known`;
- `away_formation_known`;
- `study_notes`.

No elimina ni renombra columnas previas. `home_formation` y `away_formation` siguen siendo las formaciones reales conocidas. `TeamRoster` sigue siendo la fuente de la plantilla federativa; `Participation` se reserva para jugadores realmente identificados como participantes/XI.

## Compatibilidad

Se conserva el mismo Supabase y todos los datos 3.9. La migración marca automáticamente como `formation_known=true` cualquier formación preexistente no vacía. Una formación inexistente no se rellena con ningún sistema por defecto.
