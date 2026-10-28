# Upgrade 4.0.7

4.0.7 mejora el flujo de partido neutral y scouting sin cambios de esquema.

- El editor de XI diferencia **titulares**, **suplentes** y **resto de plantilla**.
- Los desplegables del campograma muestran ese estado y siguen ocultando jugadores ya usados en otra posición.
- Puede guardarse el **banquillo** junto al XI.
- La lista pegada de Federación admite bloques `TITULARES` / `SUPLENTES` o prefijos `T;` / `S;`.
- Una lista simple `dorsal;nombre` sigue siendo únicamente plantilla de temporada: nunca se supone que las primeras 11 líneas sean titulares.
- Si no se conoce la formación pero sí la convocatoria, Jornada muestra titulares y suplentes por separado.
- Scouting usa etiquetas operativas más explícitas: **Barrido rápido**, **Observación individual** y **Dossier completo**, con explicación contextual.
- En los selectores de Scouting los jugadores aparecen identificados como `TIT`, `SUP` o `PLANTILLA`.

No añade migración. El head sigue siendo `0010_core_workspace_schema_repair_4_0_4`.
