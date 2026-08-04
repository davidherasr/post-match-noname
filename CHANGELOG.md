# Changelog

## 2.0.0 — Aplicación operativa y fiable

### Fiabilidad analítica

- Los rankings, historiales y comparadores solo incluyen evaluaciones rivales de informes aprobados/finales.
- Exclusión de borradores, jugadores propios y estados sin nota válida.
- Separación explícita entre evaluación `rival` y `own`.
- Datos no evaluados presentados como «Sin muestra» en lugar de cero.
- Filtros por temporada, competición, equipo, informador, confianza, fechas y minutos.
- Dispersión de notas, número de informadores y tamaño de muestra.

### Flujo de trabajo

- Asignación de partidos a informadores y fecha límite.
- Estados de asignación y progreso por partido.
- Informes en borrador, entregados, devueltos y aprobados.
- Revisión y aprobación por administrador/dirección deportiva.
- Autoguardado por bloques y control optimista de revisiones para evitar sobrescrituras.
- Consolidación de varios informes del mismo partido.
- Seguimientos con responsable, próxima revisión, partido objetivo e historial.

### Versionado y documentos

- Snapshots inmutables de informe, alineaciones, evaluaciones y configuración.
- PDF ejecutivo y completo por versión.
- Archivo documental con checksum, tamaño, estado, ruta local y ruta remota.
- URLs firmadas generadas bajo demanda.
- Errores de Storage visibles y reintento de subida remota.
- Regenerar no altera una versión histórica: se usa el snapshot de la entrega.

### Seguridad

- Política de contraseña fuerte y PBKDF2-HMAC-SHA256 con 390.000 iteraciones.
- Bloqueo temporal tras intentos fallidos y registro de accesos.
- Revalidación de usuario en cada ejecución y revocación de sesiones mediante `session_revision`.
- Autorización en la capa de repositorio, no solo en la navegación.
- Cambio obligatorio de contraseña inicial.
- Arranque bloqueado en producción con credenciales de demostración.
- Escape de contenido dinámico usado en HTML.
- Auditoría ampliada con valores anteriores y posteriores.

### Calidad de datos

- Edición y archivo de temporadas, competiciones, equipos, jugadores y partidos.
- Escudos de equipos y fotografías de jugadores.
- Alias de jugador, detección de duplicados y fusión con trazabilidad.
- Plantillas con altas, bajas y dorsales.
- Reconciliación de alineaciones con evaluaciones en borrador.
- Importación XLSX con selector de hoja.
- CSV con detección de separador y codificación.
- Vista previa, validación de titulares/minutos y savepoints.
- Corrección del contador de jugadores creados.
- Eliminación de soporte engañoso para `.xls`.

### Base de datos y recuperación

- Modelo ampliado a asignaciones, versiones, intentos de acceso, alias, fusiones, consolidaciones e historial de seguimientos.
- Alembic como sistema de migraciones.
- Exportación analítica completa.
- Backup técnico ZIP de todas las tablas.
- Script de restauración sobre base vacía o mediante reemplazo explícito.

### PDF 2.0

- Portada editorial compacta.
- Sistemas iniciales representados sobre el campo.
- Titulares, suplentes y minutos.
- Resumen validado del rival.
- Selección ejecutiva de jugadores a conservar.
- Fichas individuales con nota, decisión, confianza y dimensiones opcionales.
- Escudos y fotografías opcionales.
- Tipografía Unicode.
- Modos ejecutivo y completo.
- Paginación dinámica y documento histórico inmutable.

### Calidad técnica

- Arquitectura modular mantenida.
- Ocho pruebas automatizadas sobre seguridad, bloqueos, importación, duplicados, concurrencia, versionado, PDF y analíticas.
- Esquema PostgreSQL de referencia actualizado.
- Dependencias de desarrollo separadas.
