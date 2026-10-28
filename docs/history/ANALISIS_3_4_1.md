# No Name PostMatch 3.4.1 · Quality of Life

La 3.4.1 no amplía el modelo de datos. Su objetivo es reducir clics en los dos flujos más frecuentes: preparar el partido y completar informes.

## 1. Configuración habitual automática

Al iniciar un postpartido nuevo, si ya existe un partido de la temporada activa, se reutilizan automáticamente la competición, la formación de No Name y los informadores asignados. Rival, resultado, fecha y campo siguen vacíos para evitar arrastrar información incorrecta.

## 2. Borrador accesible desde Inicio

Administración muestra el borrador de postpartido más reciente y permite continuar directamente. Al abrirlo se recupera el payload guardado en Supabase y se continúa sobre ese mismo borrador.

## 3. Valoración más dirigida

Cada equipo muestra un progreso de jugadores valorados y pendientes. El filtro `Solo pendientes` utiliza el último estado guardado para que un jugador no desaparezca mientras se está escribiendo su comentario.

## 4. Menos clics en Dirección Deportiva

Cada jugador de la bandeja `Necesitan una decisión` incorpora acceso directo a su expediente 360, manteniendo el foco en convertir observaciones en decisiones.

## Compatibilidad

No hay migración nueva ni cambios destructivos. Se mantiene la revisión `0004_scout_workflow_3_3`.
