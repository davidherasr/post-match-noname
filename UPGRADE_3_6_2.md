# Actualización a No Name PostMatch 3.6.2

Hotfix sin cambios de base de datos. Mantiene el mismo Supabase, Secrets y migración `0006_player_report_360_3_6`.

## Comprobación visual

Después de desplegar, entra en **Calendario → Importar calendario completo** y comprueba que aparece `Importador 3.6.2`. Si no aparece, Streamlit sigue ejecutando una versión anterior.

## Despliegue

```bash
git add -A
git commit -m "No Name PostMatch 3.6.2 - calendar importer compatibility"
git push origin main
```

Después haz **Reboot** en Streamlit Community Cloud.
