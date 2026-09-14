# No Name PostMatch 4.1.2

Aplicación interna de No Name para postpartido, scouting, Dirección Deportiva y planificación de plantilla. La capa visible se organiza en **Inicio · Jornada · Jugadores · Plantilla · Administración**, mientras la profundidad del modelo de datos queda detrás del contexto de trabajo.

## Flujo diario

- **Inicio**: lo que requiere atención, con Partido de hoy/Próximo partido y tareas.
- **Jornada**: calendario operativo, Match Hub, horarios, postpartido, scouting e informes.
- **Jugadores**: ficha única Player Report 360, evolución, Modelo No Name, decisión y próxima acción.
- **Plantilla**: roles, necesidades, referencias internas, candidatos y oportunidades de scouting.
- **Administración**: usuarios, club, datos, configuración y herramientas técnicas.

Los roles son capacidades explícitas y combinables. No existe Perfil activo: Administración, Dirección Deportiva, Scout e Informador son responsabilidades independientes.


## 4.1 · Flujo de trabajo por responsabilidades

4.1 separa definitivamente **Administración → Dirección Deportiva → Scout**. Administración prepara usuarios, calendario, equipos, horarios y datos; Dirección Deportiva decide qué merece seguimiento y lo asigna a uno o varios usuarios con rol Scout; el Scout ejecuta el visionado y registra lo observado. Ser Administrador ya no concede automáticamente capacidades de DD o Scout: si una persona realiza varias funciones, Administración le asigna varios roles.

En Jornada desaparece el selector manual **Barrido / Observación / Dossier**. El flujo se deduce del trabajo real: varios jugadores generan apuntes rápidos, un jugador abre una observación individual y el **dossier 360** se construye automáticamente con el historial acumulado en Player Report 360.

Desde 4.1.1 las contraseñas son deliberadamente simples para este entorno interno: se acepta cualquier valor no vacío, incluido `1` o `1234`. Cambiarla es una opción del usuario, nunca una obligación. Administración dispone además de una gestión completa de cuentas: alta, edición de nombre/correo/roles/estado/contraseña, eliminación segura y restauración.

4.1.1 añade la migración no destructiva `0011_user_lifecycle_4_1_1` para soportar borrado lógico de usuarios sin romper el historial.

Desde 4.1.2 Administración ya no muestra ni solicita **Rol principal**. Solo se asignan **Roles y accesos**; todos son efectivos simultáneamente. El campo histórico `users.role` se mantiene únicamente por compatibilidad interna y la aplicación lo calcula automáticamente, sin afectar permisos. 4.1.2 no añade migraciones.


## 4.0.7 · XI observado reactivo

En el editor de alineaciones con formación conocida, cada jugador seleccionado se elimina automáticamente de los desplegables de las demás posiciones. Esto hace más rápida la identificación del XI y evita duplicados desde la propia interfaz. El botón **Guardar XI** conserva además la validación de servidor que impide guardar un jugador dos veces.

4.0.7 no introduce cambios de esquema. Mantiene el mismo Supabase y el head Alembic `0010_core_workspace_schema_repair_4_0_4`.

## 4.0.3 · Hotfix de esquema real

4.0.3 corrige el fallo observado en producción donde PostgreSQL llegaba a `Inicio` con una revisión Alembic aparente compatible pero faltaban columnas físicas que el ORM de `Match` intentaba seleccionar. La nueva revisión `0009_schema_repair_4_0_3` es idempotente y no destructiva: comprueba y restaura únicamente columnas aditivas esperadas, y después valida el contrato físico antes de renderizar cualquier workspace.

No cambia de Supabase ni reinicia datos. Mantén `RUN_MIGRATIONS = true` para que el hotfix se aplique automáticamente al reiniciar Streamlit Cloud.

## 4.0.1 · Match Study + hotfix de despliegue

La 4.0 convierte los partidos neutrales en una ficha de estudio flexible. El vídeo se marca como disponible/no disponible y cada equipo puede tratarse de forma independiente: **formación conocida → campograma**; **formación desconocida → plantilla de Federación ordenada por dorsal**. Ya no es necesario inventar un sistema para poder estudiar a un rival.

También añade pegado rápido de plantillas federativas, XI observado sobre campograma, filtro Scout por equipo, contexto visible desde Jornada y una migración no destructiva `0008_match_study_4_0`.

**4.0.2** endurece el despliegue real en Streamlit Cloud: el paquete se entrega con raíz plana y el arranque detecta archivos mezclados antes de importar la aplicación. 4.0.1 ya corrigió: elimina físicamente el directorio especial `pages/`, mueve las vistas a `views/`, robusteciendo la conexión PostgreSQL/Supabase y mostrando un diagnóstico seguro si `DATABASE_URL` no es accesible. Consulta `UPGRADE_4_0_1.md`.

## 3.9 · Matchday y fiabilidad

La 3.9 se centra en empezar a usar la aplicación con datos reales con menos riesgo operativo. El día de trabajo se calcula en `Europe/Madrid`, Jornada prioriza automáticamente la ronda de No Name, Inicio destaca el partido del día y Administración permite comprobar en segundos si temporada, calendario y plantilla están preparados.

También se corrigen dos restos importantes de la arquitectura antigua: Informes respeta todos los roles del usuario y la herramienta secundaria de calendario ya no propone una hora ficticia ni navega a módulos retirados.

Para la prueba de Jornada 1 consulta `PRUEBA_REAL_J1.md`.

## Datos y Supabase

4.1.1 mantiene el mismo Supabase, `DATABASE_URL` y Secrets. El head Alembic actual es `0011_user_lifecycle_4_1_1`. La migración es aditiva y conserva todos los datos existentes; no se incluyen datos demo.

## Validación

Consulta `VALIDACION_4_1_1.md`. La release está cubierta por `compileall`, suite automatizada completa, consistencia interna y migraciones fresh/upgrade.
## 4.0.5 · Hotfix de navegación

4.0.5 corrige la navegación desde tarjetas y tareas: las vistas ya no escriben directamente en el estado del widget `main_navigation` después de que Streamlit haya creado el radio lateral. La navegación se solicita mediante un estado pendiente y se aplica en el siguiente rerun antes de construir el widget. También protege PostgreSQL ampliando automáticamente la columna de versión de Alembic a 128 caracteres.
