# Contexto maestro actualizado · No Name · Área Técnica 4.5

**Fecha:** 28 de octubre de 2026. **Base inalterable de partida:** ZIP completo 4.4.4.1. **Versión resultante:** 4.5. **Alembic head:** `0016_partial_reading_4_5`.

## 1. Identidad, principios y límites

Herramienta Streamlit del cuerpo técnico de C.D. Noname. Las decisiones consolidadas del contexto 4.4.4.1 siguen vigentes salvo modificación expresa en la especificación 4.5. PostgreSQL/Supabase en producción; SQLite en pruebas. Una observación pertenece a su autor, partido y fuente. Un dato ausente es desconocido, nunca cero. La selección para fichaje es decisión humana DD, nunca consecuencia automática de la nota. El equipo propio se resuelve por `own_team_id`, no comparando el texto del nombre; los clubes ficticios/test no se fusionan ni se incluyen en métricas oficiales.

## 2. Cambios principales del código 4.5

- **Operativa:** un encuentro oficial de No Name permite informe de cualquier Informador autorizado sin publicación Admin, kickoff confirmado ni asignación anterior. Una asignación expresa es prioritaria; el alta voluntaria queda trazada sin cambiar autorización. Ventana sábado/domingo suficiente para operar y escoger jornada.
- **Roles y experiencia:** `admin`, `director`, `reporter` siguen siendo roles acumulables. `can_track_players` sigue siendo capacidad independiente. `users.participation_profile` organiza Inicio en `own_only`, `full`, `free` y `viewer`, independiente de permisos. Administración puede consultar/gestionar, pero una nota deportiva exige rol Informador.
- **Informe:** entrada rápida con secciones opcionales equipo propio, rival y jugadores, nota colectiva nullable, atención cualitativa sin nota, rank top 1-3, comentario opcional y modo detallado conservado. No se entrega un formulario sin contribución sustantiva. La entrega queda incorporada directamente.
- **Identidad incompleta:** la nueva tabla `unidentified_player_signals` guarda jugador por partido/equipo/posición/dorsal/autora/evidencia sin crear un `Player` ficticio. La reconciliación vincula después el mismo hecho a una identidad real y guarda quién y cuándo resolvió. Los agregados deduplican fuente y autor/partido.
- **Contexto:** posición habitual nullable en `team_rosters` independiente de posición observada en `participations`, prioridad partido → plantilla/temporada → posición global. Formación anterior solo sugerida, jamás confirmada de oficio. Campograma por slots posicionales.
- **Dirección Deportiva:** feed explicable de notas altas, señales sin nota, rankings, repeticiones, coincidencias, discrepancias, identidades pendientes, muestra y procedencia. Pregunta contextual vinculada a un hecho concreto mediante tres FKs opcionales en `player_observation_requests`. DD decide manualmente `Interesante` y `Prioritario`. Las respuestas recientes se presentan vinculadas a su petición. La ficha de equipo y Player 360 muestran cobertura y contexto.
- **PDF:** informe completo y resumen incluyen destacado sin nota y evidencia provisional, conservan señales en el snapshot histórico versionado. Los PDFs del Player 360 incluyen cobertura con muestra.
- **Jornada:** muestra aportaciones entregadas de verdad, separadas de asignaciones, y estado del informe propio.

## 3. Esquema nuevo

Migración `0016_partial_reading_4_5.py`, aditiva: `users.participation_profile`; `team_rosters.usual_position`; `player_evaluations.highlight_rank` y `attention_signal`; `match_opinion_players.highlight_rank` y `attention_signal`; tabla `unidentified_player_signals`; `player_observation_requests.origin_player_evaluation_id`, `origin_neutral_signal_id`, `origin_unidentified_signal_id`. Las 42 entidades originales, tablas históricas y los datos reales siguen en el esquema. No hay reset, drop ni relleno ficticio de posiciones.

## 4. Organización del código

- Arranque, autorización y configuración: `app.py`, `core/`, `models/entities.py`.
- Dominio y presentación anterior: `repositories/`, `views/`, `ui/`, `reports/`, `services/`.
- Lógica nueva: `repositories/unidentified_players.py`, `repositories/dd_attention.py`, `views/attention.py`, `ui/position_picker.py`.
- Cambios transversales: `repositories/reports.py`, `sporting_reading.py`, `workspaces.py`, `player_report.py`, `observation_requests.py`, `views/reports.py`, `jornada.py`, `home.py`, `team_hub.py`, `squad.py`, `admin.py`, `postmatch.py`, PDFs y reglas de postpartido.

## 5. Estado de verificación a fecha de entrega

- ZIP original 4.4.4.1: **167 pruebas**, antes de tocar código.
- Código final 4.5: **183 pruebas locales**, incluyendo contratos nuevos y pruebas de migración SQLite.
- Python `compileall` y `check_release_consistency.py`: superados.
- Alembic SQLite desde cero hasta 0016 y actualización con histórico desde 0015: superados.
- Actualización desde una base creada por Alembic del ZIP **original**, con fila antigua preservada: verificada.
- PDF actual y snapshot versionado, completo/resumen: generación y extracción de texto comprobadas para caso anónimo sin nota.
- **PENDIENTE antes de declarar producción validada:** PostgreSQL real en copia autorizada, Streamlit Cloud + Secrets/Storage, UI navegador y móvil 375 px, concurrencia y restauración de backup. No hay acceso a esas infraestructuras en esta entrega. Los tests no sustituyen aceptación manual del cuerpo técnico.

## 6. Reglas de mantenimiento

Actualizar sobre este ZIP 4.5, nunca reconstruir de memoria ni mezclar ZIP antiguos. Mantener el contexto maestro 4.4.4.1 original como archivo histórico, y la especificación completa 4.5 como contrato funcional. Respetar datos productivos; preparar `pg_dump` y backup del bucket, ensayar la migración sobre copia aislada y comprobar el head físico antes de desplegar. La prueba del entorno real es el último hito de aceptación, no un detalle ya certificado.
