# No Name PostMatch 4.2.3.1 — hotfix de asignación a informadores

## Problema reproducido en la versión 4.2.3

Un administrador podía pulsar PUBLICAR POSTPARTIDO con la lista «Informadores» vacía: `core/postmatch_validation.py` emitía una advertencia, no un error, y `views/postmatch.py` solo llamaba a `assign_reporters` si había IDs. El Match quedaba `published` sin filas `report_assignments`. Inicio no ofrecía tareas porque consultaba exclusivamente asignaciones pendientes del usuario, y Jornada ocultaba «Abrir informe» porque no existía `my_assignment`. La pantalla mostraba «Informes 0/0». El siguiente partido de Inicio solo muestra encuentros futuros: no sustituye la bandeja de informes históricos pendientes.

Este diagnóstico se basa en código y en capturas del usuario; no se han leído ni modificado los registros reales de Supabase.

## Solución incorporada

1. Al publicar un nuevo postpartido se exige al menos un Informador. La validación detiene la publicación si no se selecciona nadie. Los IDs inválidos, inactivos, eliminados o sin rol Informador provocan error explícito y rollback, en vez de omitirse silenciosamente.
2. **Recuperación desde la app sin SQL** para partidos que ya se publicaron sin asignaciones: Administrador → Jornada → jornada del partido → Abrir → «Informadores asignados · gestionar postpartido» → seleccionar cuenta(s) activas con rol Informador → «Guardar asignaciones y activar tareas». No reintroduce el asistente, no duplica el Match y conserva resultado, alineaciones, participaciones e informes.
3. El Informador asignado encuentra el postpartido en **Inicio → Tus tareas → Rellenar informe**. Ese botón abre directamente el editor; desde Jornada aparece «Abrir informe». El caso sin asignación se explica en el partido y en Inicio.
4. La herramienta mantiene informes ya entregados e historial. Solo reabre asignaciones `waived` si se vuelven a seleccionar. Si un usuario asignado se ha desactivado, la app lo avisa para revisar el reparto.
5. En los partidos propios, el seguimiento profundo de rivales con permiso especial queda como sección optativa plegada, para no eclipsar el postpartido.

## Despliegue seguro

- Conservar copia verificable de Supabase/PostgreSQL, copia de documentos remotos/bucket y commit/ZIP que actualmente funciona. El botón de backup histórico de la app no es copia integral de la base.
- Desplegar el **ZIP completo 4.2.3.1**: reemplazar el árbol de código (incluidos scripts/tests/migraciones), sin sobreescribir Secrets productivos ni modificar la base manualmente.
- **Sin nueva revisión Alembic**: el head sigue `0013_data_governance_4_2_3`. Para un PostgreSQL que ya estaba operativo en 4.2.3 no hay nuevas columnas que aplicar. No utilizar `alembic stamp` ni ejecutar SQL de asignaciones.
- Verificar versión 4.2.3.1 y que entra el único administrador. Revisar permisos: la selección del informador se hace en la cuenta Admin, no desde una cuenta exclusivamente Informador.
- Abrir **J1 La Cistérniga – C.D. Noname** desde Jornada con Admin y comprobar, según estado real, que está publicado y si tiene asignaciones. Elegir explícitamente el usuario que debe informar; no se asigna automáticamente a todos los Informadores.
- Iniciar sesión como el Informador elegido: debe aparecer «Rellenar informe» en Inicio y «Abrir informe» en Jornada, y debe permitir comenzar/continuar la valoración sin crear un segundo partido.
- Una vez entregado, confirmar incorporación inmediata a las estadísticas y lectura DD, sin aprobación obligatoria.

## Límites y regresiones

- 117 pruebas automatizadas superadas, compilación Python y consistencia OK.
- Base SQLite aislada: migración fresh a 0013 y actualización 0012 → 0013 OK. No hay una migración 0014.
- Streamlit no está instalado en el entorno de comprobación; el render visual y el flujo en Cloud/Supabase real quedan pendientes de aceptación con el usuario.
- Ninguna operación de mantenimiento ni asignación se ha ejecutado sobre Supabase productivo; el administrador debe realizarla por ID en la interfaz.
