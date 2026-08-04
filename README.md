# PostMatch Scout 2.1

Aplicación interna en **Python + Streamlit** para registrar valoraciones postpartido de jugadores, generar PDF y construir un histórico útil para dirección deportiva.

La versión 2.1 cambia especialmente la experiencia del informador: cada rol dispone de su propio menú y panel, y la valoración de jugadores se realiza mediante fichas individuales muy simples, sin tablas editables ni campos generales obligatorios.

## Cambios principales de la versión 2.1

### Menús y paneles por rol

**Informador**

- Mi panel.
- Hacer informe.
- Mis informes.
- Jugadores.

Su panel muestra únicamente asignaciones, informes en curso, entregados y aprobados.

**Dirección deportiva**

- Panel de dirección.
- Revisar y analizar.
- Informes.
- Jugadores.

El panel prioriza informes pendientes de revisión, jugadores mejor valorados y seguimientos activos.

**Administrador**

- Panel de administración.
- Partidos.
- Base de datos.
- Informes.
- Jugadores.
- Dirección deportiva.
- Administración.

El panel ofrece accesos directos a partidos, usuarios, datos y control general.

### Informe simplificado

Ya no es obligatorio completar:

- impresión general del rival;
- nivel mostrado por el rival;
- conclusiones colectivas;
- decisión de seguimiento;
- confianza;
- notas técnicas, tácticas o físicas.

Para entregar un informe basta con valorar al menos a un jugador rival.

Cada jugador aparece en una ficha individual con:

- nombre y dorsal;
- posición predeterminada y no editable;
- minutos disputados predeterminados y no editables;
- condición de titular o suplente;
- barra de valoración de 0 a 10;
- observación opcional;
- check de destacado;
- check de inclusión en PDF.

Reglas automáticas:

- `0` significa **sin valorar**;
- cualquier nota mayor que `0` genera una evaluación válida;
- el check **Incluir en PDF** aparece marcado por defecto;
- una nota de `8,0` o superior marca automáticamente al jugador como destacado;
- ambos checks pueden modificarse manualmente;
- el MVP del informe se deriva automáticamente del destacado con mejor nota.

El bloque de nuestro equipo utiliza exactamente el mismo funcionamiento y queda separado de las analíticas de jugadores rivales.

## Funcionalidades existentes

- PostgreSQL remoto mediante SQLAlchemy.
- Compatibilidad con Supabase PostgreSQL y Supabase Storage.
- Roles de administrador, informador y dirección deportiva.
- Asignación de partidos y fechas límite.
- Informes en borrador, entregados, devueltos y aprobados.
- Autoguardado por ficha.
- Versiones inmutables del informe.
- PDF ejecutivo y completo.
- Histórico de jugadores.
- Rankings solo con informes aprobados y jugadores rivales.
- Seguimientos y consolidaciones.
- Importación CSV/XLSX.
- Exportación analítica y backup técnico.
- Auditoría y control de sesiones.
- Migraciones mediante Alembic.

## Estructura

```text
app.py
pages/
  dashboard.py
  reports.py
  matches.py
  players.py
  director.py
  catalog.py
  admin.py
repositories/
services/
models/
core/
alembic/
tests/
```

## Main file path

Si el repositorio contiene directamente `app.py`:

```text
app.py
```

Si has subido la carpeta completa al repositorio:

```text
postmatch_scout_2_1/app.py
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

Sin `DATABASE_URL`, la aplicación arranca en modo demostración con SQLite.

```text
Administrador: admin@postmatch.local / DemoAdmin2026!
Informador: informador@postmatch.local / DemoReporter2026!
```

No utilices el modo demostración con información real del club.

## Producción con Supabase

Variables mínimas en Streamlit Secrets:

```toml
DATABASE_URL = "postgresql://..."
DEMO_MODE = false
RUN_MIGRATIONS = true

BOOTSTRAP_ADMIN_NAME = "Administrador"
BOOTSTRAP_ADMIN_EMAIL = "admin@club.com"
BOOTSTRAP_ADMIN_PASSWORD = "UNA-CONTRASENA-FUERTE-Y-UNICA"
```

Storage privado opcional:

```toml
SUPABASE_URL = "https://PROJECT_REF.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "SERVICE_ROLE_KEY"
SUPABASE_BUCKET = "postmatch-reports"
```

## Flujo recomendado

### Administrador

1. Crea temporada, competición y equipos.
2. Marca el equipo propio.
3. Carga plantillas.
4. Crea el partido y las alineaciones.
5. Asigna informadores.
6. Publica el partido.

### Informador

1. Entra en **Mi panel**.
2. Pulsa **Empezar** o **Continuar**.
3. Mueve la barra de cada jugador que haya podido valorar.
4. Añade observaciones solo cuando aporten información.
5. Revisa los checks de destacado y PDF.
6. Valora opcionalmente a jugadores propios.
7. Genera una vista previa y entrega.

### Dirección deportiva

1. Revisa informes entregados.
2. Aprueba o devuelve.
3. Consulta rankings e históricos.
4. Consolida opiniones.
5. Gestiona seguimientos.

## Importación

La plantilla incluida contiene:

- `plantillas`;
- `alineaciones`;
- `instrucciones`.

Archivo:

```text
templates/plantilla_importacion_postmatch_scout_2_1.xlsx
```

## Comprobaciones

```bash
python -m compileall .
pytest -q
python scripts/smoke_test.py
```

PDF de muestra:

```text
sample/informe_demo_postmatch_scout_2_1_ejecutivo.pdf
sample/informe_demo_postmatch_scout_2_1_completo.pdf
```

## Actualización desde 2.0

La versión 2.1 no añade tablas ni modifica el esquema de base de datos. Puede utilizar la misma base de datos de la versión 2.0. Antes de actualizar en producción, descarga un backup técnico.

## Limitaciones conocidas

- Streamlit está orientado a herramientas internas, no a una plataforma pública masiva.
- La autenticación es propia de la aplicación y no utiliza Supabase Auth.
- El almacenamiento local de Streamlit Community Cloud es efímero; configura Supabase Storage para conservar PDF.
- La interfaz debe probarse finalmente en el navegador y dispositivos reales del cuerpo técnico.
