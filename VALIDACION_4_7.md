# Validación 4.7 · resultados locales y checklist operativo

**Verificación automatizada local:** 218 pruebas `pytest`, compilación Python y consistencia de versiones; migración de SQLite a la revisión `0018_workspaces_4_7`. La suite cubre también regresiones anteriores y pruebas de backend 4.7. Para la publicación no basta con este número.

**Importante:** no se ha conectado a la base Supabase real, no se ha ejecutado Streamlit Cloud y la instalación de Streamlit local falló porque este entorno no pudo resolver PyPI. Se comprobó la importabilidad de los módulos de interfaz con un módulo simulado, **que no equivale** a prueba visual ni interacciones reales. La documentación oficial de Streamlit recomienda `AppTest` y la selección `st.dataframe(..., on_select='rerun')`, que deben ensayarse con la versión instalada en producción.

## Pruebas de aceptación en navegador (obligatorias antes de producción)

Marca cada ítem como `OK / Error / No probado` con cuenta y captura de evidencia:

| ID | Perfil / recorrido | Condición verificable |
|---|---|---|
| A01 | DD exclusivo | Menú DD, Inicio y bandeja; no se le pide informar. Abre respuesta de solicitud desde DD, no una ruta inaccesible. |
| A02 | DD + Informador | Puede decidir y también realizar informe voluntario; cambio de rol no cambia autoría ni privacidad. |
| A03 | DD tras diez días | Ver informe, marcar X, comprobar que desaparece de Nuevos y permanece en Todos. Guardar con estrella sin iniciar seguimiento. |
| A04 | DD propuestas | Una propuesta explícita, su evidencia, guardar, iniciar seguimiento solo con jugador identificado, descartar y retornar. Compartir solo con destinatario seleccionado. |
| A05 | DD solicitudes | Pedir observación de jugador sin nombre y enlazar a propuesta. Destinatario recibe y puede responder con texto/informe; la X no resuelve la solicitud. |
| A06 | David/Roma lunes | Inicio → último partido Noname → resumen → rápido o completo sin XI; borrador y regreso. |
| A07 | David/Roma martes | Partido futuro → partidos del rival → lectura individual o síntesis de varias fechas. Ningún formulario del equipo rival se exige. |
| A08 | Coloto ocasional | Mis partidos → último → seleccionar nota 7 → Guardar; antes de Guardar no hay fila. Volver y modificar sin duplicar. |
| A09 | Coloto zona | Sin XI, elegir EI y dorsal opcional. La valoración queda asociada a zona, sin inventar jugador ni crear participación. |
| A10 | Privacidad | Roma no puede leer borrador ni informe privado de David (tampoco por URL, tabla o gráfico). DD no ve borrador de David. |
| A11 | Jugador provisional | Identificar dorsal solo cuando hay coincidencia confirmada; conservar dorsal/posición original. No fusionar automáticamente dos señales. |
| A12 | Plantilla DD | Cuatro informadores en un partido = 1 PJ, 4 opiniones; no generar tendencia con un partido. Comprobar muestra 0. |
| A13 | Ficha de jugador | Abrir desde catálogo/plantilla y volver; conservar filtros; visualizar solo fuentes permitidas. |
| A14 | Equipo histórico | Abrir desde partido; lista de roster + partidos + fuentes, no confundir con preparación táctica. |
| A15 | Datos incompletos | Partido sin hora, informe sin XI, suplente sin nombre, rival externo; todos navegables. |
| A16 | Alineación comprobada | Importar lista sin TITULARES no genera Participation. Etiquetas explícitas sí; usuario own_only no puede editar oficiales. |
| A17 | Formación contradictoria | David introduce 4-4-2, Roma 4-2-3-1. DD ve las interpretaciones compartidas; formación oficial no se modifica. |
| A18 | Corrección | Diego comunica error; Admin revisa y cierra. Una corrección posterior no muta la nota firmada previa. |
| A19 | Navegación móvil | Probar 360–420 px: notas 1–10, tabla, botones, retorno a partido, mensajes largos, formularios y acceso a menú. |
| A20 | Históricos 4.6 | Reportes y opiniones entregados siguen legibles en DD y las fichas de partidos; no se presentan falsamente como recién publicados. |
| A21 | Recuperación | Abrir una aportación desde bandeja, volver a Inicio, filtros anteriores; salida y nueva sesión retienen visto/guardado. |
| A22 | Seguridad/operación | Revisar permisos SQL, backup restaurable, secretos rotados, Alembic head y ausencia de duplicados tras envío repetido. |

## Aceptación de release

**No llamar «estable en producción» a la 4.7** hasta que al menos A01–A22 se hayan ejecutado con la app real, un duplicado de la base o un entorno de preproducción con datos representativos, y los errores bloqueantes estén resueltos. Ante un error de permiso o migración, bloquear el despliegue.

## Límites documentados

- Los cortes de vídeo se registran como **referencia textual**, no como vídeos reproducibles/almacenados por un nuevo servicio ni como herramienta de edición.
- Las estadísticas de pases se pueden adjuntar como **lectura textual**; no se importan automáticamente CSV ni se calculan mapas/redes de pases en la 4.7.
- La corrección de alineaciones oficiales de partidos con informes históricos cerrados exige revisión de integridad, no una sobreescritura automática.
- Los tests no sustituyen sesión móvil ni revisión visual de todas las pantallas; estos pasos son pendientes, no resultados supuestos.
