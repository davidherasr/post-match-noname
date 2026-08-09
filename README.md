# No Name PostMatch 3.0

Aplicación interna de No Name para convertir cada partido terminado en dos cosas a la vez: memoria de rendimiento del propio equipo y base acumulada de scouting de rivales. La edición 3.0 mantiene la arquitectura robusta de PostMatch Scout 2.x, pero cambia por completo el flujo visible para reducir pasos y carga administrativa.

## Idea de producto

El flujo normal ya no es `temporada → competición → equipo → plantilla → partido → alineaciones → informe`. Para el usuario es simplemente:

**Nuevo postpartido → partido → No Name → rival → publicar → valorar jugadores.**

La base de datos, plantillas y relaciones siguen existiendo, pero trabajan por detrás. La sección **Base de datos** queda como mantenimiento y corrección, no como paso previo obligatorio.

## Qué cambia en 3.0

### Administración

- Dashboard propio para administrador, distinto al del informador y dirección deportiva.

- Acción principal **Nuevo postpartido**.
- Flujo continuo en una sola página.
- Configuración inicial de No Name desde el propio flujo si aún no existe equipo propio.
- Creación rápida de temporada activa desde el flujo.
- Competición nueva sin abandonar el postpartido.
- Rival nuevo sin abandonar el postpartido.
- Plantilla de No Name reutilizable durante toda la temporada.
- Alta de jugadores propios desde la propia alineación.
- Pegado masivo de jugadores propios con `Nombre;POS;Dorsal`.
- Copia de la última alineación de No Name.
- El rival no necesita tener una plantilla creada previamente.
- Al escribir un rival, sus jugadores se crean/resuelven y se vinculan a su plantilla como consecuencia natural del partido.
- Recuperación de la última alineación conocida del rival.
- Pegado rápido de alineación rival.
- Importación CSV/XLSX opcional.
- Publicación y asignación de informadores al final del mismo flujo.

### Informador

Cada rol tiene su propio menú. El informador ve únicamente:

- Inicio.
- Valorar partido.
- Mis informes.
- Jugadores.

La valoración de jugadores propios y rivales usa exactamente la misma interfaz simple:

- jugador, dorsal, posición, minutos y titularidad: **solo lectura**;
- slider 0–10 con precisión de 0,1;
- botones rápidos 5 / 6 / 7 / 8 / 9;
- observación opcional;
- check **Destacado**;
- check **Incluir en PDF**.

Automatismos:

- 0 = sin valorar;
- nota > 0 activa PDF por defecto;
- nota ≥ 8 marca destacado por defecto;
- ambos checks pueden cambiarse manualmente;
- no es obligatorio valorar a todos los participantes;
- para entregar basta con al menos una valoración rival válida.

### Jugadores

La pantalla separa dos usos:

- **No Name**: histórico interno de rendimiento, últimas notas, evolución y comentarios.
- **Rivales**: historial de scouting creado automáticamente a partir de los postpartidos aprobados.

Las valoraciones propias nunca contaminan el ranking rival y las valoraciones rivales nunca contaminan el histórico interno.

### Dirección deportiva

La pantalla se orienta primero a decisiones y después a análisis:

- informes pendientes de revisar;
- últimas notas rivales ≥ 8;
- jugadores observados varias veces;
- seguimientos activos;
- aprobación/devolución de informes;
- historial y rankings con filtros avanzados;
- consenso entre informadores;
- comparación y exportaciones.

### PDF

El PDF se acorta y prioriza lo seleccionado por el informador:

- contexto del partido;
- sistemas sobre campo cuando existen;
- resumen de nuestro equipo;
- resumen rival;
- solo jugadores con **Incluir en PDF** y nota válida;
- fichas individuales para perfiles seleccionados/destacados;
- versión ejecutiva y completa;
- snapshots y versiones históricas inmutables.

## Persistencia y Supabase

No Name PostMatch 3.0 mantiene PostgreSQL/Supabase como fuente de verdad. El ZIP **no contiene equipos, jugadores, temporadas, competiciones, partidos, evaluaciones ni informes de muestra**. Solo se crea el administrador inicial definido en Secrets cuando la tabla de usuarios está vacía.

La actualización desde 2.0/2.1/2.1.1 usa Alembic. La revisión `0002_noname_3_0` es no destructiva y no elimina ni transforma datos deportivos existentes.

## Despliegue Streamlit Community Cloud

Si subes el contenido del ZIP directamente a la raíz de GitHub:

```text
Main file path: app.py
```

Secrets mínimos:

```toml
DATABASE_URL = "postgresql://..."
DEMO_MODE = false
RUN_MIGRATIONS = true
REQUIRE_REPORT_APPROVAL = true

BOOTSTRAP_ADMIN_NAME = "Administrador"
BOOTSTRAP_ADMIN_EMAIL = "tu-correo@dominio.com"
BOOTSTRAP_ADMIN_PASSWORD = "CONTRASEÑA-FUERTE"

LOGIN_MAX_ATTEMPTS = 10
LOGIN_LOCK_MINUTES = 15
```

Storage PDF opcional:

```toml
SUPABASE_URL = "https://PROJECT_REF.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "CLAVE-BACKEND"
SUPABASE_BUCKET = "postmatch-reports"
```

## Primera utilización con una base vacía

1. Entra con el administrador de Secrets.
2. Cambia la contraseña inicial si la aplicación lo solicita.
3. Pulsa **Nuevo postpartido**.
4. Configura No Name una sola vez.
5. Crea la temporada activa si aún no existe.
6. Crea el partido, las dos alineaciones y publícalo sin salir de esa pantalla.
7. Crea los usuarios informadores desde Administración cuando los necesites.

## Actualización desde 2.1.1

1. Haz backup técnico desde la versión actual.
2. Sustituye **todo** el contenido del repositorio por esta versión, no solo `app.py`.
3. Conserva los mismos Secrets y el mismo `DATABASE_URL` de Supabase.
4. Haz Reboot en Streamlit Cloud.
5. Con `RUN_MIGRATIONS = true`, Alembic avanza hasta `0002_noname_3_0` sin borrar datos.

## Estructura

```text
app.py
pages/
  dashboard.py
  postmatch.py
  reports.py
  players.py
  director.py
  matches.py
  catalog.py
  admin.py
repositories/
services/
models/
core/
alembic/
tests/
scripts/
```

## Validación

La release se valida con:

```bash
python scripts/check_release_consistency.py
pytest -q
alembic upgrade head
```

El entorno en el que se construyó esta release no incluye el paquete Streamlit para levantar el navegador, por lo que la aceptación visual final debe hacerse en Streamlit Cloud. La lógica de repositorio, flujos, PDF, migraciones y tests sí se ejecuta fuera de la interfaz.
