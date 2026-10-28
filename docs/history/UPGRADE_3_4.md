# Actualización a No Name PostMatch 3.4.0

## Base de datos

3.4.0 usa **el mismo Supabase, la misma DATABASE_URL y los mismos Secrets**.

No existe migración 0005: la revisión actual sigue siendo `0004_scout_workflow_3_3`. No se borra, renombra ni transforma ninguna tabla en esta actualización.

## Actualización

Sustituye todo el contenido del repositorio por el ZIP 3.4.0 y ejecuta:

```bash
git add -A
git commit -m "No Name PostMatch 3.4.0 - cierre auditoria y rendimiento"
git push origin main
```

En Streamlit Cloud: **Reboot**. El Main file path continúa siendo `app.py`.

## Comprobación recomendada tras desplegar

Entra como Administrador → `Administración` → `Rendimiento`.

1. Pulsa **Probar conexión y lecturas**.
2. Pulsa **Ejecutar aceptación real (rollback)**.

La segunda prueba usa la base configurada de verdad, crea un flujo temporal dentro de un SAVEPOINT y lo revierte. Si termina correctamente, valida conexión, escritura, bulk upsert, posición observada y apertura de ficha scout sin dejar datos deportivos de prueba.
