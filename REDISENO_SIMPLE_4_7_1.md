# No Name · Área Técnica 4.7.1 — simplificación del uso diario

**Problema identificado:** 4.7 convirtió tareas breves en recorridos con demasiados filtros y alternativas, y dejó sin acceso visible una herramienta existente de eliminación de registros. Esta versión no añade más conceptos deportivos: reduce las decisiones que el usuario debe tomar para conseguir su objetivo.

## Inicio según el uso real

- **Informador de Noname:** `Mis partidos` abre el último encuentro documentado, con una única acción principal `Valorar a Noname` o `Editar mi valoración`. Nota de 1–10 mediante pastillas y un único botón `Guardar valoración`. Campo por posiciones y comentarios, opcionales. Los demás partidos y el histórico personal están detrás de `Elegir otro partido`.
- **David y Roma:** al entrar se muestra el último partido propio con `Elaborar postpartido de [rival]`, `Continuar...` si hay un borrador o `Consultar...` si ya hay un análisis completo entregado. No se considera terminado un postpartido porque exista solamente una nota rápida. También se muestra el próximo adversario con acceso a sus partidos. Para los encuentros externos, `Anotar este partido` es el camino principal. Otros formularios quedan en `Otras aportaciones`.
- **Aarón:** inicio con una sola acción para revisar las propuestas y solicitudes; las novedades están disponibles sin inundar la portada de filtros. La mesa deportiva prioriza propuestas y solicitudes; Modelo, Actividad y aportaciones están en `Más`.
- **Administración:** empieza en `Jugadores`: buscar por nombre, seleccionar, corregir nombre/posición o eliminar. El borrado exige vista previa de filas dependientes, confirmar una copia de seguridad y escribir `BORRAR`. Los datos vinculados se calculan y vuelven a validar mediante el motor existente de eliminación, que registra auditoría. No hay borrado silencioso.

## Información que no se inventa

- Sin hora confirmada: la fecha se muestra sin el texto repetitivo «Hora no confirmada».
- Sin XI: no se generan titulares artificiales, ni se bloquean notas por zonas.
- Un jugador destacado para Aarón se envía de forma **expresa** marcando la casilla correspondiente. Una nota alta por sí sola no produce propuestas ni decisiones de fichaje.
- Una corrección de nombre conserva la identidad del jugador y su histórico. Un borrado definitivo se muestra como operación de mayor riesgo, no como simple cambio de nombre.

## Datos y despliegue

- **Misma migración que la 4.7:** `0018_workspaces_4_7`. No hay migración adicional ni se modifica Supabase desde este paquete.
- Los informes, fichas, roles, eventos y aportaciones existentes se mantienen. Las funciones especializadas siguen presentes, pero no aparecen como pasos obligatorios en las pantallas habituales.
- En un despliegue, sustituye **todo el repositorio**, no únicamente `experience47.py`.

## Pruebas funcionales obligatorias en navegador antes de utilizarla en producción

1. Coloto: entra, ve último partido, pulsa 7, guarda, sale, vuelve y edita. Comprueba que no se duplica.
2. David: ve último partido, escribe dos párrafos de postpartido, guarda borrador, vuelve y envía a Aarón; no se da por terminado al publicar solo una nota rápida.
3. Roma: abre partido externo, valora a un futbolista desconocido y marca «Destacar para Aarón». Se envía una propuesta independiente y no se inventa su nombre.
4. Aarón: ve la propuesta, puede guardarla sin iniciar seguimiento y puede solicitar información.
5. Admin: busca un jugador mal escrito, cambia nombre y comprueba que conserva su plantilla y evaluaciones.
6. Admin: intenta borrar un jugador con informes. Debe ver las dependencias, una advertencia, confirmación de copia y `BORRAR` antes de ejecutar. No realizar esta prueba sobre datos reales no respaldados.
7. Todas las cuentas: verificar ausencia de acceso a informes privados o borradores ajenos.
8. Navegación desde y hacia históricos, ficha de jugador y último encuentro; probar también desde móvil.

**Estado:** la validación automatizada no constituye prueba visual. Este ZIP es candidato para comprobación en entorno de pruebas, no una publicación ya verificada con Streamlit Cloud/Supabase real.
