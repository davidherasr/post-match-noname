# No Name PostMatch 3.0 · Supabase + Streamlit Cloud

## Si ya tienes Supabase conectado en 2.x

No crees otra base de datos. Conserva el mismo proyecto y los mismos Secrets.

1. Descarga un backup técnico desde la aplicación actual.
2. Sustituye el repositorio completo por No Name PostMatch 3.0.
3. Mantén `DATABASE_URL` apuntando al mismo Session Pooler de Supabase.
4. Mantén `RUN_MIGRATIONS = true`.
5. Haz Reboot en Streamlit Community Cloud.
6. Alembic avanzará a `0002_noname_3_0` sin borrar datos.

## Secrets

```toml
DATABASE_URL = "postgresql://postgres.PROJECT_REF:PASSWORD@HOST.pooler.supabase.com:5432/postgres"
DEMO_MODE = false
RUN_MIGRATIONS = true
REQUIRE_REPORT_APPROVAL = true

BOOTSTRAP_ADMIN_NAME = "Administrador"
BOOTSTRAP_ADMIN_EMAIL = "tu-correo@dominio.com"
BOOTSTRAP_ADMIN_PASSWORD = "CONTRASEÑA-FUERTE"

LOGIN_MAX_ATTEMPTS = 10
LOGIN_LOCK_MINUTES = 15
```

Opcional para PDF persistente:

```toml
SUPABASE_URL = "https://PROJECT_REF.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "CLAVE-BACKEND"
SUPABASE_BUCKET = "postmatch-reports"
```

## Main file path

Si el contenido del ZIP está directamente en la raíz del repositorio:

```text
app.py
```

## Primer arranque

- No se insertan equipos, jugadores ni partidos.
- Si `users` está vacío, se crea únicamente el administrador definido en Secrets.
- Los ajustes visuales mínimos se crean si faltan.
- El club propio y la temporada se configuran desde **Nuevo postpartido**.
