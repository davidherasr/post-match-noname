# Validación 4.1.2

Objetivo: eliminar el concepto visible de rol principal y mantener permisos acumulativos.

Comprobaciones de release:
- `Rol principal` no aparece como selector ni columna en Administración.
- Alta/edición requieren al menos un rol.
- El rol legado de compatibilidad se calcula automáticamente.
- No hay migración nueva; head esperado `0011_user_lifecycle_4_1_1`.
