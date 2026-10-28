# Actualización a No Name PostMatch 3.6.0

## Resumen

La 3.6.0 añade **Player Report 360**, una presentación profesional y accionable de los datos de jugadores ya recogidos por No Name PostMatch.

## Base de datos

Esta versión incluye una migración no destructiva:

```text
0005_planning_scout_3_5
          ↓
0006_player_report_360_3_6
```

Añade tres campos opcionales a `player_season_decisions`:

- `current_level`;
- `potential_score`;
- `criteria_json`.

No se eliminan tablas, columnas ni datos existentes.

Por tanto se mantiene:

- el mismo proyecto Supabase;
- la misma `DATABASE_URL`;
- los mismos Secrets;
- usuarios y roles existentes;
- calendario de liga;
- partidos;
- jugadores;
- informes;
- observaciones Scout;
- misiones;
- Modelo No Name y necesidades.

## Antes de actualizar

Al tratarse de una versión con migración se recomienda generar un **backup técnico** desde Administración.

## Despliegue

Sustituye el contenido del repositorio por la 3.6.0 y ejecuta:

```bash
git add -A
git commit -m "No Name PostMatch 3.6.0 - Player Report 360"
git push origin main
```

Después haz **Reboot** en Streamlit Community Cloud.

`Main file path` continúa siendo:

```text
app.py
```

No cambies los Secrets. Con `RUN_MIGRATIONS = true`, Alembic aplica automáticamente `0006_player_report_360_3_6` sobre la base actual.

## Primera comprobación recomendada

1. Iniciar sesión como Administración/DD.
2. Abrir `Jugadores ojeados`.
3. Abrir cualquier futbolista con observaciones.
4. Entrar en `Player Report 360`.
5. Si existe un rol del Modelo No Name, consolidar criterios DD.
6. Generar una Ficha Scout Ejecutiva y comprobar el PDF.
7. Revisar `Modelo No Name → Plantilla sombra` para mapear referencias de la plantilla propia si se desea comparación interna.
