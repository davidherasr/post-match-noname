# Calendario operativo 3.7

## Regla principal

La fecha importada desde el calendario federativo es **orientativa** hasta que Administración confirma una hora.

Formato recomendado:

```text
1;13/09/2026;Ciudad Rodrigo C.F.;C.D.F. Mojados
1;13/09/2026;La Cistérniga C.F.;C.D. Noname
```

Estado resultante:

```text
Fecha de referencia: 13/09/2026
Horario: pendiente
Estado: provisional
```

No se interpreta como “se juega el domingo 13”.

## Confirmación

Cuando se conozca el dato real:

```text
Fecha definitiva: 12/09/2026
Hora definitiva: 18:00
```

El partido pasa a `confirmed` y se habilitan las acciones operativas.

## Qué se puede hacer antes de confirmar

- consultar la jornada;
- ver el rival;
- planificar una misión Scout;
- asignar el Scout;
- definir jugador/equipo objetivo, motivo y focos.

## Qué requiere fecha + hora confirmadas

- preparar el postpartido desde Calendario;
- publicar un nuevo postpartido;
- iniciar una observación Scout vinculada al partido;
- barrido rápido;
- completar análisis rival asociado al encuentro;
- iniciar un informe nuevo sobre un partido todavía programado.

## Reimportación segura

Si un horario ya fue confirmado manualmente, volver a pegar el calendario provisional **no lo sobrescribe**.
