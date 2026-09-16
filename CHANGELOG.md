## 4.2.3.1 · Hotfix de asignaciones y bandeja del Informador

- Corrige el fallo detectado en Cloud 4.2.3: publicación sin informadores permitida por un aviso no bloqueante; el partido aparecía como «Informes 0/0» y no generaba ninguna tarea.
- La publicación nueva requiere seleccionar al menos un usuario Informador. Una selección inválida provoca error explícito y revierte la transacción, no se descarta silenciosamente.
- En Jornada, un Administrador puede asignar o reasignar informadores en un postpartido **ya publicado**, conservando el partido, XI, resultados, informes e histórico; no hay que volver a publicar.
- Inicio muestra tareas reales de informes con botón «Rellenar informe» que abre el editor directamente, y explica cuándo un Informador no tiene asignaciones.
- Jornada explica al Informador sin asignación por qué no aparece el botón. El contador separa informes registrados y asignaciones activas.
- Sin migración nueva: head Alembic 0013, mismos datos y Secrets. No se ha accedido a Supabase productivo.

## 4.2.3 · Catálogo DD, datos de prueba y postpartidos directos

- Admin → Club: equipo propio único por ID y gestión de pruebas/archivos reversibles y auditados (teams/matches); no se identifican registros por coincidencia de nombre.
- Filtro compartido para excluir partidos de prueba/archivados y equipos de prueba/archivados de calendarios, estadísticas oficiales e inteligencia.
- Jugadores: filtros estables por equipo/temporada/posición/ámbito/estado/evidencia, resultados paginados en SQL, contadores desglosados por procedencia.
- Preparación de postpartido: paso de publicación localizable desde el inicio; requisitos explícitos; reutilización de titulares documentados para el mismo partido; sin formación predeterminada inventada.
- Entrega de Informador incorporada directamente a DD y estadísticas, sin revisor ficticio; Admin dispone de reapertura excepcional con motivo/auditoría y snapshot histórico para nueva entrega V+1. Se conservan estados e informes históricos.
- Migración aditiva `0013_data_governance_4_2_3`; no se renombran ni borran históricos. Validación: 113 pruebas y migraciones temporales (no producción).
- Consultar `UPGRADE_4_2_3.md` y `VALIDACION_4_2_3.md`; requiere backup PostgreSQL real y comprobación Cloud posterior.

## 4.2.2 · Hotfix de arranque + paquete de continuidad

- Corrige el arranque observado en 4.2.1 evitando entrar en Alembic cuando Supabase ya está exactamente en el head `0012_sporting_reading_4_2`.
- Mantiene validación física de esquema antes de renderizar la aplicación.
- Recuperación defensiva de `KeyError` únicamente cuando el head y el contrato físico quedan verificados.
- Diagnóstico de arranque dividido por fase y traceback completo en logs.
- Sin nueva migración y sin cambios destructivos de datos.
- Incluye `CONTEXTO_NUEVO_CHAT.md` para continuar el proyecto en otra conversación sin perder decisiones funcionales ni técnicas.

## 4.2.0 · Lectura deportiva y seguimiento real

- Se elimina de la interfaz activa el flujo de asignación `Dirección Deportiva → Scout`.
- Los roles visibles pasan a ser Administrador, Dirección Deportiva e Informador.
- El seguimiento individual de jugadores pasa a ser un permiso especial por usuario, no un rol organizativo.
- Partidos de No Name y partidos neutrales tienen flujos distintos.
- Los postpartidos de No Name incorporan nota colectiva de No Name y del rival.
- Los partidos neutrales permiten una lectura ligera del staff y señalar jugadores sin iniciar seguimiento.
- Dirección Deportiva agrega opiniones con pesos separados para partidos de No Name y neutrales.
- Nuevo centro DD: Lectura deportiva / Plantilla y modelo / Criterio del staff.
- Un jugador de No Name nunca puede abrirse como objetivo de seguimiento de mercado.
- Calendario y Jornada eliminan los formularios de misiones Scout.
- Jugadores elimina la asignación de próxima acción a Scout y muestra observaciones de seguimiento.
- Nueva migración no destructiva `0012_sporting_reading_4_2`.
- Suite final de la release: 101 tests.

## 4.1.2 · Roles sin principal visible

