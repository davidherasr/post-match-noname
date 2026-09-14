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
