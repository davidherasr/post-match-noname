# Actualización No Name PostMatch 4.0.4

## Motivo

4.0.3 reparaba las columnas añadidas en 3.5-4.0, pero el contrato de arranque comprobaba solo ese subconjunto. SQLAlchemy, sin embargo, hidrataba la entidad `Match` completa y además hacía `joinedload` de `Competition` y `Team`. Por ello una base histórica podía superar el chequeo de 4.0.3 y fallar después en `Inicio` con `sqlalchemy.exc.ProgrammingError`.

## Corrección

- Nueva migración no destructiva `0010_core_workspace_schema_repair_4_0_4`.
- Repara campos opcionales/defaultables de `matches`, `teams`, `competitions` y `seasons` que puedan faltar en una base antigua.
- El contrato físico de arranque comprueba ahora **todas** las columnas ORM usadas por esas entidades, no solo las recientes.
- `Inicio` deja de cargar `Competition` y todas las columnas de `Match` cuando únicamente necesita jornada, fecha/hora, resultado y nombres de equipos.
- No se borran ni recrean partidos, jugadores, informes, observaciones o calendario.

Mantén el mismo Supabase, `DATABASE_URL` y Secrets, con `RUN_MIGRATIONS = true`.
