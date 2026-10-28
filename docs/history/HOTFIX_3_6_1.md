# No Name PostMatch 3.6.1 · Calendar window hotfix

La 3.6.1 corrige un caso real detectado al importar el calendario oficial 2026/27: una jornada puede abarcar dos meses, por ejemplo **31 de octubre–1 de noviembre de 2026**.

La 3.6.0 interpretaba `31-01/11/2026` como si ambos días pertenecieran a noviembre y fallaba porque noviembre no tiene día 31.

## Formato recomendado

Usa siempre las dos fechas completas:

```text
8;31/10/2026-01/11/2026;C.D. Ribert;La Bañeza F.C.
```

También sigue admitido el formato compacto cuando la ventana no cambia de mes:

```text
7;24-25/10/2026;C.D.F. Cubillos;Betis C.F.
```

## Semántica

Una ventana de dos fechas significa **fin de semana previsto / horario pendiente**. No confirma el día de juego ni la hora. Cuando Federación o el club comunique el horario definitivo, Administración lo actualizará desde las incidencias de calendario.

## Base de datos

No hay migración nueva. Se mantienen los mismos datos, Supabase y Secrets.
