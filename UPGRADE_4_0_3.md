# Actualización No Name PostMatch 4.0.3

## Motivo

En el primer uso real de 4.0.2, Streamlit alcanzó `Inicio` pero PostgreSQL devolvió `sqlalchemy.exc.ProgrammingError` al cargar el próximo partido. El traceback mostraba que el fallo aparecía al ejecutar un `SELECT Match` desde `repositories/workspaces.py`.

Como Streamlit Cloud redacta el mensaje SQL original, la release no asume una columna concreta. 4.0.3 corrige la clase completa del problema: una revisión Alembic que no coincide con la estructura física realmente disponible.

## Migración

Nuevo head:

```text
0008_match_study_4_0
        ↓
0009_schema_repair_4_0_3
```

`0009` es idempotente y no destructiva. Comprueba y, solo si faltan, añade:

- calendario: `window_start`, `window_end`, `kickoff_at`, `schedule_status`, `fixture_type`;
- Match Study: `video_available`, `video_reference`, `home_formation_known`, `away_formation_known`, `study_notes`;
- decisión 360: `current_level`, `potential_score`, `criteria_json`;
- observación Scout consolidada: `observation_level`, `model_role_id`, `legacy_review_id`.

No borra ni recrea tablas. No modifica resultados, jugadores, informes, observaciones o decisiones. Las formaciones ya conocidas solo se marcan como conocidas.

## Despliegue

Mantén el mismo Supabase y los mismos Secrets. Es importante que exista:

```toml
RUN_MIGRATIONS = true
```

Sustituye el repositorio por el contenido completo de 4.0.3, confirma y sube:

```bash
git add -A
git commit -m "No Name PostMatch 4.0.3 - schema repair"
git push origin main
```

Después: **Streamlit Cloud → Manage app → Reboot**.

## Protección adicional

Después de ejecutar Alembic, el arranque valida físicamente las columnas críticas. Si la base siguiera incompleta, la aplicación se detiene antes de `Inicio` y muestra qué tabla/columnas faltan, en lugar de dejar que una consulta ORM produzca un traceback.
