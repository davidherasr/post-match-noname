# Validación técnica · No Name PostMatch 3.6.0

## Resultado

- Compilación Python completa: **correcta**.
- Suite automatizada: **42 pruebas superadas**.
- Contrato de versión: **3.6.0**.
- Alembic head: **`0006_player_report_360_3_6`**.
- Release consistency: **correcta**.
- Bases `.db`, `.sqlite`, `.sqlite3` incluidas en release: **0**.
- Datos deportivos de demostración incluidos: **0**.

## Migraciones verificadas

Se han comprobado dos escenarios con bases temporales:

1. base vacía → `alembic upgrade head` → 0006;
2. base en revisión 0005 → `alembic upgrade head` → 0006.

La migración 0006 añade únicamente a `player_season_decisions`:

- `current_level`;
- `potential_score`;
- `criteria_json`.

No elimina ni reinicia información existente.

## Cobertura específica 3.6

La suite incorpora pruebas de:

- construcción del Player Report 360 con datos reales de postpartido y scouting;
- criterios del Modelo No Name sin completar valores inexistentes;
- decisión DD por temporada con encaje, nivel, proyección y criterios;
- comparación con futbolistas de la plantilla propia asignados al mismo rol;
- generación de Ficha Scout Ejecutiva PDF;
- generación de Dossier Player Report 360 PDF.

Se conservan las pruebas anteriores de calendario completo, horarios, multirol, perfil Scout, misiones, scouting espontáneo, observaciones múltiples, análisis rival, Modelo No Name, plantilla sombra, calidad de datos, bulk UPSERT, dirty state, informes, DD, seguridad y migraciones.

## Verificación visual de PDF

Los dos nuevos documentos se generaron con un dataset temporal fuera de la release y se renderizaron a imagen para inspección visual:

- Ficha Scout Ejecutiva: 1 página;
- Dossier Player Report 360: 2 páginas en la muestra de validación.

Se comprobó ausencia de texto recortado, solapamientos, glifos rotos y valores inventados. Los archivos de demostración y sus renders **no se incluyen en el ZIP final**.

## Limitación realista

La latencia exacta de Streamlit Community Cloud ↔ Supabase solo puede medirse después del despliegue real. La aplicación mantiene las herramientas de rendimiento y aceptación con rollback de versiones anteriores.
