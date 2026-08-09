# Despliegue seguro: Streamlit + Supabase

## 1. Crear el proyecto

1. Crea un proyecto en Supabase.
2. Guarda la contraseña de PostgreSQL.
3. En **Connect**, copia una URL PostgreSQL compatible con conexiones desde Streamlit.
4. Para producción, utiliza un usuario de base de datos con los permisos mínimos necesarios.

## 2. Configurar Secrets

En local, copia `.streamlit/secrets.example.toml` como `.streamlit/secrets.toml`. En Streamlit Community Cloud, pega las mismas variables en **Settings > Secrets**.

```toml
DATABASE_URL = "postgresql://..."
DEMO_MODE = false
RUN_MIGRATIONS = true
REQUIRE_REPORT_APPROVAL = true

BOOTSTRAP_ADMIN_NAME = "Administrador"
BOOTSTRAP_ADMIN_EMAIL = "admin@club.com"
BOOTSTRAP_ADMIN_PASSWORD = "UNA-CONTRASENA-FUERTE-Y-UNICA"

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15
```

Para PDF persistentes:

```toml
SUPABASE_URL = "https://PROJECT_REF.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "SERVICE_ROLE_KEY"
SUPABASE_BUCKET = "postmatch-reports"
```

No subas `secrets.toml` al repositorio. No uses la clave `service_role` en código cliente ni la compartas con usuarios.

## 3. Preparar la base

```bash
pip install -r requirements.txt
alembic upgrade head
```

El arranque también ejecuta la migración cuando `RUN_MIGRATIONS = true`.

## 4. Desplegar

1. Sube el proyecto a un repositorio privado.
2. Crea una app en Streamlit Community Cloud con `app.py`.
3. Añade los Secrets.
4. Despliega.
5. Entra con el administrador inicial y cambia su contraseña.
6. Crea una segunda cuenta administrativa de emergencia y guárdala de forma segura.

## 5. Verificación obligatoria

- `DEMO_MODE = false`.
- La contraseña inicial no coincide con ninguna contraseña de ejemplo.
- Creación y edición de un partido.
- Asignación de un informador.
- Guardado y recuperación de un borrador.
- Entrega, aprobación y presencia en el ranking.
- Generación de PDF ejecutivo y completo.
- Estado `stored_remote` en **Administración > Documentos**.
- Descarga de un backup técnico.
- Prueba de restauración en un entorno separado.

## 6. Actualizaciones

Antes de desplegar una nueva versión:

1. Descarga un backup técnico.
2. Prueba `alembic upgrade head` sobre una copia.
3. Ejecuta `pytest -q`.
4. Despliega.
5. Comprueba el archivo de documentos y las analíticas.
