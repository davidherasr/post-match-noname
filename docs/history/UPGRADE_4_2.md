# Upgrade 4.2.0

1. Sustituye el código completo por la release 4.2.0.
2. Mantén tus Secrets de Streamlit Cloud.
3. Mantén `RUN_MIGRATIONS = true`.
4. Reinicia la aplicación.

## Migración

El head pasa de `0011_user_lifecycle_4_1_1` a `0012_sporting_reading_4_2`.

La migración es aditiva/no destructiva:
- añade `users.can_track_players`;
- añade `reports.own_team_rating` y `reports.rival_team_rating`;
- crea `staff_sporting_weights`;
- crea `match_opinions`;
- crea `match_opinion_players`.

Los usuarios heredados con rol `scout` reciben `can_track_players = true`, se les añade Informador si no lo tenían y se retira el rol Scout organizativo. Los históricos de observaciones y misiones no se borran.

## Después de actualizar

En Administración → Usuarios, activa **Puede realizar seguimiento individual de jugadores** únicamente para las personas que deban hacer seguimiento longitudinal. En Dirección Deportiva → Criterio del staff puedes ajustar los pesos de opinión por contexto.
