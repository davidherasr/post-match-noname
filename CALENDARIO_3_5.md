# Calendario completo 3.5

## Alcance

El calendario representa **toda la competición**. Incluye partidos de No Name y partidos neutrales entre cualquier pareja de rivales.

## Importación masiva

Formatos admitidos:

```text
1;15-16/08/2026;La Bañeza;Laguna
1;15-16/08/2026;No Name;Benavente
2;22/08/2026;18:30;Laguna;No Name
```

También se aceptan variantes con fecha única y campo.

La previsualización se valida antes de escribir. La importación crea equipos inexistentes y crea/actualiza fixtures de una vez.

## Estados de programación

- `window`: fin de semana conocido, horario pendiente.
- `date_confirmed`: fecha definitiva, hora pendiente.
- `confirmed`: fecha y hora definitivas.
- `postponed`: aplazado.
- `cancelled`: suspendido.

## Incidencias

Administración dispone de `Horarios pendientes`. Los partidos sin hora dentro del horizonte próximo aparecen como pendientes o urgentes según cercanía.

Al confirmar un horario se actualiza el partido existente. Las misiones, objetivos de scouting y demás relaciones permanecen intactas.

## Por perfil

### Informador
Ve los partidos de No Name.

### Scout
Ve toda la liga y puede abrir cualquier partido para observar.

### Dirección Deportiva
Ve toda la liga y puede crear una misión de scouting vinculada al encuentro.

### Administrador
Ve/edita todo, importa la temporada y resuelve horarios.

## No Name

Un fixture importado de No Name es el mismo objeto que después se utiliza para el postpartido. No se duplica al llegar la jornada.
