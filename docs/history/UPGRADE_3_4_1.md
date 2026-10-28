# Actualización a No Name PostMatch 3.4.1

Esta versión es una actualización de calidad de vida sobre la 3.4.0.

## Base de datos

No hay migración nueva. Se mantiene `0004_scout_workflow_3_3`, por lo que continúan intactos el mismo Supabase, `DATABASE_URL`, usuarios, jugadores, partidos, informes y Secrets.

## Cambios

- Nuevo postpartido con configuración habitual precargada desde el último partido: competición, sistema de No Name e informadores.
- Recuperación directa del último borrador desde el dashboard de Administración.
- Progreso por equipo y filtro `Solo pendientes` en la valoración rápida.
- Apertura directa del expediente desde `Necesitan una decisión` en Dirección Deportiva.

## Despliegue

Sustituye el contenido del repositorio por esta versión y ejecuta:

```bash
git add -A
git commit -m "No Name PostMatch 3.4.1 - mejoras de flujo"
git push origin main
```

Después haz **Reboot** en Streamlit Community Cloud. No cambies los Secrets ni el Main file path (`app.py`).