- Se elimina **Rol principal** de Listado, alta y edición de usuarios.
- Administración asigna únicamente **Roles y accesos**; todos los roles seleccionados son capacidades simultáneas.
- La compatibilidad con el campo histórico `users.role` se resuelve automáticamente con una prioridad interna determinista; no concede ni retira permisos.
- Se exige al menos un rol al crear o editar una cuenta para evitar usuarios sin acceso definido.
- Sin cambios de esquema: Alembic continúa en `0011_user_lifecycle_4_1_1`.

## 4.1.1 · Contraseñas libres y gestión completa de usuarios

- Se elimina toda exigencia de complejidad de contraseña: cualquier valor no vacío es válido.
- Desaparece el cambio obligatorio de contraseña; `Mi cuenta` ofrece el cambio solo como opción.
- Administración → Usuarios incorpora Listado, Añadir, Editar / eliminar y Eliminados.
- Admin puede modificar nombre, correo, roles, rol principal, estado y contraseña de cualquier cuenta.
- Eliminación lógica segura con restauración posterior, preservando todo el histórico referenciado.
- Protecciones: no se puede eliminar la propia cuenta conectada ni el último administrador activo.
- Nueva migración no destructiva `0011_user_lifecycle_4_1_1`.
- Suite automatizada: 96 tests.

## 4.1.0 · Admin → DD → Scout

- Administración deja de heredar automáticamente las capacidades de Dirección Deportiva y Scout. Los roles son explícitos y combinables.
- Solo Dirección Deportiva puede crear y asignar trabajo de scouting; el responsable debe tener el rol Scout.
- DD puede asignar Partido completo, Equipo o Jugador(es), a uno o varios scouts, con prioridad y objetivo.
- Jornada elimina el selector Barrido / Observación / Dossier. Varios jugadores abren apuntes rápidos; uno abre observación individual.
- El Dossier deja de ser un nivel de captura: Player Report 360 lo construye con el historial de observaciones.
- El Scout ve sus encargos de DD y puede vincular la observación a la tarea; las tareas con objetivos se completan cuando queda registrada la evidencia correspondiente.
- Administración muestra con claridad qué hace cada rol y permite asignar varios roles a una misma persona.
- Contraseñas provisionales simples: mínimo 4 caracteres cuando el cambio en primer acceso es obligatorio. La contraseña definitiva mantiene la política fuerte.
- Restablecer contraseña desde Administración crea siempre una credencial provisional y fuerza el cambio en el siguiente acceso.
- No hay migración nueva: el head continúa en `0010_core_workspace_schema_repair_4_0_4`.
- Suite automatizada de la release: 94 tests.

## 4.0.7 · XI observado sin jugadores duplicados

- El selector de cada posición del XI es ahora reactivo: al elegir un jugador desaparece inmediatamente de los desplegables de las demás posiciones.
- El jugador ya asignado a una posición permanece visible únicamente en su propio selector, para poder corregirlo sin perder el estado.
- Se elimina el formulario agrupado del editor de XI para que Streamlit refresque las opciones en cada selección.
- Se mantiene una segunda protección en repositorio: aunque llegara una entrada inconsistente, no se puede guardar un mismo jugador dos veces en el XI.
- No hay cambios de base de datos ni migración nueva: el head sigue siendo `0010_core_workspace_schema_repair_4_0_4`.

## 4.0.5 · Navegación segura en Streamlit y Alembic PostgreSQL

- Corrige `StreamlitWidgetAlreadyInstantiatedError` al abrir partidos/tareas desde Inicio.
- Los cambios de navegación se difieren a la siguiente ejecución y se aplican antes de instanciar el `st.radio` lateral.
- Extiende automáticamente `alembic_version.version_num` a VARCHAR(128) en PostgreSQL antes de ejecutar migraciones, evitando el fallo detectado con la revisión 0010.
- No introduce una nueva migración de datos: el head sigue siendo `0010_core_workspace_schema_repair_4_0_4`.

## 4.0.4 · Reparación completa del workspace de Inicio

- Nueva migración no destructiva `0010_core_workspace_schema_repair_4_0_4`.
- El contrato de esquema comprueba todas las columnas ORM de Match/Team/Competition/Season.
- Inicio usa una consulta ligera y deja de hidratar datos que no necesita.
- Se corrige el caso en que 4.0.3 podía validar el esquema y aun así fallar después con `ProgrammingError`.

## 4.0.3 · Reparación de esquema real en Supabase

