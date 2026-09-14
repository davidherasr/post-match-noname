# Validación 4.1.1

Release validada sobre el paquete fuente y el ZIP final.

- `compileall`: OK.
- Suite automatizada: 96 tests pasados.
- Consistencia interna: OK.
- Alembic fresh → `0011_user_lifecycle_4_1_1`: OK.
- Alembic `0010_core_workspace_schema_repair_4_0_4 → 0011_user_lifecycle_4_1_1`: OK.
- `users.deleted_at` presente tras migración: OK.
- Contraseñas simples no vacías (`1`, `1234`, etc.): OK.
- Eliminación/restauración lógica de usuarios: OK.
- Sin `pages/`, bases SQLite ni Secrets reales en el paquete final.
