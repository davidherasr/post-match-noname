# Actualización segura · No Name · Área Técnica 4.4.3

## Código de partida y alcance

Esta release completa deriva únicamente del ZIP `NoName_Area_Tecnica_4.4.2.zip`. Conserva todos los módulos y datos históricos; añade la migración **0015_observation_requests_4_4_3** sobre **0014_unified_player_evidence_4_4_2**. No instala ni ejecuta borrados de usuarios, temporadas, partidos, clubes, jugadores, informes o seguimientos. Las herramientas de borrado que ya existían siguen requiriendo intervención explícita y confirmación reforzada.

## Antes del despliegue

1. Confirma qué commit y `VERSION` están realmente desplegados. Conserva una copia del repositorio y de la release anterior. No mezcles archivos entre ZIP; coloca el contenido íntegro de la raíz del ZIP (donde están `app.py` y `VERSION`) en el repositorio.
2. Obtén **un backup PostgreSQL completo restaurable** y una copia separada del bucket que aloja PDF y archivos. La exportación técnica en la aplicación y el ZIP de código no son un reemplazo. Comprueba la restauración en un PostgreSQL aislado y no compartas contraseñas ni claves.
3. Comprueba `alembic_version.version_num` en una conexión autorizada **de solo lectura**: la versión anterior prevista es `0014_unified_player_evidence_4_4_2`. Si difiere, detente e investiga antes de migrar. Nunca uses `alembic stamp` como sustituto de ejecutar la migración.
4. En una copia aislada del PostgreSQL existente prueba `alembic upgrade head`: debe quedar `0015_observation_requests_4_4_3`. Esta actualización crea **tres tablas nuevas** (`player_observation_requests`, `player_observation_recipients`, `player_observation_responses`) e índices; no altera ni elimina filas históricas. Las instalaciones nuevas también terminan en 0015.
5. Si las migraciones se ejecutan durante el arranque, verifica la configuración `RUN_MIGRATIONS` y programa una ventana de despliegue. Si está desactivada, migra la réplica y aplica la secuencia autorizada sobre producción antes de abrir la versión nueva. Mantén `.streamlit/secrets.toml` fuera del repositorio.
6. Despliega, reinicia la aplicación y comprueba en logs `VERSION=4.4.3`, versión Alembic 0015 y conexión real a Supabase. Si falla, conserva el traceback completo **sin secretos**; no reinicialices ni reemplaces la base.

## Flujo práctico de aceptación

- **Informador:** entra en Inicio, abre un postpartido asignado y ve «Tu lectura breve» por defecto. Pulsa botones grandes de 1 a 10 o «Sin evaluar», escribe una frase opcional y, si quiere, marca hasta tres jugadores presentes en ese partido. Puede guardar borrador o entregar una lectura con evidencia real; al entregar vuelve a Inicio y queda disponible para DD. «Abrir informe detallado» mantiene todas las opciones previas de titular/suplente.
- **Seguimiento:** un 8/10 no marca casillas ni inicia seguimiento. Solo un usuario con `can_track_players` puede seleccionar expresamente «Quiero ampliar...» para un rival puntuado. La ampliación reutiliza la nota, el autor y el partido; se conserva el Player Report 360 y los PDFs. Los usuarios sin permiso solo pueden dejar su valoración normal.
- **DD:** entra en «Mi mesa de trabajo», «Jugadores de interés» o «Peticiones de opinión», elige un externo por identidad, una pregunta concreta y uno o más informadores activos. Puede asignar un encuentro oficial pertinente o indicar «Cuando vuelva a coincidir». La petición es voluntaria; no crea misión Scout, nota ni seguimiento automáticamente.
- **Informador destinatario:** ve la solicitud en Inicio y, si coincide con un partido, en su ficha; el aviso indica **participación documentada** o **posible coincidencia** (no convierte plantilla en XI). Puede contestar «Lo vi», «No pude verlo», «No jugó», «Ahora no» o rechazarla. «Lo vi» enlaza su evaluación o señal previa del mismo partido sin generar una segunda nota. DD ve autor, resultado, fuente y puede cerrar la petición. Rechazar esta solicitud no rechaza el postpartido completo.
- **Informes:** la sección «Informes» del menú abre el archivo ya existente, con filtros y acceso a las versiones entregadas. Admin puro no obtiene permiso deportivo solo por ser Admin. DD puede leer, pero solo DD+Informador puede puntuar.
- **Correcciones:** DD puede eliminar con auditoría un seguimiento individual independiente que sea erróneo, con motivo concreto y confirmación; no puede eliminar mediante esa vía la valoración vinculada al postpartido. Para borrados masivos persisten las herramientas específicas de mantenimiento y sus medidas de protección.

## Comprobaciones negativas

Verifica que un jugador propio, de prueba o archivado no cree una petición de mercado; que un destinatario ajeno no responda a solicitudes de otros; que responder «Ahora no» mantenga la tarea disponible; que «No pude verlo» no invente una nota; que editar la lectura neutral conserve el enlace de la señal; que una petición para un partido sin vínculo real con el jugador sea rechazada; que no se pierdan los estados históricos de informes ni observaciones. Repite con permisos multirrol, dos autores y varias temporadas.

## Limitaciones expresas

Pruebas locales automáticas y migraciones SQLite **no equivalen** a arranque en Streamlit Cloud, comprobación móvil ni migración PostgreSQL real. En el entorno de construcción no está instalado Streamlit y no se pudo descargar; por tanto, no se afirma prueba visual, medición real de un minuto, pruebas en un navegador o concurrencia PostgreSQL. Las peticiones son **avisos internos al abrir Inicio o un partido**, no notificaciones push, correo ni vigilancia en tiempo real. La unicidad de solicitudes concurrentes debe ensayarse en PostgreSQL si se usa de manera simultánea a gran escala. No se actualiza automáticamente ningún registro de petición histórica.
