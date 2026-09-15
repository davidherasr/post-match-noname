# Validación 4.2.1

Checklist de release:

- `VERSION = 4.2.1`.
- `APP_VERSION = 4.2.1`.
- `REPORTS_PAGE_API_VERSION = 4.2.1`.
- Alembic head: `0012_sporting_reading_4_2` (sin migración nueva).
- Dirección Deportiva dispone de lectura transversal de jugadores, equipos, discrepancias y partidos recientes.
- Las señales de jugador agregan partidos distintos, menciones, staff, ponderación y tendencia.
- Las discrepancias se presentan como consenso legible y enlazan al partido de origen.
- Inicio enlaza directamente con DD → Jugadores señalados.
- `can_report` exige rol Informador; Admin y DD puros no pueden escribir valoraciones/postpartidos.
- `can_track_players` continúa siendo permiso independiente.
- Partidos de No Name y neutrales siguen separados; No Name no puede iniciar seguimiento de mercado.
- Vistas obsoletas `scout.py`, `director.py`, `scouted.py`, `model.py` y `dashboard.py` ausentes.
- Workspaces activos sin `ScoutMission`, `ScoutMissionTarget`, `my_missions`, `mission_counts` ni `targets_by_mission`.
- Sin directorio `pages/`.
- Sin SQLite ni `secrets.toml` real en el ZIP.
- Contraseñas: cualquier valor no vacío.
- `pytest`: 106 passed.
- `compileall`: OK sobre el ZIP final extraído.
- `check_release_consistency.py`: OK sobre el ZIP final extraído.

- Validación del ZIP final extraído: 106 tests, consistencia y compilación OK.
- Migración desde SQLite vacía hasta `0012`: OK.
- Upgrade específico `0011_user_lifecycle_4_1_1 -> 0012_sporting_reading_4_2`: OK.