- Nueva migración no destructiva `0009_schema_repair_4_0_3`.
- Repara bases cuyo `alembic_version` avanzó pero cuya estructura física quedó incompleta.
- Verifica antes de renderizar Inicio que `matches`, `player_season_decisions` y `scout_observations` tengan las columnas requeridas.
- Repara de forma idempotente las columnas de calendario 3.5 y Match Study 4.0 que falten.
- Conserva partidos, jugadores, resultados, informes, observaciones, plantillas y decisiones existentes.
- Si el esquema siguiera incompleto, la app se detiene con un diagnóstico legible antes de ejecutar consultas ORM.
- Suite final: 71 tests.

## 4.0.2 · Hotfix de integridad de despliegue

- El ZIP se distribuye con **raíz plana**: `app.py`, `core/`, `views/`, etc. quedan directamente al extraerlo.
- `app.py` detecta un `core/config.py` antiguo o incompleto y muestra un diagnóstico legible en vez de morir con `ImportError`.
- Se refuerza el contrato interno 4.0.2 entre `app.py`, `core/config.py` y `views/reports.py`.
- Se mantiene el mismo esquema Alembic `0008_match_study_4_0`; no hay migración nueva ni cambios destructivos.

# Changelog

## 4.0.0 · Match Study

- Vídeo disponible Sí/No para partidos neutrales, con referencia opcional.
- Formación conocida Sí/No independiente para local y visitante.
- Campograma visual cuando existe formación real.
- Modo plantilla/dorsal cuando la formación es desconocida.
- Pegado rápido de plantilla Federación sin crear participaciones ficticias.
- XI observado por slots del sistema y campograma responsive.
- Filtro Scout por equipo en partidos neutrales.
- Contexto visible desde Jornada: vídeo y formaciones conocidas X/2.
- Scout puede capturar alineaciones neutrales sin poder alterar partidos de No Name.
- Exportación analítica incluye contexto de estudio.
- Migración no destructiva `0008_match_study_4_0`, preservando formaciones existentes.
- 5 pruebas específicas nuevas; suite completa: 64 tests.

## 3.9.0 · Matchday y fiabilidad

- Día operativo en zona `Europe/Madrid`.
- Inicio distingue Partido de hoy y Próximo partido.
- Jornada prioriza la ronda real de No Name y marca partidos de hoy.
- Panel de estado operativo de datos reales.
- Comprobación read-only de matchday por script.
- Informes y calendario secundario corregidos para permisos multirol acumulativos.
- Eliminada la hora ficticia 17:00 del último flujo de horarios que todavía la conservaba.
- Navegación heredada de Calendario redirigida a Jornada.
- Parser/contratos actualizados a 3.9.0.
- 10 pruebas nuevas con la J1 real La Cistérniga C.F. - C.D. Noname.

## 3.7.0 · Calendario operativo

- El calendario usa una sola fecha federativa orientativa; se eliminan rangos del flujo normal.
- Nuevo estado `provisional`: fecha de jornada conocida, horario pendiente.
- Fecha + hora son obligatorias para activar postpartido, informe nuevo y observación Scout.
- Las misiones DD pueden planificarse antes del horario y sincronizan `due_at` al confirmarlo.
- Reimportar calendario provisional preserva horarios ya confirmados.
- Postpartido manual registra `kickoff_at`.
- Corrección de autorización multirol en informes.
- Observación Scout recupera rol, recomendación y criterios guardados, y el cambio de rol refresca criterios inmediatamente.
- Acceso directo desde Dashboard Admin a incidencias de horario.
- Sin migración nueva: Alembic permanece en `0006_player_report_360_3_6`.

## 3.6.2 · Calendar importer compatibility

- Admite ventanas completas `DD/MM/YYYY-DD/MM/YYYY` en cualquier mes.
- Admite variante `DD/MM-DD/MM/YYYY`.
- Identificador visible `Importador 3.6.2` en Calendario.
- Carga directa de TXT UTF-8 y contadores de reconocidos/errores.
- Sin migración de base de datos.

## 3.6.2 · Calendar window hotfix

- Corrige la importación de fines de semana que cruzan de mes o de año.
- Nuevo formato recomendado: `31/10/2026-01/11/2026`.
- Mantiene el formato compacto `15-16/08/2026` cuando ambos días pertenecen al mismo mes.
- Una ventana de dos días sigue guardándose como `Horario pendiente`, nunca como fecha definitiva.
- No hay cambios de base de datos ni nueva migración.

