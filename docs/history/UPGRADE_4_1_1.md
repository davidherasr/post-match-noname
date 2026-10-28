# Upgrade 4.1.1

4.1.1 simplifica por completo la gestión de usuarios.

- Las contraseñas ya no tienen requisitos de complejidad. Cualquier valor no vacío es válido, incluido `1` o `1234`.
- Cambiar la contraseña es siempre opcional. Se elimina el bloqueo por contraseña provisional y se limpian los flags antiguos de cambio obligatorio.
- Cada usuario dispone de `Mi cuenta` para cambiar la contraseña solo si quiere.
- Administración → Usuarios pasa a ser una pantalla completa de gestión: listado, alta, edición, roles, activación/desactivación, cambio de correo/contraseña, eliminación y restauración.
- Eliminar es un borrado lógico seguro: impide el acceso y oculta la cuenta, pero conserva referencias históricas en informes, scouting, asignaciones y auditoría.
- No se puede eliminar la propia cuenta durante la sesión ni el último administrador activo.

## Base de datos

Se añade la migración no destructiva `0011_user_lifecycle_4_1_1`, que incorpora `users.deleted_at` y limpia cualquier `must_change_password=true` heredado.

Mantén el mismo Supabase, `DATABASE_URL` y Secrets. Con `RUN_MIGRATIONS = true`, Streamlit aplicará automáticamente `0010 → 0011` al reiniciar.
