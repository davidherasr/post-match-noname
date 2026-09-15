# No Name PostMatch 4.2.1

Aplicación interna de No Name para postpartido, lectura compartida del staff, Dirección Deportiva y seguimiento individual de jugadores externos. La capa visible se organiza en **Inicio · Jornada · Jugadores · Dirección Deportiva · Administración**.

## Flujo diario 4.2

- **Inicio**: partido de hoy/próximo partido y acciones pendientes.
- **Jornada**: distingue de forma explícita entre partidos de No Name y partidos neutrales.
- **Jugadores**: Player Report 360, evolución y seguimiento individual cuando exista evidencia real.
- **Dirección Deportiva**: lectura agregada del staff, pesos de opinión, Modelo No Name, plantilla y candidatos.
- **Administración**: usuarios, roles, calendario, equipos, plantillas, calidad de datos y configuración.

Los roles organizativos son **Administrador · Dirección Deportiva · Informador**. El seguimiento individual de jugadores **no es un rol Scout**: es un permiso adicional `Puede realizar seguimiento individual de jugadores`, activable solo para quienes realmente hagan ese trabajo.

## 4.2.1 · Lectura transversal de Dirección Deportiva

La lectura deportiva ya no se limita al partido abierto. Dirección Deportiva dispone de una capa de **inteligencia de liga** construida únicamente con datos introducidos por el staff:

- jugadores externos que empiezan a repetirse entre partidos;
- número de partidos y señales, personas que los señalaron y nota ponderada por el peso deportivo de cada miembro;
- tendencia entre primeras y últimas apariciones;
- equipos rivales con evidencia acumulada;
- discrepancias localizadas por partido, equipo o jugador con etiquetas de consenso legibles;
- acceso directo desde Inicio a `Lectura deportiva → Jugadores señalados`.

Los permisos también quedan cerrados por responsabilidad: **Administrador** mantiene datos y usuarios, **Dirección Deportiva** interpreta la información y **Informador** es el único rol que habilita la escritura de valoraciones y postpartidos. Los roles pueden combinarse. El permiso `Puede realizar seguimiento individual de jugadores` sigue siendo independiente.

La 4.2.1 no añade esquema nuevo; utiliza la migración `0012_sporting_reading_4_2`. Los históricos de antiguas misiones se conservan en base de datos, pero ya no forman parte de los workspaces ni de las vistas activas.

## 4.2 · Lectura deportiva real

4.2 elimina el flujo artificial de `DD → asignar Scout → misión`. El trabajo se adapta a la estructura real del staff:

- **Partidos de No Name**: son postpartidos. Cada Informador puntúa el rendimiento colectivo de No Name, el rival y los jugadores que realmente haya podido valorar. Dirección Deportiva obtiene consensos ponderados, discrepancias y evolución. Los jugadores propios se tratan siempre como **rendimiento de plantilla**, nunca como objetivos de mercado.
- **Partidos neutrales**: cada miembro del staff deja una lectura ligera del partido, puntúa a ambos equipos y puede señalar jugadores que le hayan llamado la atención. Señalar un jugador genera una **señal**, no un seguimiento automático.
- **Dirección Deportiva**: dispone de un centro propio con tres áreas: `Lectura deportiva`, `Plantilla y modelo` y `Criterio del staff`. Puede dar más o menos peso a cada persona según se trate de partidos de No Name o partidos neutrales.
- **Seguimiento individual**: solo aparece a usuarios con el permiso especial. Desde una señal de DD o desde un partido se puede iniciar seguimiento de un jugador externo y alimentar su Player Report 360. El sistema impide abrir como objetivo de mercado a un jugador de No Name.
- **Administración**: ya no reparte trabajo deportivo. Prepara usuarios, datos, plantillas, calendario y horarios.

La migración no destructiva `0012_sporting_reading_4_2` añade el permiso individual, los pesos deportivos del staff, las lecturas de partidos neutrales y las notas colectivas No Name/rival. Los antiguos registros Scout se conservan como histórico y los usuarios con rol Scout heredado se convierten a **Informador + permiso de seguimiento individual**.

Las contraseñas siguen siendo deliberadamente libres para este entorno interno: cualquier valor no vacío es válido y cambiarlo es opcional.

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