## 3.6.0 · Player Report 360

- Nuevo Player Report 360 en pantalla para jugadores observados/ojeados.
- Cabecera profesional con rendimiento, encaje No Name y confianza explicable.
- Resumen ejecutivo con conclusión, fortalezas, riesgos, nivel, proyección y recomendación.
- Radar y criterios clave construidos exclusivamente desde el Modelo No Name y puntuaciones realmente registradas.
- Separación entre rendimiento postpartido y perfil Scout.
- Evolución conjunta de postpartidos y observaciones Scout con fuente, partido, posición y observador.
- Posiciones realmente observadas.
- Comparación contextual con la plantilla de No Name y perfiles conocidos de la liga para el mismo rol.
- Mapeo de jugadores propios al Modelo No Name para crear referencias internas reales.
- Decisiones DD por temporada ampliadas con nivel actual, proyección y criterios.
- Ficha Scout Ejecutiva PDF y Dossier Player Report 360 PDF bajo demanda.
- Política explícita de no inventar mercado, altura, estadísticas, comparables externos o atributos inexistentes.
- Migración no destructiva `0006_player_report_360_3_6`.

## 3.5.0 · Planning & Scouting

- Calendario completo de toda la liga con importación masiva y horarios pendientes/confirmados.
- Partidos neutrales disponibles para scouting y análisis rival.
- Perfil Scout completo y capacidades múltiples por usuario.
- Misiones DD por jugador, varios jugadores, equipo o rival.
- Observaciones Scout repetibles y scouting espontáneo.
- Informe estructurado de equipo/rival.
- Modelo No Name configurable, criterios ponderados y consulta Scout.
- Necesidades de plantilla, plantilla sombra y decisiones por temporada.
- Planificación automática de observaciones usando calendario + necesidades + candidatos.
- Evidencia postpartido y evidencia específica separadas.
- Búsqueda/paginación SQL en vistas densas.
- Centro de calidad de datos y logout con limpieza total de sesión.
- Migración no destructiva `0005_planning_scout_3_5`.

## 3.4.1 · Quality of Life

- Nuevo postpartido precarga automáticamente competición, sistema de No Name e informadores del último partido de la temporada.
- El dashboard de administración muestra y permite recuperar directamente el último borrador de postpartido guardado en la nube.
- El informe añade progreso por equipo y filtro **Solo pendientes**, sin consultas adicionales mientras se puntúa.
- Dirección Deportiva permite abrir directamente el expediente de un jugador desde la bandeja de decisiones.
- Sin cambios de esquema: se mantiene la revisión Alembic `0004_scout_workflow_3_3`.

## 3.4.0 · Audit Closure & Live Performance

- Informe compacto con `st.fragment` y estado real de cambios sin guardar.
- Desambiguación de homónimos rivales con contexto y decisión humana.
- Confianza 0–100 desglosada y tendencias por ventanas.
- DD: alertas vencidas, dossiers de rivales y XI con filtros de confianza/seguimiento.
- Backup bajo demanda, filtro de jornada y telemetría SQL real por sesión.
- Aceptación live con SAVEPOINT + rollback contra la DATABASE_URL configurada.
- Repositorios y motor PDF divididos en módulos.
- Sin nueva migración; misma base Supabase.

## 3.3.0 · Advanced Scout & Production Polish

- Nuevo flujo **Jugadores ojeados**: Observado → Candidato → Solicitado → En revisión → Ojeado/Archivado.
- Dirección Deportiva ubica al jugador en una posición y rol del modelo de No Name antes/después de solicitar una ficha scout.
- Ficha scout avanzada asignable a informadores con bloque técnico, táctico, físico, mental y atributos opcionales específicos por posición.
- Conclusión final de DD con encaje, nivel actual, proyección, decisión y resumen propio.
- Informe semanal sigue compacto: opciones Destacado/PDF ocultas por defecto y flujo No Name → Rival → Entregar que impide saltarse el guardado.
- Evaluaciones guardadas con UPSERT SQL real `ON CONFLICT DO UPDATE`.
- Identidad rival más segura por equipo/temporada/alias y tratamiento prudente de homónimos.
- Rankings, XI y expediente 360 basados en **posición observada**.
- XI de la liga con criterios de media, confianza, forma reciente o selección DD y sustitución manual.
- Tendencias robustas por medias de ventanas inicial/reciente y dispersión.
- Confianza 0–100 explicable por muestra, informadores, consenso y recencia.
- Bandeja DD con razones accionables y dossier reforzado de equipos rivales.
- Base de datos simplificada: datos internacionales/secundarios pasan a paneles avanzados.
- Archivo de informes lazy y backup bajo demanda.
- Migración `0004_scout_workflow_3_3` con tablas scout e índices compuestos de rendimiento.
- Instrumentación de tiempos en sesión para detectar operaciones lentas sin incrementar escrituras.
- Limpieza técnica del generador PDF, repositorios especializados y validación pura de postpartido.
- Accesibilidad móvil reforzada y navegación más compacta en áreas densas.

