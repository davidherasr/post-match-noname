# Actualización a No Name PostMatch 3.8.0

## Antes de actualizar

Haz un backup técnico desde la versión 3.7.0 antes de desplegar.

La 3.8.0 mantiene el mismo proyecto Supabase, `DATABASE_URL` y Secrets. La migración es no destructiva y conserva las estructuras legacy para mantener histórico y permitir recuperación.

## Base de datos

Alembic avanza de:

```text
0006_player_report_360_3_6
        ↓
0007_product_consolidation_3_8
```

La consolidación incorpora `ScoutObservation` como evidencia operativa, `PlayerSeasonDecision` como decisión deportiva por temporada, normalización de necesidades y unificación de la próxima acción/misiones sin borrar el histórico anterior.

## Despliegue

Sustituye el contenido del repositorio por el contenido de este ZIP, mantén los mismos Secrets y `Main file path = app.py`.

```bash
git add -A
git commit -m "No Name PostMatch 3.8.0 - simplificacion total"
git push origin main
```

Después realiza **Reboot app** en Streamlit Community Cloud.

Con `RUN_MIGRATIONS=true`, la migración `0007_product_consolidation_3_8` se aplicará automáticamente.

## Comprobaciones de producto

La navegación normal pasa a **Inicio / Jornada / Jugadores / Plantilla / Administración** según permisos. Los roles son capacidades acumulativas y ya no requieren Perfil activo. Jornada actúa como centro operativo mediante Match Hub; Jugadores utiliza una ficha única y Player Report 360; Plantilla reúne Modelo No Name, necesidades y candidatos.
