# Actualización a No Name PostMatch 3.3.0

## Compatibilidad

3.3.0 usa el **mismo proyecto Supabase y los mismos Secrets**. No incluye datos deportivos de demostración.

La migración nueva es:

```text
0003_league_intelligence_3_2
        ↓
0004_scout_workflow_3_3
```

Es no destructiva: crea las tablas de scouting avanzado y añade índices de rendimiento. No elimina usuarios, partidos, jugadores, informes, evaluaciones, listas ni seguimientos existentes.

## Antes de actualizar

Si ya hay datos reales, descarga un backup técnico desde Administración.

## Despliegue

Sustituye **todo** el contenido de tu repositorio por el ZIP 3.3.0 y ejecuta:

```bash
git add -A
git commit -m "No Name PostMatch 3.3.0 - scouting avanzado y optimización"
git push origin main
```

Después, en Streamlit Community Cloud, haz **Reboot**.

No cambies:

- `DATABASE_URL`
- `SUPABASE_URL`
- claves de Storage
- `Main file path`, que sigue siendo `app.py`

Con `RUN_MIGRATIONS = true`, Alembic aplicará 0004 automáticamente.
