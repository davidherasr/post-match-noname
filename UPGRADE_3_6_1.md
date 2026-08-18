# Actualización a No Name PostMatch 3.6.1

La 3.6.1 es un hotfix de calendario sobre la 3.6.0. Corrige la importación de fines de semana que cruzan de mes o de año.

## Qué cambia

- Se admite `31/10/2026-01/11/2026` como una única ventana de jornada.
- La ventana sigue siendo **horario pendiente**: no confirma ni el día exacto ni la hora.
- El formato compacto `15-16/08/2026` continúa funcionando cuando ambos días están en el mismo mes.
- El importador muestra ejemplos con el formato explícito recomendado.

## Base de datos

No hay migración nueva. Se mantiene `0006_player_report_360_3_6`, el mismo Supabase y los mismos Secrets.

## Despliegue

```bash
git add -A
git commit -m "No Name PostMatch 3.6.1 - hotfix calendario"
git push origin main
```

Después haz **Reboot** en Streamlit Community Cloud.
