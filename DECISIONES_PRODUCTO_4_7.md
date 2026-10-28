# No Name · Área Técnica 4.7 — Contrato de producto

**Fecha:** 28 de octubre de 2026. **Base:** exclusivamente 4.6. **Fuente funcional:** once rondas de entrevistas, auditoría de la 4.6 y prototipo de recorridos. **Alcance:** sustitución de la navegación y las pantallas principales, preservando los expedientes y tablas anteriores. La aplicación se refiere al club como **Noname**.

## 1. Roles frente a perfiles operativos

- **Director deportivo (Aarón):** entra ocasionalmente; Inicio es una bandeja de noticias reales y una síntesis de asuntos abiertos. Puede abrir propuestas expresas, leer aportaciones compartidas, decidir guardar una propuesta o iniciar seguimiento de un jugador identificado, solicitar ampliaciones y dar prioridad a partidos concretos. Marcar importante **no** genera una tarea hasta designar destinatario en una solicitud. Puede informar por voluntad propia **solo cuando** tenga además el rol Informador.
- **Analistas (David y Roma):** comparten rol Informador y perfil operativo completo/libre. Inicio contiene novedades pertinentes, peticiones y acceso a partidos. Lunes: encuentro propio; martes: últimos partidos del rival. Pueden hacer valoración rápida del propio, análisis completo con borrador, observaciones de jugadores externos, notas generales, estructura observada y síntesis de varios partidos. Proponer a DD es una acción voluntaria explícita.
- **Informadores de Noname (Coloto, Diego, Viti...):** menú reducido **Mis partidos · Mis valoraciones · Mis solicitudes**. El último partido tiene acceso directo a la nota rápida; seleccionar 1–10 **no guarda** hasta pulsar Guardar. Zona, dorsal, impresión cualitativa y comentario son voluntarios. Una petición real de DD se puede contestar, pero no existe obligación semanal genérica.
- **Administración:** pantalla independiente de incidencias, usuarios, datos y herramientas técnicas. No depende de completar calendarios semanales, horarios o XI para que otros aporten. Cualquier usuario puede comunicar un error. Administración resuelve o descarta con historial; DD y analistas full/free mantienen datos deportivos comprobados en el apartado del partido. El control de permisos está **en repositorios y consultas**, no solo ocultando menús.
- **Consulta:** sin permiso Informador, no escribe valoraciones; puede consultar los datos públicos de catálogo/partidos pero no opiniones privadas.

Los nombres de las personas no están codificados como ACL. El usuario Admin puede cambiar roles acumulables y el `participation_profile` (`own_only`, `full`, `free`, `viewer`).

## 2. Privacidad, evidencia y estado

1. La aportación pertenece a su autor. Si está en **borrador**, solo él puede leerla. Si se **comparte**, la ven autor, DD y Administración. No se muestra al resto del staff en listas, medias o ficha.
2. Guardar borrador, publicar, marcar una notificación vista, guardar una novedad, guardar una propuesta, iniciar seguimiento y resolver una petición son **acciones independientes**.
3. DD puede compartir una **propuesta concreta** con destinatarios concretos; esto no abre el informe privado de origen. La propuesta contiene motivo, asunto y referencia.
4. Los informes anteriores continúan consultables. Los acontecimientos legados se incluyen en **Todos**, no se anuncian como si fueran nuevas notificaciones en la primera conexión a la 4.7.
5. Los eventos nuevos tienen marca de lectura y guardado **por usuario**. La X retira de Nuevos, pero no borra documentos ni cierra solicitudes.
6. El informe rápido de Noname se actualiza sobre el **mismo registro** (índice parcial único por autor y partido). En estadísticas de plantilla se cuenta **cada encuentro una sola vez**, separando partidos de número de opiniones y haciendo tendencias únicamente con cuatro o más encuentros distintos.
7. No se infieren titulares desde la plantilla. Una observación sin XI conserva zona y dorsal, **sin crear Participation**. La resolución manual de identidad conserva autor, dorsal/posición originales y fecha.
8. Una nota 8, una tendencia negativa o una observación cualitativa **no** crean interés DD, fichaje, misión o necesidad de plantilla automáticamente.
9. Las estructuras interpretadas por dos analistas son aportaciones independientes; la estructura de referencia solo se cambia mediante la función autorizada de mantenimiento de datos.

## 3. Matriz de pantallas y recorridos

