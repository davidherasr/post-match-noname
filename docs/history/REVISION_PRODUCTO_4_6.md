# No Name · Área Técnica — revisión de producto 4.6

**Base única:** `NoName_Area_Tecnica_4.5.1.1.zip`.
**Motivo:** las capturas reales del 28/10/2026 muestran que un usuario DD+Informador llega a un editor de informes cuando su principal necesidad puede ser conocer novedades y consultar decisiones. La modalidad «Completo» presentaba una pantalla vacía por falta de alineaciones. El problema no se resuelve simplemente cambiando colores.

## 1. Contrato del producto

1. **Leer antes que escribir.** Entrar en Inicio debe ser útil aunque el usuario no quiera crear registros ese día.
2. **Una noticia ha de tener fuente, fecha y autor real.** Sin inventar eventos, consensos ni posiciones; solo informes entregados, lecturas neutrales registradas y decisiones DD explícitas. Las notas internas DD no se muestran en actividad compartida.
3. **Contribución voluntaria.** Un Informador con permiso puede realizar una lectura pero no se le asigna una tarea ficticia por defecto. Una petición explícita sí aparece como petición.
4. **Rol de seguridad != perfil de participación.** `admin`, `director` y `reporter` son permisos acumulables; `own_only`, `full`, `free` y `viewer` orientan la interfaz. No se inventa un selector de rol único.
5. **Desconocido = desconocido.** Un futbolista en plantilla no es titular ni participante confirmado. Su presencia en el selector sirve para no inventar identidades, y `participation_id=NULL` conserva la incertidumbre.
6. **DD decide.** Top 3, una calificación de 8 o una señal sin nota son evidencia; ninguna asciende a «Interesante» o «Prioritario» por automatismo.
7. **Dato histórico intacto.** Esta revisión no elimina tablas, no altera Alembic y mantiene la incorporación directa de informes.

## 2. Rutas según el usuario

| Situación | Inicio predeterminado | Acción opcional | Área de profundidad |
|---|---|---|---|
| Informador, `own_only` | Novedades, decisiones compartidas y partido propio | Abrir editor, responder una petición DD | Jornada / Informes |
| Informador, `full` | Mismas novedades; calendario completo accesible | Valorar No Name y rivales | Jornada / Informes |
| Informador, `free` | Novedades y consulta libre | Aportación sobre encuentro permitido | Jornada |
| Perfil `viewer` | Novedades, partidos y catálogo, sin tareas genéricas | Ninguna por defecto | Jugadores / Jornada |
| DD | Novedades y primeras señales con muestra | Selección explícita, pregunta al staff | Dirección Deportiva |
| Admin | Novedades y enlaces a usuarios/calidad | Gestionar incidencias | Administración |
| DD + Informador (p. ej. Aarón) | Novedades y evidencia DD **antes** de la opción de informar | Puede informar, sin obligación ni CTA dominante | Ambas áreas |

**Regla de visualización:** un rol acumulable añade capacidad, no multiplica bloques idénticos de inicio.

## 3. Cambios realmente implementados en 4.6

### Inicio

- Feed cronológico de seis elementos, con título, fuente, fecha, autor y acceso al partido/jugador.
- Solo informes incorporados y lecturas neutrales guardadas; borradores excluidos.
- Decisiones de DD explícitas en la temporada activa, sin mostrar `director_note`, criterios, contraseñas ni registros administrativos.
- Actividad compartida excluye descartes a perfiles sin DD. Las decisiones sobre la plantilla propia no se anuncian como objetivos de mercado.
- DD recibe hasta tres señales externas con tamaño de muestra; los expedientes extensos quedan en Dirección Deportiva.
- El partido del club aparece como tarjeta compacta **después** de novedades; «Aportar una lectura» está plegado.
- Partidos previos y la respuesta a peticiones DD están en bloques opcionales, no en la portada principal.
- Admin tiene enlaces a usuarios y datos sin tareas obligatorias de hora/convocatoria.

### Editor de lectura

- `Básico · No Name`, `Básico · ambos equipos` y `Completo` funcionan sobre un mismo formulario parcial.
- `Completo` añade dos secciones optativas de notas individuales **solo si hay participaciones confirmadas**; no bloquea por falta de XI.
- Cuando no hay participantes confirmados, se ofrecen jugadores de la **plantilla del equipo/temporada**, etiquetados como participación no confirmada.
- Guardar la señal de uno de estos jugadores deja `participation_id=NULL`; no se crea `Participation`, un titular ni una formación.
- La posición desconocida y el jugador sin identificar siguen disponibles fuera del formulario básico.
- No cambia la validación de aportación real: un formulario totalmente vacío no se incorpora.

### DD / Administración

- La mesa DD limita el primer tramo de tarjetas visibles; el resto sigue accesible en el área correspondiente.
- Administración sustituye el selector largo de sección por una banda compacta.

