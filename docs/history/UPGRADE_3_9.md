# Actualización a No Name PostMatch 3.9.0

## Objetivo

3.9.0 es una release de **Matchday, fiabilidad y pulido** sobre 3.8.0. Mantiene la arquitectura de producto simplificada y está pensada para empezar a trabajar con datos reales desde la Jornada 1.

## Base de datos

No hay migración nueva en 3.9.0. El head continúa en:

```text
0007_product_consolidation_3_8
```

Por tanto se mantiene el mismo Supabase, `DATABASE_URL`, Secrets, usuarios, calendario, jugadores, informes, observaciones, decisiones, Modelo No Name y documentos.

## Mejoras principales

- Día operativo calculado con `Europe/Madrid`, no con la zona horaria del servidor de Streamlit Cloud.
- Inicio distingue **Partido de hoy** de **Próximo partido**.
- Jornada abre automáticamente la ronda que corresponde al partido de No Name más próximo y marca los encuentros de hoy.
- Nuevo panel de **Estado operativo de la temporada** en Administración → Datos.
- Script de comprobación de matchday en modo solo lectura.
- Flujo multirol corregido también en Informes y herramientas de calendario: los permisos acumulativos ya no dependen del perfil principal antiguo.
- Eliminado definitivamente el valor 17:00 inventado en la herramienta heredada de horarios.
- Las herramientas de calendario vuelven siempre a **Jornada**, no a módulos retirados como Misiones o Nuevo postpartido.
- Textos técnicos retirados del trabajo diario.
- Parser de calendario y contratos de release actualizados a 3.9.0.
- Prueba automatizada específica con la Jornada 1 real `La Cistérniga C.F. - C.D. Noname`.

## Despliegue

Haz primero un backup técnico desde Administración. Después sustituye el repositorio completo por el contenido del ZIP 3.9.0 y mantén los mismos Secrets.

```bash
git add -A
git commit -m "No Name PostMatch 3.9.0 - matchday y fiabilidad"
git push origin main
```

En Streamlit Community Cloud ejecuta **Reboot app**. `Main file path` sigue siendo `app.py`.

Consulta `PRUEBA_REAL_J1.md` para la prueba de hoy.
