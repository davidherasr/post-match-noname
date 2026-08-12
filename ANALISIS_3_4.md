# Auditoría cerrada · No Name PostMatch 3.4.0

La 3.4 no añade otra capa de producto: termina de verdad los puntos que habían quedado parciales en 3.3.

## 19/19

1. **Informe compacto**: modo rápido por defecto. Cada jugador queda reducido a identidad/metadatos, slider y comentario. Destacado/PDF viven en `Más opciones`.
2. **Cambios sin guardar reales**: cada bloque mantiene snapshot guardado y estado `dirty`; aparece aviso y no se permite abandonar el bloque hasta guardar o deshacer.
3. **UPSERT masivo**: se mantiene el `INSERT ... ON CONFLICT DO UPDATE` por plantilla.
4. **Último XI automático**: se mantiene como propuesta por defecto al preparar No Name.
5. **Identidad rival segura**: resolución por equipo+temporada, alias, DOB cuando exista y panel de desambiguación cuando haya varios candidatos. La opción `Crear nuevo para este rival` evita fusiones forzadas.
6. **Posición observada**: rankings y XI usan la posición real de la participación.
7. **XI de liga avanzado**: media/confianza/forma/selección DD + muestra mínima + confianza mínima + seguimiento/prioridad + sustitución manual.
8. **Tendencias robustas**: mínimo 4 observaciones y ventanas inicial/reciente no solapadas; se muestran variabilidad y fiabilidad.
9. **Confianza explicable**: 0–100 desglosado en Muestra (40), Informadores (20), Consenso (25) y Recencia (15).
10. **Bandeja DD**: además de destacados/media/desacuerdo, alerta por seguimiento vencido y prioritarios sin observar durante demasiado tiempo.
11. **Dossier rival**: último XI conocido, perfiles de mayor interés y jugadores que mejor conocemos.
12. **Base diaria simple**: los campos secundarios siguen en Datos avanzados.
13. **Backup bajo demanda**: Administración no recorre la base al entrar; solo al pulsar `Preparar backup técnico`.
14. **Archivo lazy completo**: temporada, rival, informador, estado y jornada; el workspace solo se carga al abrir un informe.
15. **Índices PostgreSQL**: se conservan los índices de 0004; no se requiere nueva migración.
16. **Rendimiento medible**: instrumentación SQLAlchemy separa `total_ms`, `db_ms`, `render_ms` y `queries`, con resumen de cuellos de botella.
17. **Deuda técnica**: `repositories/scouting.py` baja de ~2333 a ~1462 líneas y se extraen `users.py`, `players.py`, `matches.py`, `reports.py`. `services/report_service.py` pasa a ser una fachada de 19 líneas y los PDF se dividen en `reports/payload.py`, `reports/summary_pdf.py` y `reports/full_pdf.py`.
18. **Aceptación real preparada**: Administración incluye una prueba contra la DATABASE_URL real que ejecuta partido → bulk evaluation → aprobación → ranking por posición → ficha scout dentro de un SAVEPOINT y revierte todo. También existe `scripts/live_acceptance.py` para terminal.
19. **Móvil/accesibilidad**: el informe usa `st.fragment`, menos tarjetas, menos altura, controles táctiles, fuentes ≥16px y disposición que colapsa de forma limpia en móvil.

## Principio 3.4

El usuario trabaja localmente; PostgreSQL solo aparece cuando hay que leer el workspace inicial o confirmar una operación. Dirección Deportiva recibe información procesada y accionable, no tablas crudas.
