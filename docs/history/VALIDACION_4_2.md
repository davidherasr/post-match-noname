# Validación 4.2.0

Checklist de release:

- `VERSION = 4.2.0`.
- `APP_VERSION = 4.2.0`.
- `REPORTS_PAGE_API_VERSION = 4.2.0`.
- Alembic head: `0012_sporting_reading_4_2`.
- Navegación: Inicio / Jornada / Jugadores / Dirección Deportiva / Administración según permisos.
- Sin directorio `pages/`.
- Sin SQLite ni `secrets.toml` reales en el ZIP.
- Jornada separa partido No Name de neutral.
- No existe asignación activa de trabajos a Scout.
- Admin expone permiso de seguimiento individual, no rol Scout.
- Dirección Deportiva muestra lectura deportiva y pesos del staff.
- Jugadores propios no se pueden abrir como seguimiento de mercado.
- Contraseñas: cualquier valor no vacío.
- `pytest`: 101 passed.
- `compileall`: OK.
- `check_release_consistency.py`: OK.
- Migración desde base SQLite vacía hasta `0012`: OK.
- Upgrade específico `0011 -> 0012` con usuario Scout legado: OK; se conserva como Informador y recibe `can_track_players = true`.
