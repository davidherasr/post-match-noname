# PostMatch Scout 2.0

Aplicación interna en **Python + Streamlit** para transformar cada partido en observaciones estructuradas de jugadores rivales, informes PDF inmutables y decisiones de seguimiento para dirección deportiva.

La versión 2.0 no es una ampliación estética de la 1.1: corrige la fiabilidad analítica, endurece permisos y seguridad, incorpora asignaciones y aprobación, crea versiones históricas reales y añade un flujo operativo completo.

## Qué incluye

### Operativa del cuerpo técnico

- Usuarios con roles de administrador, informador y dirección deportiva.
- Bloqueo temporal tras intentos de acceso fallidos y revocación de sesiones al modificar una cuenta.
- Asignación de partidos a informadores, fecha límite y seguimiento de entregas.
- Informes en estados: borrador, entregado, devuelto y aprobado.
- Autoguardado por bloques con detección de cambios concurrentes.
- Evaluación rival simplificada: estado, nota general, decisión, observación y destacado.
- Análisis avanzado opcional: técnica, táctica, física, confianza, fortalezas y nota ampliada.
- Valoraciones del equipo propio almacenadas en un ámbito separado y excluidas del scouting rival.
- MVP rival único y varios jugadores destacados, sin mezclar ambos conceptos.

### Dirección deportiva

- Ranking calculado exclusivamente con jugadores rivales de informes aprobados/finales.
- Exclusión automática de borradores, evaluaciones propias y observaciones sin nota válida.
- Filtros por temporada, competición, equipo, informador, posición, confianza, fecha y minutos.
- Dispersión de notas y número de informadores para interpretar el grado de consenso.
- Historial de jugador con posición y minutos observados; los datos ausentes aparecen como «Sin muestra», nunca como cero.
- Revisión, devolución y aprobación de informes.
- Consolidación de varios informadores por partido y decisión final de dirección deportiva.
- Seguimientos con responsable, prioridad, próxima revisión, partido objetivo, cierre e historial.

### Administración y calidad de datos

- Alta, edición y archivo de temporadas, competiciones, equipos, jugadores y partidos.
- Escudos de equipos y fotografías opcionales de jugadores.
- Plantillas por temporada con altas, bajas y dorsales.
- Alias, detección de posibles duplicados y fusión trazable de jugadores.
- Alineaciones reconciliadas con las evaluaciones en borrador.
- Importación CSV/XLSX con selector de hoja, detección de separador/codificación, vista previa, validaciones y transacciones parciales seguras.
- Asignaciones de informes y progreso por partido.
- Auditoría con valores anteriores y posteriores en operaciones relevantes.

### Documentos y datos

- PDF ejecutivo y PDF completo.
- Portada editorial, onces sobre el campo, alineaciones, resumen validado y fichas individuales.
- Versiones inmutables: cada entrega conserva un snapshot del informe, evaluaciones, participantes y configuración visual.
- Archivo de documentos con checksum, tamaño, ruta local/remota y estado de almacenamiento visible.
- Subida opcional a Supabase Storage y reintento de fallos.
- Exportación analítica a Excel.
- Backup técnico completo en ZIP y script de restauración.
- Migraciones de esquema con Alembic.

## Arquitectura

```text
Streamlit
  ├── pages/                interfaz por área funcional
  ├── repositories/         autorización, consultas y transacciones
  ├── services/             PDF, importación, exportación y almacenamiento
  ├── models/               modelo relacional SQLAlchemy
  ├── alembic/              migraciones de base de datos
  ├── tests/                pruebas automatizadas
  └── scripts/              administración, muestra y restauración

PostgreSQL / Supabase
  ├── datos operativos
  ├── versiones inmutables
  ├── auditoría
  └── metadatos de documentos

Supabase Storage (opcional)
  └── PDF privados
```

## Instalación local

Recomendado: Python 3.11 o 3.12.

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Sin `DATABASE_URL`, la aplicación arranca en modo demostración con SQLite y datos ficticios.

```text
Administrador: admin@postmatch.local / DemoAdmin2026!
Informador: informador@postmatch.local / DemoReporter2026!
```

No utilices el modo demo con información real del club.

