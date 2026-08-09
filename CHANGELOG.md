# Changelog

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
