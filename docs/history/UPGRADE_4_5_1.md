# No Name · Área Técnica 4.5.1

## Motivo

Revisión de producción de la 4.5 tras detectar errores en Gestión de usuarios y al abrir fichas de equipo, así como un exceso de altura y campos en Jugadores e Informador.

## Cambios entregados

- Administración: consulta directamente el catálogo de perfiles desde `repositories.users`, sin depender de su reexportación en `repositories.scouting`. En el editor se tolera un perfil histórico desconocido y se selecciona `full` como referencia segura.
- Equipos: la vista de plantilla sigue disponible cuando falla **la importación de la capa auxiliar** de atención DD. Se muestra un aviso específico, en lugar de impedir abrir el equipo. La avería de fondo debe corregirse desplegando una release completa y coherente.
- Jugadores: tabla de una fila por futbolista, 25/50 filas por página, selección de fila para abrir ficha, buscador, filtros de equipo/posición/ámbito/estado/tipo de evidencia y orden ascendente/descendente por nombre, posición, nota media, partidos o fecha. El filtrado y el orden se ejecutan en SQL antes de paginar.
- Informador, Inicio: solo para el rol Informador sin otros roles, partido actual como primera acción y encuentros anteriores compactos en un selector. Las peticiones DD siguen disponibles.
- Informador, editor: tres modalidades seleccionables: básico No Name; básico de ambos; completo. En básicos las notas de los equipos son opcionales; tres más destacados y tres menos destacados por equipo también son opcionales, sin nota individual obligatoria. Los datos desconocidos siguen vacíos.
- Señal de identidad pendiente: se mantiene el campograma posicional fuera de `st.form`, de modo que sus botones no choquen con la restricción de formularios de Streamlit.
- «Menos destacados»: nuevo ranking `lowlight_rank` nullable (1–3), independiente de `highlight_rank` y de la nota. Su significado es **una apreciación comparativa dentro de ese partido**; no genera automáticamente una decisión de DD. Se incorpora a las instantáneas de informe, lectura de Player 360 y tablas de señales de PDF.

## Migración 0017 (aditiva)

`0017_lowlight_compact_4_5_1` añade `player_evaluations.lowlight_rank INTEGER NULL`. No borra ni modifica notas anteriores. Los informes anteriores quedan con `NULL` y conservan su significado original. La revisión anterior era `0016_partial_reading_4_5`.

No se modifica la base Supabase productiva mediante la preparación de este ZIP. Hacer `pg_dump`/backup real antes de desplegar o migrar, y probar en una copia PostgreSQL si se dispone de ella.

## Despliegue

Sustituir **la release completa**, incluidos `models/`, `repositories/`, `views/`, `core/`, `alembic/`, `scripts/` y `VERSION`. No subir únicamente `views/` ni cambiar solo el fichero principal: una mezcla 4.5.1/4.5/4.4 explica ImportError/AttributeError en rutas diferidas.

Tras instalar `requirements.txt`, comprobar:

```bash
python -m compileall -q .
python scripts/check_release_consistency.py
python scripts/check_ui_contract_451.py
python -m pytest -q
```

Probar en Streamlit Cloud, con usuarios de roles informador y administrador: abrir Listado/Añadir/Editar, una ficha de equipo, el catálogo, una lectura básica No Name, una básica de ambos y la ficha PDF. También verificar la versión Alembic 0017, sin ejecutar reseteos de base.

La comprobación local automatizada no sustituye las pruebas visuales y funcionales en Cloud.