## Producción con Supabase PostgreSQL

Copia `.streamlit/secrets.example.toml` como `.streamlit/secrets.toml` o pega sus variables en Streamlit Community Cloud.

Variables mínimas:

```toml
DATABASE_URL = "postgresql://..."
DEMO_MODE = false
RUN_MIGRATIONS = true

BOOTSTRAP_ADMIN_NAME = "Administrador"
BOOTSTRAP_ADMIN_EMAIL = "admin@club.com"
BOOTSTRAP_ADMIN_PASSWORD = "UNA-CONTRASENA-FUERTE-Y-UNICA"
```

La aplicación no permite arrancar en producción con la contraseña de demostración. El administrador inicial deberá cambiar su contraseña en el primer acceso.

Storage privado opcional:

```toml
SUPABASE_URL = "https://PROJECT_REF.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "SERVICE_ROLE_KEY"
SUPABASE_BUCKET = "postmatch-reports"
```

La clave `service_role` solo debe existir en Secrets. La aplicación guarda `bucket` y `path`; las URL firmadas se generan bajo demanda y no se persisten.

## Migraciones

En el arranque, si `RUN_MIGRATIONS = true`, se ejecuta:

```bash
alembic upgrade head
```

Comandos manuales:

```bash
alembic current
alembic upgrade head
```

Antes de aplicar una migración en producción, descarga un backup técnico desde **Administración > Backup**.

## Flujo recomendado

### Administrador

1. Crea temporada, competición y equipos.
2. Marca el equipo propio.
3. Carga plantillas manualmente o mediante CSV/XLSX.
4. Crea el partido y sus alineaciones.
5. Asigna informadores y fecha límite.
6. Publica el partido.
7. Supervisa documentos, auditoría y copias técnicas.

### Informador

1. Abre un partido asignado.
2. Escribe una impresión general breve.
3. Completa la tabla rápida rival.
4. Abre el análisis avanzado solo para perfiles relevantes.
5. Revisa el PDF ejecutivo o completo.
6. Entrega una versión inmutable.
7. Corrige una nueva versión si dirección deportiva devuelve el informe.

### Dirección deportiva

1. Revisa y aprueba o devuelve informes.
2. Consulta rankings validados y dispersión de criterio.
3. Consolida las opiniones del mismo partido.
4. Abre seguimientos con responsable y próxima acción.
5. Exporta la información analítica cuando sea necesario.

## Importación

La plantilla contiene:

- `plantillas`: equipo, temporada, dorsal, jugador, posición, fecha de nacimiento y nacionalidad.
- `alineaciones`: partido, equipo, dorsal, jugador, posición, titular, minutos y capitán.
- `instrucciones`: reglas y ejemplos.

La interfaz permite elegir la hoja correcta. Los CSV admiten coma o punto y coma y varias codificaciones habituales. El formato `.xls` antiguo no se acepta: conviértelo a `.xlsx` o CSV.

## Backups y restauración

La exportación analítica y el backup técnico son distintos:

- **Excel analítico:** pensado para lectura y análisis.
- **ZIP técnico:** incluye todas las tablas y relaciones, también hashes de contraseña; es confidencial.

Restauración sobre una base vacía:

```bash
python scripts/restore_backup.py ruta/al/backup.zip
```

Para reemplazar una base existente, crea primero una copia y utiliza:

```bash
python scripts/restore_backup.py ruta/al/backup.zip --replace
```

## Comprobaciones

```bash
python -m compileall .
pytest -q
python scripts/generate_sample.py
```

PDF de muestra:

```text
sample/informe_demo_postmatch_scout_2_0_ejecutivo.pdf
sample/informe_demo_postmatch_scout_2_0_completo.pdf
```

## Limitaciones conocidas

- Streamlit es idóneo para una herramienta interna de un cuerpo técnico, no para una plataforma pública masiva.
- La autenticación es propia de la aplicación sobre PostgreSQL; no utiliza Supabase Auth.
- El almacenamiento local en Streamlit Community Cloud es efímero: para archivo permanente configura Supabase Storage.
- Las migraciones futuras deben probarse primero sobre una copia de la base de datos.
