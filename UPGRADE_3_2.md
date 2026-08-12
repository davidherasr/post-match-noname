# Actualización a No Name PostMatch 3.2.0

## Qué cambia

Esta versión sí modifica el esquema de base de datos. Añade la revisión Alembic:

```text
0002_noname_3_0
        ↓
0003_league_intelligence_3_2
```

La migración es **aditiva y no destructiva**: no elimina ni reescribe jugadores, usuarios, partidos, informes o evaluaciones existentes.

## Antes de actualizar

1. Desde la versión actual, descarga un **backup técnico ZIP** si ya hay datos reales.
2. No crees otro proyecto de Supabase.
3. No cambies `DATABASE_URL` ni el resto de Secrets.

## Actualización de código

Sustituye el contenido del repositorio por el contenido completo del ZIP 3.2.0 y ejecuta:

```bash
git add -A
git commit -m "No Name PostMatch 3.2.0 - league intelligence y workflow rápido"
git push origin main
```

En Streamlit Community Cloud haz **Reboot**.

Con:

```toml
RUN_MIGRATIONS = true
```

el arranque ejecutará `alembic upgrade head` y avanzará automáticamente a `0003_league_intelligence_3_2`.

## Qué debe aparecer después

La base seguirá conteniendo todos los datos anteriores y añadirá cuatro tablas funcionales nuevas:

- `postmatch_drafts`
- `league_player_profiles`
- `scouting_lists`
- `scouting_list_items`

## Rollback

El código 3.1 no conoce las nuevas funciones de DD, pero las nuevas tablas son aditivas. Si hubiera un problema visual se puede volver temporalmente al commit 3.1 sin borrar estas tablas. Para revertir físicamente el esquema se debe utilizar Alembic/backup, no borrar tablas manualmente en Supabase.
