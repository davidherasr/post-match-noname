# No Name PostMatch 4.0.2

Aplicación interna de No Name para postpartido, scouting, Dirección Deportiva y planificación de plantilla. La capa visible se organiza en **Inicio · Jornada · Jugadores · Plantilla · Administración**, mientras la profundidad del modelo de datos queda detrás del contexto de trabajo.

## Flujo diario

- **Inicio**: lo que requiere atención, con Partido de hoy/Próximo partido y tareas.
- **Jornada**: calendario operativo, Match Hub, horarios, postpartido, scouting e informes.
- **Jugadores**: ficha única Player Report 360, evolución, Modelo No Name, decisión y próxima acción.
- **Plantilla**: roles, necesidades, referencias internas, candidatos y oportunidades de scouting.
- **Administración**: usuarios, club, datos, configuración y herramientas técnicas.

Los roles son capacidades acumulativas. No existe Perfil activo.

## 4.0.1 · Match Study + hotfix de despliegue

La 4.0 convierte los partidos neutrales en una ficha de estudio flexible. El vídeo se marca como disponible/no disponible y cada equipo puede tratarse de forma independiente: **formación conocida → campograma**; **formación desconocida → plantilla de Federación ordenada por dorsal**. Ya no es necesario inventar un sistema para poder estudiar a un rival.

También añade pegado rápido de plantillas federativas, XI observado sobre campograma, filtro Scout por equipo, contexto visible desde Jornada y una migración no destructiva `0008_match_study_4_0`.

**4.0.2** endurece el despliegue real en Streamlit Cloud: el paquete se entrega con raíz plana y el arranque detecta archivos mezclados antes de importar la aplicación. 4.0.1 ya corrigió: elimina físicamente el directorio especial `pages/`, mueve las vistas a `views/`, robusteciendo la conexión PostgreSQL/Supabase y mostrando un diagnóstico seguro si `DATABASE_URL` no es accesible. Consulta `UPGRADE_4_0_1.md`.

## 3.9 · Matchday y fiabilidad

La 3.9 se centra en empezar a usar la aplicación con datos reales con menos riesgo operativo. El día de trabajo se calcula en `Europe/Madrid`, Jornada prioriza automáticamente la ronda de No Name, Inicio destaca el partido del día y Administración permite comprobar en segundos si temporada, calendario y plantilla están preparados.

También se corrigen dos restos importantes de la arquitectura antigua: Informes respeta todos los roles del usuario y la herramienta secundaria de calendario ya no propone una hora ficticia ni navega a módulos retirados.

Para la prueba de Jornada 1 consulta `PRUEBA_REAL_J1.md`.

## Datos y Supabase

4.0.2 mantiene el mismo Supabase y el mismo head Alembic `0008_match_study_4_0`. Se conservan `DATABASE_URL`, Secrets y todos los datos existentes. No se incluyen datos demo.

## Validación

Consulta `VALIDACION_4_0_2.md`. La release está cubierta por `compileall`, suite automatizada completa, consistencia interna y migraciones fresh/upgrade.
