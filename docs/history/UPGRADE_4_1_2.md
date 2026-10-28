# Upgrade 4.1.2

Parche de interfaz y coherencia de roles sobre 4.1.1.

- Sustituye el código completo por 4.1.2.
- No ejecutes SQL manual ni hay migración nueva.
- Alembic permanece en `0011_user_lifecycle_4_1_1`.
- Administración → Usuarios ya no muestra `Rol principal`; asigna únicamente `Roles y accesos`.
- Los permisos siguen siendo acumulativos e independientes.
- El campo legado `users.role` se calcula internamente por compatibilidad.
