# Actualización a No Name PostMatch 3.5.0

## Importante

3.5.0 **sí cambia la estructura de base de datos**. Antes de desplegar, descarga un backup técnico si ya tienes información que quieras conservar.

La migración es no destructiva:

```text
0004_scout_workflow_3_3
          ↓
0005_planning_scout_3_5
```

Conserva los datos deportivos existentes.

## Qué añade

- calendario/horarios en `matches`;
- `user_roles`;
- `scout_missions`;
- `scout_mission_targets`;
- `scout_observations`;
- `game_model_roles`;
- `game_model_criteria`;
- `squad_needs`;
- `player_season_decisions`;
- índices nuevos.

El rol principal antiguo de cada usuario se copia automáticamente como primera capacidad en `user_roles`.

## Secrets

No cambies:

- `DATABASE_URL`;
- credenciales de Supabase;
- configuración del administrador.

Mantén:

```toml
RUN_MIGRATIONS = true
```

## Despliegue

Sustituye todo el contenido del repositorio por 3.5.0 y ejecuta:

```bash
git add -A
git commit -m "No Name PostMatch 3.5.0 - calendario y Scout"
git push origin main
```

Después haz **Reboot** en Streamlit Community Cloud.

`Main file path` continúa siendo:

```text
app.py
```

## Primer arranque

1. Inicia sesión como Administrador.
2. Comprueba Administración → Rendimiento / conexión.
3. Comprueba que Alembic está en `0005_planning_scout_3_5`.
4. Asigna el perfil `Scout` a los usuarios que deban cubrir partidos neutrales.
5. Importa el calendario de la liga.
6. Define los roles del Modelo No Name cuando quieras comenzar la planificación DD.
