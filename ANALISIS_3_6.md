# No Name PostMatch 3.6.0 · Player Report 360

## Objetivo

La 3.6 no intenta convertir No Name PostMatch en una plataforma profesional de datos. Su objetivo es presentar de forma mucho más clara y profesional la información que **No Name realmente ha recogido** mediante postpartidos, observaciones Scout, Modelo No Name y decisiones de Dirección Deportiva.

El principio es estricto: **si un dato no existe, no se inventa**. No se estiman valor de mercado, altura, estadísticas, nacionalidad, comparables externos ni atributos que ningún miembro del staff haya valorado.

## Cambios principales

1. **Player Report 360 en pantalla** dentro de Jugadores ojeados, con navegación por Resumen, Modelo No Name, Evolución, Observaciones, Comparativa, Datos y Decisión DD.
2. **Cabecera profesional** con jugador, equipo, posición, rol No Name y tres KPI principales: rendimiento observado, encaje No Name y confianza.
3. **Resumen ejecutivo** con conclusión consolidada, fortalezas, dudas/riesgos, recomendación, nivel actual y proyección.
4. **Radar del Modelo No Name** generado únicamente cuando existen al menos tres criterios reales puntuados para el rol elegido.
5. **Criterios clave ponderados** por rol, con bloque, peso y puntuación real.
6. **Separación entre rendimiento observado y perfil Scout**: una buena actuación no se presenta como equivalente a un buen encaje en el modelo.
7. **Evolución conjunta** de postpartidos y observaciones Scout, conservando fuente, partido, posición, nota, observador y apunte.
8. **Posiciones observadas** para diferenciar la posición principal administrativa de dónde ha sido realmente evaluado el jugador.
9. **Evidencia explicable**: muestra, informadores, consenso/dispersion, recencia y fuerza de scouting específico.
10. **Comparativa interna** con jugadores de la plantilla de No Name asignados al mismo rol del modelo.
11. **Perfiles similares de nuestra liga**, calculados solo sobre jugadores realmente conocidos y criterios/encaje existentes; no se comparan con futbolistas externos inventados.
12. **Decisión DD por temporada** ampliada con nivel actual, proyección y puntuaciones de criterios del Modelo No Name.
13. **Mapeo de la plantilla propia al Modelo No Name**, para que la plantilla sombra pueda comparar candidatos externos con referencias internas reales.
14. **Ficha Scout Ejecutiva PDF**, pensada para lectura rápida y normalmente de una página.
15. **Dossier Player Report 360 PDF**, con evolución, observaciones, posiciones, modelo, comparativa y datos disponibles.
16. **Diseño responsive** para que la misma jerarquía funcione en escritorio y móvil.

## Qué no se ha añadido deliberadamente

- estadísticas externas automáticas;
- valor de mercado estimado;
- altura/peso inventados;
- nacionalidad inferida;
- comparables con estrellas o jugadores de otras ligas sin una base real;
- radares rellenados con valores neutros cuando faltan observaciones;
- docenas de atributos obligatorios.

## Flujo de producto

```text
POSTPARTIDO + SCOUTING ESPECÍFICO
                ↓
       EVIDENCIA DEL JUGADOR
                ↓
        MODELO NO NAME
       rol + criterios reales
                ↓
      PLAYER REPORT 360
                ↓
   DECISIÓN DIRECCIÓN DEPORTIVA
                ↓
 seguimiento · prioritario · archivo
```

## Base de datos

La 3.6 incorpora la migración aditiva y no destructiva `0006_player_report_360_3_6`.

Añade a `player_season_decisions`:

- `current_level`;
- `potential_score`;
- `criteria_json`.

No elimina ni transforma datos previos. Calendario, roles Scout, misiones, observaciones, informes, jugadores y decisiones existentes continúan en el mismo Supabase.
