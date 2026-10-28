# Auditoría 3.3 · 19 mejoras aplicadas

No Name PostMatch 3.3 consolida la 3.2 y trabaja sobre cuatro objetivos: **menos tiempo**, **menos consultas**, **mejor calidad de datos** y **un último escalón scout real para Dirección Deportiva**.

## 1–19

1. **Informe compacto**: el informador ve nombre, metadatos bloqueados, nota y observación; Destacado/PDF permanece oculto por defecto.
2. **Cambios sin guardar**: el flujo es secuencial No Name → Rival → Entregar; no se puede avanzar a la entrega sin guardar el bloque actual.
3. **UPSERT SQL real**: las evaluaciones de una plantilla se insertan/actualizan con una única sentencia `ON CONFLICT DO UPDATE` en PostgreSQL/SQLite.
4. **Último XI automático**: al seleccionar estructura se propone de entrada el último XI disponible y, después, la posición principal.
5. **Identidad rival segura**: la resolución prioriza equipo+temporada, después alias y solo reutiliza coincidencias globales inequívocas; los homónimos no se fusionan silenciosamente.
6. **Posición observada**: rankings e inteligencia utilizan la posición de la participación en el partido, no únicamente `primary_position`.
7. **XI de la liga mejorado**: criterios por media, confianza, forma reciente o selección DD; mínimo de muestra y sustitución manual de propuestas.
8. **Tendencias robustas**: compara medias iniciales/recientes con muestra mínima y dispersión, en lugar de primera vs última nota.
9. **Confianza explicable**: puntuación 0–100 con muestra, informadores, dispersión y recencia, además de etiqueta Alta/Media/Baja.
10. **Bandeja de decisiones DD**: razones explícitas como destacados repetidos, media alta, muestra sin decisión u opiniones divididas.
11. **Dossier de rival**: jugadores conocidos, destacados, seguimientos, prioritarios y último enfrentamiento conocido.
12. **Base de datos simplificada**: país, nacionalidad, pie, fecha de nacimiento, imágenes y otros metadatos secundarios pasan a Datos avanzados; la vista diaria se centra en nombre, posición, temporada y equipo.
13. **Backup bajo demanda**: no se prepara un ZIP técnico al entrar en la pantalla; solo al solicitarlo.
14. **Archivo de informes lazy**: se filtra por temporada, estado, rival e informador y el workspace solo se carga tras pulsar Abrir informe.
15. **Índices PostgreSQL**: migración 0004 añade índices compuestos para partidos, evaluaciones, informes, participaciones, asignaciones, seguimientos, plantillas y scouting.
16. **Instrumentación de rendimiento**: tiempos de workspace, guardado, publicación, archivo, PDF y DD se registran en sesión para diagnóstico sin añadir escrituras a la base.
17. **Deuda técnica reducida**: inteligencia de liga y scouting avanzado viven en repositorios separados; se eliminan definiciones duplicadas antiguas del generador de informes; la validación de postpartido pasa a un módulo puro independiente de Streamlit.
18. **Pruebas ampliadas**: flujo scout, bulk upsert, posición observada, confianza, tendencia y validación de publicación se incorporan a la suite.
19. **Accesibilidad/móvil**: inputs a 16px, targets táctiles, formularios más compactos, navegación selectbox en áreas densas, foco visible y reducción de contenido secundario.

## Nueva capa scout

El informe postpartido **no se vuelve más complejo**. El cuerpo técnico sigue puntuando rápido. Dirección Deportiva decide qué jugador merece pasar al siguiente nivel:

`Observado → Candidato → Ficha solicitada → En revisión → Ojeado / Archivado`

La ficha avanzada permite:

- posición y rol dentro del modelo de No Name;
- encaje, nivel actual y proyección;
- asignación a un informador;
- valoración técnica/táctica/física/mental opcional;
- atributos específicos por posición, también opcionales;
- fortalezas, riesgos, resumen y recomendación;
- conclusión final y decisión de Dirección Deportiva.

El principio es deliberado: **el postpartido detecta; Dirección Deportiva profundiza solo donde hay interés**.
