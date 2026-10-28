# No Name · Área Técnica 4.5.1.1 — revisión de compatibilidad del esquema real

**Base única:** paquete completo 4.5.1. **Alembic head:** `0017_lowlight_compact_4_5_1` (sin nueva migración). No se restablecen ni borran tablas o información deportiva.

## Hallazgo contrastado con el archivo remitido el 28/10/2026

El esquema exportado de `public` tiene **43 tablas y 461 columnas**. La estructura requerida por 4.5.1.1 tiene **44 tablas y 488 columnas**. La comparación exacta de nombres de columnas indica:

| Tabla | Columnas que faltaban en el listado |
|---|---|
| `users` | `participation_profile` |
| `team_rosters` | `usual_position` |
| `player_evaluations` | `highlight_rank`, `attention_signal`, `lowlight_rank` |
| `match_opinion_players` | `highlight_rank`, `attention_signal` |
| `player_observation_requests` | `origin_player_evaluation_id`, `origin_neutral_signal_id`, `origin_unidentified_signal_id` |
| `unidentified_player_signals` | **Tabla completa, 17 columnas** |

**No hay diferencias adicionales en el listado recibido.** Estas 27 columnas corresponden a la migración aditiva `0016_partial_reading_4_5` (26 columnas) y `0017_lowlight_compact_4_5_1` (1 columna). **La coincidencia estructural no prueba la revisión Alembic almacenada**: el archivo solo contiene el nombre y tipo de `alembic_version.version_num`, no su contenido.

## Qué significa el mensaje de los logs

El error PostgreSQL `42P01`, `relation "supabase_migrations.schema_migrations" does not exist`, se refiere a una relación usada para migraciones de Supabase (no al esquema de la aplicación). **No indica por sí solo que las migraciones Alembic de No Name hayan fallado**, ni autoriza a crear a mano ese esquema, ejecutar `supabase db reset` ni usar operaciones destructivas. El historial de nuestra aplicación está en **`public.alembic_version`**.

## Procedimiento para producción, sin asumir que se ha probado aquí

1. Obtener un respaldo **restaurable** con `pg_dump` de PostgreSQL y copia de los ficheros del Storage. Verificar que pueden recuperarse en un entorno aislado.
2. Ejecutar en el **Supabase SQL Editor** las consultas de `docs/CONSULTA_SEGURA_SUPABASE_4511.sql`. Leer el valor real de `public.alembic_version.version_num` y comprobar columnas. Estas consultas no escriben datos.
3. Si la revisión es `0015_observation_requests_4_4_3` y el esquema coincide con el archivo recibido, la cadena prevista es **0015 → 0016 → 0017**. Con respaldo verificado, desplegar la release íntegra y usar `RUN_MIGRATIONS = true`; el arranque puede aplicar las migraciones. No copiar solo `app.py` o una vista.
4. Si la revisión ya es `0017_lowlight_compact_4_5_1` pero faltan columnas, **no ejecutar `alembic stamp` a ciegas**. Hay inconsistencia física y se debe investigar antes de permitir acceso deportivo. Igual para revisiones diferentes/no reconocidas.
5. Reiniciar desde *Streamlit Cloud → Manage app → Reboot* y comprobar Inicio, Gestión de usuarios, ficha de C.D. Noname y de un rival, catálogo compacto de Jugadores y las tres modalidades de Informe. Comprobar especialmente que no se dupliquen evaluaciones ni cambien autores.
6. Confirmar después que `public.alembic_version` es `0017_lowlight_compact_4_5_1`, que hay 44 tablas/488 campos (si no hay ampliaciones ajenas) y que ya se pueden abrir las pantallas con permisos adecuados.

**No ejecutar SQL que cree manualmente `supabase_migrations.schema_migrations`.** Si ese error persiste de forma independiente, revisar origen de los logs, el servicio de Supabase que consulta dicha relación y su estado con soporte oficial. No inferir que proviene del código de No Name.

## Diagnóstico fuera de la aplicación

```bash
python scripts/diagnosticar_esquema_4511.py --export docs/ESQUEMA_PUBLIC_RECIBIDO_2026_10_28.txt
```

Devuelve `matches_4441_public_shape=true` y diferencias físicas esperadas. El comando puede salir con código 2 porque **el archivo previo no cumple el contrato de 4.5.1.1**; no es un fallo del script.

Con conexión PostgreSQL configurada en el entorno y sus dependencias instaladas, `python scripts/diagnosticar_esquema_4511.py --live` realiza consultas **solo lectura**, muestra las revisiones Alembic y omite la contraseña. **No llama a `init_db()`** ni aplica migraciones. No pegues credenciales en capturas o mensajes.

## Cambios respecto a 4.5.1

- Validación exacta de esquema público (43/461 → 44/488) a partir del documento real remitido.
- Prueba de upgrade desde un **volcado sintético creado por el código 4.4.4.1 original**, con datos ficticios ya almacenados. Se conserva el informe y su nota tras el upgrade hasta 0017.
- Utilidad de diagnóstico sin escritura y consultas SQL seguras para inspeccionar Alembic.
- Un fallo de Alembic en modo demo ya no queda disimulado por `metadata.create_all()` posterior.
- Mensajes de arranque y comprobación de release actualizados a 4.5.1.1 y a 0017.
- Se mantienen íntegros los cambios de experiencia de usuario, el catálogo compacto y el esquema de 4.5.1; **no se añade 0018**.
