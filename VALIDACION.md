# Validación técnica · No Name PostMatch 3.7.0

## Release

- `VERSION`: 3.7.0
- `APP_VERSION`: 3.7.0
- contrato `pages/reports.py`: 3.7.0
- Alembic head: `0006_player_report_360_3_6`
- migración nueva: no

## Suite automatizada

```text
49 passed
```

Se cubre específicamente:

- importación con una única fecha orientativa;
- rechazo claro de rangos antiguos;
- importación directa de fecha+hora confirmadas;
- calendario completo;
- misión DD creada antes de conocer horario;
- bloqueo de observación Scout mientras el partido es provisional;
- desbloqueo tras confirmar fecha/hora;
- sincronización de `ScoutMission.due_at` con el kickoff confirmado;
- reimportación provisional sin destruir un horario confirmado;
- bloqueo de informes nuevos sobre un `scheduled` sin horario;
- permisos multirol usando `user_roles` y no solo el perfil principal;
- Player Report 360;
- PDFs;
- evaluación rápida;
- inteligencia DD;
- seguridad y flujos heredados.

## Calendario real 2026/27

El fichero real generado para 3.7 se ha pasado por el parser de la release:

```text
240 partidos reconocidos
0 errores
30 jornadas
16 equipos
```

La Jornada 8 utiliza simplemente:

```text
01/11/2026
```

como fecha federativa orientativa, por lo que ya no existe ningún caso especial `31/10-01/11` que deba interpretar el parser.

## Compilación, migraciones y consistencia

- `python -m compileall`: OK
- `pytest -q`: OK · 49 tests
- `python scripts/check_release_consistency.py`: OK
- Alembic base vacía → `0006`: OK
- Alembic `0005` → `0006`: OK
- No existe migración 3.7 porque no cambia el esquema.
