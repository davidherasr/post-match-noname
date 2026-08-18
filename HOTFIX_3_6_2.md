# No Name PostMatch 3.6.2 · Calendar importer compatibility

La 3.6.2 refuerza el importador de calendario y hace visible la versión del parser para evitar confundir una app desplegada con código anterior.

## Formatos admitidos

- `12/09/2026-13/09/2026`
- `12-13/09/2026` cuando ambos días están en el mismo mes
- `31/10/2026-01/11/2026`
- `31/10-01/11/2026`

Todas las ventanas de dos fechas se guardan como **horario pendiente**.

## Interfaz

La pantalla de Calendario muestra `Importador 3.6.2` y permite pegar el texto o cargar directamente un `.txt`. Antes de importar muestra partidos reconocidos y errores.

## Base de datos

No hay migración nueva. Se mantiene `0006_player_report_360_3_6`.