## 3.2.0 · League Intelligence & Fast Workflow

- Postpartido preparado principalmente en memoria y publicación transaccional.
- Borradores remotos opcionales para continuar otro día sin guardar cada interacción.
- Cache de contexto, plantilla propia, último XI, rival previo y lista de borradores durante el flujo.
- Formaciones automáticas con sugerencia de XI y cambios `minuto · sale · entra`.
- Rival sin plantilla previa obligatoria, pegado rápido y guardado masivo de alineación/roster.
- Workspace de informes y guardado masivo por equipo; sin escritura por jugador.
- Rankings de scouting agregados en SQL en lugar de agrupar todas las evaluaciones en Python.
- Bandeja de revisión cargada en bloque para eliminar N+1.
- Búsqueda global de catálogo y edición masiva de plantilla.
- Dirección Deportiva enfocada exclusivamente a nuestra liga: Panorama, Jugadores 360, Por posiciones, Equipos, Seguimiento, Comparador, XI de la liga, Consenso, Informes y Listas.
- Índice de confianza basado en muestra, informadores y dispersión.
- Tendencias de evolución, destacados recientes y bandeja de decisión.
- Nueva migración Alembic `0003_league_intelligence_3_2`, aditiva y no destructiva.
- Backup/restore y exportación analítica actualizados con perfiles DD, borradores y listas.
- 24 pruebas automatizadas.

## 3.1.0 · Performance & Accessibility

- Evaluaciones propias y rivales agrupadas en formularios: no hay escrituras por slider ni por jugador.
- Guardado masivo de cada plantilla en una sola transacción y con una única precarga de evaluaciones existentes.
- Eliminación de `st.tabs` para evitar ejecutar secciones ocultas.
- Carga perezosa de documentos, históricos y herramientas de dirección deportiva.
- Revalidación de sesión con TTL y bootstrap memorizado para reducir consultas repetitivas.
- Cache selectiva de ajustes de aplicación.
- Dashboard de administración sin consulta N+1 del progreso de asignaciones.
- Filtros de jugadores y consenso agrupados en formularios.
- Generador de once automático por formación; 4-4-2 y otras once estructuras crean sus posiciones predeterminadas.
- Once rápido de No Name: el administrador asigna nombres a posiciones ya creadas.
- Estructura rival automática por formación, reutilización de última alineación e importación opcional.
- PDF Ejecutivo renombrado a **Resumen** y rediseñado a 1–2 páginas de uso diario.
- PDF Completo se conserva y solo se genera bajo demanda.
- Mejora general de contraste, foco, tamaño táctil, etiquetas, responsive y `prefers-reduced-motion`.
- Sin cambios de esquema: compatible con la misma base Supabase 3.0/3.0.1.
- Sin datos deportivos de demostración en la release.

## 3.0.1 · Navegación limpia

- Ocultada la navegación automática que Streamlit genera al detectar la carpeta `pages/`.
- Añadido `[client] showSidebarNavigation = false` en `.streamlit/config.toml`.
- Añadida defensa en tiempo de ejecución con `st.set_option("client.showSidebarNavigation", False)`.
- El login ya no muestra un sidebar vacío: queda centrado y limpio.
- Tras iniciar sesión solo se muestra el menú propio de No Name según el rol del usuario.
- `toolbarMode = "minimal"` reduce controles de desarrollo innecesarios en la interfaz publicada.
- Sin cambios de esquema: no requiere migración y no modifica datos de Supabase.

## 3.0.0 · No Name Edition

