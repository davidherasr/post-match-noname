# Dirección Deportiva 3.2 · Inteligencia de nuestra liga

La Dirección Deportiva de No Name PostMatch no intenta cubrir mercados internacionales. Se alimenta exclusivamente de los partidos e informes de nuestra competición y convierte esa información en decisiones acumuladas.

## Navegación

```text
Dirección deportiva
├── Panorama
├── Jugadores
├── Por posiciones
├── Equipos
├── Seguimiento
├── Comparador
├── XI de la liga
├── Consenso
├── Informes
└── Listas
```

## Panorama

Responde a cuatro preguntas:

1. ¿Cuántos jugadores de la liga conocemos?
2. ¿A quién hemos visto varias veces?
3. ¿Quién ha llamado la atención recientemente?
4. ¿Qué perfiles necesitan una decisión de Dirección Deportiva?

KPIs: jugadores observados, 2+ observaciones, seguimiento, prioritarios, equipos vistos e informes por revisar.

## Expediente 360

Cada rival dispone de un expediente construido solo con observaciones aprobadas:

- equipo actual observado;
- posición;
- media;
- tamaño de muestra;
- informadores distintos;
- última nota;
- dispersión;
- confianza;
- gráfico de evolución;
- observaciones partido a partido;
- conclusión de DD;
- prioridad;
- seguimiento;
- listas en las que aparece.

## Confianza

La nota se muestra siempre junto al tamaño de muestra. La aplicación clasifica la confianza en función de número de observaciones, número de informadores y dispersión. Un 8,5 en una sola observación no se presenta como equivalente a un 8,1 sostenido por varios informes.

## Rankings por posición

Los rankings se calculan mediante agregaciones SQL. Permiten comparar únicamente jugadores que ocupan el mismo rol y seleccionar un mínimo de observaciones.

## Rivales

Cada equipo de la liga reúne los futbolistas vistos, notas acumuladas, destacados y última alineación conocida. El objetivo no es un informe táctico del rival, sino saber qué jugadores de ese club han generado interés.

## Seguimiento

Agenda dividida en:

- vencidos;
- esta semana;
- próximos.

Cada seguimiento puede tener responsable, prioridad, próxima revisión, partido objetivo, nota y estado. El historial profundo solo se carga cuando el usuario lo solicita.

## XI de la liga

Se selecciona una formación y un mínimo de muestra. El sistema elige el mejor futbolista observado para cada posición sin repetir jugadores. El XI puede guardarse como lista y editarse después.

## Listas

Permiten construir listas cortas reales de la competición: delanteros interesantes, jugadores a revisar en segunda vuelta, prioridades, XI objetivo o cualquier selección propia.

## Consenso

Cuando varios informadores evalúan al mismo jugador en un partido, Dirección Deportiva ve media, dispersión, tamaño de muestra y nivel de consenso y puede guardar una nota final consolidada.

## Principio de uso

El cuerpo técnico no tiene que hacer trabajo adicional de scouting. Cada valoración postpartido alimenta automáticamente esta área. Al avanzar la temporada, el valor de Dirección Deportiva crece sin ampliar el formulario semanal.