| Pantalla | Uso real | Acciones y criterios de aceptación |
|---|---|---|
| Inicio DD | Volver después de 10 días | Nuevos/Todos/Guardados; tipo de noticia; X visto reversible, estrella guardado, fuente abrible; propuestas y peticiones sin resolver siguen vigentes. |
| Dirección Deportiva | Revisar recomendaciones | Propuesta con motivo y evidencia; decisión **guardar vs seguir**; solicitar una ampliación vinculada; compartir individualmente, no abrir automáticamente opiniones. |
| Inicio analista | Ver lo pendiente y último/próximo partido | Solicitudes asignadas, novedades permitidas, acceso a partido y dossier, sin tareas automáticas. |
| Mis partidos | Informador ocasional | Último partido + Valorar; lista corta de encuentros; sin XI, hora ni informe previo. |
| Valoración rápida | Entrar, puntuar, salir | Nota 1–10 sin preselección ficticia; Guardar explícito; edición sin duplicar; zona de campo opcional. |
| Partidos | Consultar calendario | Tabla compacta, propios/neutrales, recientes/próximos/todos; nombre/dorsal desconocidos no bloquean; crear partido comprobado sin hora inventada. |
| Ficha de partido | Consultar antes de aportar | Resultado, hora si hay, estructuras confirmadas con advertencia, fuentes privadas permitidas; entradas separadas para rápido, completo e individual; importancia DD opcional. |
| Completo | Analizar propio, rival o ambos | Borrador privado, contexto cualitativo, datos propios y referencia a cortes; recuperar/ampliar/publicar voluntariamente; sin XI obligatorio. |
| Observación individual | Observar un futbolista externo | Jugador existente opcional, equipo, zona, dorsal, nota y descripción; privada por defecto, compartir expresamente; resolución posterior no destructiva. |
| Síntesis | Tres partidos del rival | Varios partidos referenciados, síntesis opcional independiente; no es una cuarta evaluación cuantitativa. |
| Mis aportaciones | Retomar trabajo tras semanas | Borradores/compartidos, enlace a detalle, edición de borrador y publicación individual o en lote; informes antiguos preservados. |
| Mis solicitudes | Contestar encargo | Respuesta de texto o informe ya compartido; enlace a propuesta y partido; persistencia de estado hasta responder/cerrar; recibido incluso por informador `own_only`. |
| Jugadores | Encontrar fichas sin recorrer tarjetas | Catálogo SQL paginado real, nombre/posición/equipo; ficha con fuentes visibles y muestra, sin divulgar calificaciones ajenas. |
| Ficha de equipo | Consulta histórica | Plantilla de temporada, partidos observados, evidencia del usuario; **separada** del análisis de próximo rival. |
| Plantilla DD | Ver desempeño propio | Tabla por jugador/posición, **PJ distintos**, nº de opiniones, media solo de DD, tendencias condicionadas a muestra y cobertura por posición. |
| Modelo Noname | Planificar cuando proceda | Perfiles y necesidades manuales, discretos; no exige mantenimiento semanal. |
| Administración | Corregir lo importante | Incidencias comunicadas, usuarios, temporadas, datos, herramientas; no considera falta de hora o informes voluntarios pendientes una incidencia. |

## 4. Regresiones que bloquean la aceptación

- Un perfil `own_only` no puede acceder a la fuente privada de otro Informador cambiando una ruta. DD tampoco puede leer un borrador ajeno ni resolver su identidad antes de que se comparta.
- Al marcar vista una noticia, una solicitud dirigida sigue pendiente. Al guardar una propuesta no se inicia seguimiento. Una nota alta no crea decisión.
- Los nuevos informes compartidos sí generan novedad; los informes antiguos siguen presentes sin simular novedades recientes.
- Un duplicado de partido oficial o de nota rápida no debe añadir una segunda fila cuantitativa.
- `TITULARES`/`SUPLENTES` solo crea participaciones si el texto está marcado y se permite modificar; listas sin estos encabezados **solo** actualizan plantilla.
- Si el equipo tiene cuatro opiniones de un único partido, no se afirma que haya cuatro partidos observados ni una tendencia.
- La aplicación debe comprobar permisos en cada operación CRUD y el contrato físico antes de cargar pantallas.

## 5. Alcance que requiere validación o evolución posterior

Se entregan **referencias** a cortes y datos de pases escritos en análisis, no un motor que lea vídeos, corte clips automáticamente o importe hojas CSV arbitrarias. Las calificaciones se agregan con reglas conservadoras, pero no se ha validado su utilidad con datos productivos reales. La formación observada se conserva como interpretación y no se arbitra automáticamente. La 4.7 no sustituye una comprobación visual real de Streamlit ni pruebas de acceso con las cuentas reales del staff. Ver `VALIDACION_4_7.md`.
