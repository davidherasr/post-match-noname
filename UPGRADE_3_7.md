# Actualización a No Name PostMatch 3.7.0

## Base de datos

No hay migración nueva.

La versión continúa en:

```text
0006_player_report_360_3_6
```

No cambies `DATABASE_URL`, Supabase ni los Secrets.

Las columnas `window_start/window_end` se conservan por compatibilidad histórica, pero los nuevos calendarios 3.7 ya no las necesitan.

## Despliegue

```bash
git add -A
git commit -m "No Name PostMatch 3.7.0 - calendario operativo"
git push origin main
```

Después reinicia la aplicación en Streamlit Cloud.

## Importar el calendario real 2026/27

Usa `Calendario_NoName_2026_27_IMPORTAR_3.7.txt`.

Cada línea utiliza una sola fecha de referencia:

```text
1;13/09/2026;La Cistérniga C.F.;C.D. Noname
```

La previsualización debe mostrar:

```text
240 partidos reconocidos
0 errores
```

Los 240 quedan con horario pendiente. Administración confirma después fecha y hora encuentro por encuentro cuando se publiquen los horarios reales.
