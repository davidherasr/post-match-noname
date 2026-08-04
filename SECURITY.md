# Seguridad operativa

- Mantén el repositorio privado.
- Usa `DEMO_MODE = false` en cualquier despliegue real.
- Guarda PostgreSQL y Supabase únicamente en Secrets.
- Rota la clave `service_role` si existe sospecha de exposición.
- No envíes backups técnicos por correo o mensajería sin cifrar.
- Desactiva inmediatamente las cuentas que abandonen el cuerpo técnico.
- Revisa periódicamente los accesos fallidos y el registro de auditoría.
- Conserva al menos una copia técnica reciente fuera del proveedor de despliegue.
- Prueba la restauración antes de considerar que existe una estrategia de backup.

La aplicación utiliza autorización en repositorio, bloqueo por intentos, sesiones revocables y versiones inmutables, pero sigue siendo una herramienta interna: la seguridad también depende del control de dispositivos, contraseñas y accesos al proyecto Supabase.
