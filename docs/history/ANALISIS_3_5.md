# No Name PostMatch 3.5.0 · Planning & Scouting

## Objetivo

Cerrar todo el circuito que hasta 3.4.1 empezaba después del partido. En 3.5 la aplicación conoce la temporada completa, permite planificar qué merece ser visto y transforma esas observaciones en decisiones concretas para el Modelo No Name.

## Cambios principales

1. Calendario completo de toda la liga, no solo No Name.
2. Importación masiva por texto con fin de semana conocido y hora pendiente.
3. Confirmación posterior de fecha/hora sin recrear el partido.
4. Incidencias de horarios próximos pendientes.
5. Partido programado de No Name reutilizado como postpartido.
6. Partidos neutrales entre rivales disponibles para scouting.
7. Nuevo perfil operativo Scout.
8. Usuarios con varios perfiles simultáneos y selector de perfil activo.
9. Agenda Scout de jornada.
10. Misiones DD sobre jugador, varios jugadores, equipo o análisis rival.
11. Observaciones Scout específicas repetibles por jugador/scout/partido.
12. Scouting espontáneo de cualquier encuentro de la liga.
13. Informe estructurado de equipo/rival.
14. Separación visible entre evidencia postpartido y evidencia específica.
15. Modelo No Name configurable por Dirección Deportiva.
16. Criterios ponderados por rol.
17. Necesidades de plantilla por temporada.
18. Plantilla sombra por rol.
19. Decisiones de jugador históricas por temporada.
20. Planificación que cruza necesidad + candidato + próximo partido.
21. Comparador DD orientado al Modelo No Name.
22. Seguimiento más operativo con partido objetivo y acciones rápidas.
23. Posición de entrada en sustitución editable.
24. Botones rápidos 5–9 en valoración postpartido.
25. Minutos insuficientes diferenciados de una valoración 0.
26. Inicio DD y Panorama consumen tendencias/cola robustas comunes.
27. Centro de calidad de datos en Administración.
28. Cierre de sesión limpia todo el estado operativo.
29. Búsqueda/paginación de jugadores trasladada a SQL en vistas densas.
30. Evidencia Scout mostrada sin alterar artificialmente la media postpartido.

## Principio Scout

El Scout no sustituye al Informador.

- **Informador:** hace el informe postpartido de No Name con rapidez.
- **Scout:** puede observar cualquier partido de la liga y profundiza donde DD ha identificado una necesidad o un jugador interesante.

Un usuario puede tener ambos perfiles.

## Valor añadido

La aplicación puede responder ahora a tres preguntas distintas:

1. ¿Qué pasó contra nosotros?
2. ¿Qué jugador merece que vayamos a verlo específicamente?
3. ¿Para qué rol de nuestro modelo lo estamos observando y qué necesidad cubriría?