### Cambio de producto
- La aplicación pasa de ser una plataforma genérica de scouting a una herramienta operativa de postpartido para No Name.
- El scouting rival nace automáticamente de las valoraciones realizadas después de cada partido.
- El propio equipo mantiene un histórico interno independiente.

### Nuevo postpartido
- Flujo único en una página: partido → No Name → rival → publicar.
- Configuración inicial del club propio dentro del flujo.
- Creación de temporada activa dentro del flujo.
- Creación inline de competición y rival.
- Alta individual y pegado masivo de jugadores propios.
- Plantilla propia reutilizable por temporada.
- Copiar última alineación propia.
- Alineación rival sin plantilla previa obligatoria.
- Creación/resolución automática de rivales y actualización de su plantilla.
- Reutilización de la última alineación conocida del rival.
- Pegado e importación opcional CSV/XLSX.
- Asignación de informadores y publicación desde la misma pantalla.

### Informador
- Dashboard y navegación propios.
- Eliminados del flujo operativo los apartados generales obligatorios del rival.
- Equipo propio y rival usan la misma ficha simple.
- Metadatos deportivos bloqueados para el informador.
- Slider 0–10, paso 0,1.
- Botones rápidos 5–9.
- Observación opcional.
- Destacado/PDF automáticos y manualmente editables.
- 0 significa no valorado.
- Se permite finalizar con jugadores sin valorar.

### Administración
- Dashboard centrado en Nuevo postpartido.
- Partidos y Base de datos pasan a ser mantenimiento/corrección.
- Menú reducido y jerarquizado.

### Jugadores y dirección deportiva
- Histórico independiente de jugadores No Name.
- Histórico rival solo con evaluaciones válidas aprobadas/finales.
- Dirección deportiva prioriza pendientes de revisión, notas ≥8, perfiles repetidos y seguimientos.
- Rankings y filtros avanzados siguen disponibles como segundo nivel.

### PDF
- Respeta `pdf_include` en tablas, watchlist y fichas.
- Prioriza un documento más corto y accionable.
- Mantiene ejecutivo/completo, versiones inmutables, checksum y storage.

### Base de datos
- Nueva revisión Alembic `0002_noname_3_0` no destructiva.
- Compatible con el esquema normalizado de 2.x.
- No se incluyen datos deportivos de ejemplo.
- Bootstrap limitado al administrador técnico y ajustes de aplicación.

### Calidad
- Nuevas pruebas de alineación rival sin roster previo, copia de alineación, separación own/rival y ausencia de seed deportivo.
- Contrato de release actualizado a 3.0.0.

## 2.1.1
- Hotfix de compatibilidad entre `app.py` y la API de `pages/reports.py`.

## 2.1.0
- Valoración simple por fichas, navegación por rol y automatismos PDF/destacado.

## 2.0.0
- PostgreSQL/Supabase, Alembic, seguridad, snapshots, seguimiento, backups y analítica robusta.
## 4.0.1 · Hotfix de despliegue y arranque

- Se elimina físicamente el directorio especial `pages/` de Streamlit. Las vistas internas pasan a `views/`, por lo que ya no puede reaparecer la navegación automática con `admin`, `calendar`, `scout`, etc.
- Arranque PostgreSQL/Supabase robustecido: prueba de conectividad con reintentos, TLS obligatorio para hosts Supabase y timeout finito.
- Alembic reutiliza la conexión ya validada durante el arranque, evitando abrir una segunda conexión en frío.
- Los fallos de conexión ya no derriban la aplicación con un traceback rojo: se muestra un diagnóstico seguro sin exponer contraseña.
- Se detectan `DATABASE_URL` incompletas o con placeholders antes de intentar migrar.
- Aviso específico cuando se usa el host directo `db.<project>.supabase.co`, recomendando Session pooler en despliegues sin IPv6.
- Suite de pruebas estabilizada cerrando correctamente los engines SQLite de cada test.
- No cambia el esquema respecto a 4.0.0: Alembic continúa en `0008_match_study_4_0`.

## 4.0.7 · Convocatoria clara y Scouting operativo

- Federación puede distinguir TITULARES y SUPLENTES sin inferencias por orden.
- XI y banquillo se gestionan juntos cuando existe formación conocida.
- Desplegables de XI y Scouting diferencian TIT / SUP / PLANTILLA.
- Scouting explica claramente Barrido rápido, Observación individual y Dossier completo.
- Sin cambios de esquema; mantiene Alembic en 0010.
