# Auditoría y mejoras implementadas · No Name PostMatch 3.2.0

## Objetivo

Reducir el tiempo de preparación y evaluación y convertir Dirección Deportiva en una herramienta completa de **nuestra liga**, sin funcionalidades internacionales que no aportan valor.

## 25 mejoras aplicadas

1. **Postpartido en memoria:** preparar partido y alineaciones ya no implica escribir cada paso en PostgreSQL.
2. **Publicación transaccional:** partido, alineaciones y asignaciones se confirman conjuntamente al publicar.
3. **Borrador remoto opcional:** solo se sincroniza cuando el administrador pulsa Guardar borrador.
4. **Catálogos cacheados por sesión:** temporada, competiciones, rivales e informadores no se recargan en cada interacción.
5. **Plantilla propia cacheada:** se consulta una vez durante la preparación del partido.
6. **Último XI cacheado:** reutilización del partido anterior sin repetir lecturas.
7. **Último rival cacheado:** su última alineación conocida se carga bajo demanda y se reutiliza.
8. **Formaciones estructurales:** cada sistema crea automáticamente las once posiciones esperadas.
9. **Sugerencia automática de XI:** se prioriza el último once y después la posición principal de la plantilla.
10. **Cambios naturales:** `minuto · sale · entra`, derivando automáticamente minutos individuales.
11. **Rival sin roster previo:** los jugadores pueden escribirse directamente y se crean/resuelven al publicar.
12. **Pegado rápido rival:** nombres, dorsal+nombre o formato separado por `;`.
13. **Guardado rápido de alineación rival:** precarga de jugadores, alta de nuevos y sincronización masiva de plantilla.
14. **Informe como workspace:** partido, participantes y evaluaciones se cargan de forma conjunta.
15. **Cero escrituras durante la edición:** sliders y comentarios viven en el formulario hasta Guardar.
16. **Bulk save por equipo:** No Name y rival se sincronizan por bloques.
17. **Sin rerun obligatorio después de guardar notas:** se puede continuar trabajando inmediatamente.
18. **Rankings en SQL:** medias, muestra, informadores y destacados se agregan en PostgreSQL.
19. **Bandeja de revisión batch:** se eliminan consultas de evaluaciones/documentos informe por informe.
20. **Carga lazy de históricos:** comentarios, documentos y seguimiento profundo solo se consultan al pedirlos.
21. **Búsqueda global de catálogo:** equipos/jugadores desde una sola entrada de mantenimiento.
22. **Plantilla editable en lote:** dorsales, actividad y fechas se modifican y guardan conjuntamente.
23. **PDF Resumen como documento diario:** el dossier completo no penaliza cada entrega.
24. **Accesibilidad reforzada:** foco, contraste, targets táctiles, responsive y lenguaje simplificado.
25. **Dirección Deportiva de liga:** panorama, rankings por posición, rivales, seguimiento, comparador, XI, consenso, listas y expedientes 360.

## Dirección Deportiva: principio de diseño

No se muestran mapas, países ni mercados internacionales. La pregunta de producto es:

> De todos los jugadores contra los que hemos jugado, ¿quién nos ha llamado la atención, cuántas veces, con qué consenso y qué debemos hacer a continuación?

Por eso la información principal es muestra, nota, evolución, equipo, posición, destacados, dispersión, confianza, seguimiento y decisión de DD.