## 4. Auditoría restante — no declarar terminado

### P0 · Verificación con usuarios y navegador (imprescindible)

- **Inicio:** probar con usuarios `reporter`, `director`, `admin`, DD+Informador y los cuatro perfiles de participación. Comprobar que solo ven información autorizada y que el dashboard cabe en una pantalla razonable sin ventanas desbordadas.
- **Informe completo sin XI:** revisar guardar, entregas, volver a abrir, PDF, señal sin nota y cambios de modo en Streamlit real. Verificar `st.form`/`st.fragment` y los efectos de `st.rerun`.
- **Migraciones reales:** comprobar `public.alembic_version` y esquema PostgreSQL tras backup; el inventario recibido tenía 43 tablas/461 columnas y Alembic 0015. Esta versión presupone que se ejecuten 0016 y 0017 antes de usarla.
- **Credenciales:** rotar las contraseñas y secretos expuestos durante el soporte. No dejarlos en documentación, capturas o ZIP.

### P1 · Rediseño pendiente de pantallas completas

| Pantalla | Problema observado o deuda de código | Dirección prevista y aceptación |
|---|---|---|
| Jornada | Match Hub muy extenso, mantenimiento mezclado con consulta | Cabecera compacta, resumen factual, pestañas «Ver / Aportar / Gestionar». La última solo para Admin; 1 clic para ver resultado y lecturas |
| Informes | Historia de modos completos heredados y formularios largos | Una lectura reversible; estados «Borrador / Incorporada» visibles, resumen antes de editar y cambios explícitos |
| Jugadores | Tabla compacta ya creada en 4.5.1, pero filtro y ficha viven separados | Barra de filtros fija, vistas de 25/50, comparación en segundo nivel, evidencia/estado visibles en una fila |
| Player 360 | Demasiados bloques y métricas cuando la muestra es cero | Resumen «qué sabemos / con qué evidencia / qué falta», luego detalle por pestañas; cero nunca significa no evaluado |
| Dirección Deportiva | Múltiples áreas profundas y duplicaciones de tarjetas | Mesa de atención en filas compactas con motivo, muestra, coincidencia, próxima acción; decisiones solo explícitas |
| Equipo rival | Mezcla de plantilla conocida y XI observado | Ficha con fechas de observación y campogramas verificados; registro posicional provisional claramente marcado |
| Administración | Distintas áreas de mantenimiento de épocas anteriores | Inicio de incidencias reales, catálogos y seguridad separados, acción destructiva detrás de confirmación fuerte |
| Mi cuenta y permisos | Rol acumulable + perfil operativo puede confundir | Mostrar capacidad de acción y perfil de navegación por separado; Admin asigna, backend sigue validando permisos |
| Documentos/PDF | Mucho detalle en primeros planos | Resumen breve exportable como primer nivel, dossier en segundo; preservar procedencia y muestra |

### P2 · Arquitectura funcional pendiente

- Registrar un **log de actividad de producto** con permisos de visibilidad y semántica inmutable si se quiere notificar cada cambio exacto y permitir «visto/no visto». El feed 4.6 **es derivado**, no una notificación fiable de cada transición: una decisión puede aparecer de nuevo cuando se edita su nota o su estado.
- Definir el contrato de un `match_reading` general que permita adjuntar observaciones a un jugador sin crear un informe completo de partido para todos. Requiere migración y decisiones sobre autoría/duplicados antes de introducirlo.
- Unificar la capa de consultas repetidas para que Inicio no realice varias lecturas por pantalla sin medición de coste en Supabase.
- Tests de interfaz, perfiles/permiso, accesibilidad, edición simultánea y despliegue real en PostgreSQL.

## 5. Criterios de aceptación de la revisión global futura

1. Un DD+Informador entra y ve **novedades verificables**, sin abrir un formulario ni recibir una tarea ficticia.
2. Un Informador puede pasar varios días consultando sin que aparezcan avisos «pendiente» por no valorar.
3. Si alguien observa un jugador sin conocer XI/identidad, puede guardar una señal sin datos inventados.
4. Una media con un único observador siempre muestra **un partido, un autor**; ningún «consenso» fingido.
5. Un rol de solo consulta nunca puede escribir usando una navegación oculta o llamada al repositorio.
6. Admin no necesita fijar hora ni publicar postpartido para permitir una aportación.
7. Migraciones 0015→0017 no borran jugadores, informes, partidos ni auditorías.
8. Todas las pantallas principales deben probarse en desktop y móvil; pasar pytest por sí solo no certifica el diseño.

## 6. Alcance y cautelas

Esta release **sí implementa** Inicio consultivo, el feed limitado, la selección de plantilla sin XI, el editor completo sin bloqueo y ajustes de DD/Admin. **No implementa** todavía todos los rediseños P1 ni el log de actividad de P2. Debe tratarse como candidata local de una revisión mayor, no como aprobación de producto.
