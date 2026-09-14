# Prueba real de Jornada 1 · 13/09/2026

Partido de referencia para probar la 3.9.0:

**Jornada 1 · La Cistérniga C.F. - C.D. Noname · 13/09/2026**

La release no inventa hora, resultado, alineaciones ni jugadores. Debe consumir los datos existentes de tu Supabase.

## Si ya tienes el calendario 2026/27 cargado

No importes nada. Tras desplegar 3.9.0:

1. Entra en **Inicio**. Si la fecha operativa es 13/09/2026, el partido debe aparecer como **Partido de hoy**.
2. Entra en **Jornada**. Debe abrir por defecto **Jornada 1** y colocar el partido de No Name primero.
3. Abre **La Cistérniga C.F. - C.D. Noname**.
4. Si la hora real todavía no está confirmada, Administración debe escribirla manualmente. El campo empieza vacío: 3.9 no propone 17:00 ni ninguna otra hora.
5. Cuando el horario esté confirmado, **Preparar partido** reutiliza ese Match del calendario; no crea otro partido.
6. Completa resultado, XI y cambios reales. Después publica y comprueba que los informadores asignados reciben el partido desde el mismo Match Hub.

## Si el partido no existe todavía

El fichero `J1_REAL_2026_27.txt` contiene únicamente esta jornada real y puede importarse desde:

**Jornada → Importar calendario / mantenimiento excepcional → Herramientas de calendario → Importar**

La importación es idempotente respecto a jornada/local/visitante y no sobrescribe un horario ya confirmado con una fecha provisional.

## Comprobación de datos

Administración → Datos muestra un bloque **Estado operativo de la temporada** con temporada activa, número de partidos, jornadas, tamaño de plantilla y partido de hoy/próximo partido.

En un entorno que tenga configurada la `DATABASE_URL` real también puede ejecutarse, en modo solo lectura:

```bash
python scripts/check_matchday_readiness.py
```

No se incluyen datos demo ni se modifica Supabase desde este script.
