# Validación técnica — PostMatch Scout 2.0

Fecha de validación: 4 de agosto de 2026.

## Alcance comprobado

- 41 módulos Python y aproximadamente 6.286 líneas de código.
- Compilación completa mediante `python -m compileall -q .`.
- 8 pruebas automatizadas superadas con `pytest -q`.
- Migración inicial Alembic aplicada desde una base vacía y confirmada en `head`.
- 23 tablas creadas correctamente en la prueba de migración.
- Flujo de muestra con dos informadores, entrega, aprobación, snapshot inmutable y PDF.
- PDF completo y ejecutivo generados y abiertos correctamente.
- Preflight PDF: no cifrados, no escaneados, sin XFA y legibles mediante PyMuPDF.
- Renderizado visual de las 7 páginas del PDF completo y 5 páginas del ejecutivo.
- Plantilla XLSX creada con `artifact_tool`, tres hojas, tablas, listas desplegables y sin errores de fórmula.
- Backup técnico ZIP generado y restaurado sobre una base SQLite vacía, conservando usuarios, temporadas, competiciones, equipos y partidos.

## Resultado de pruebas

```text
8 passed
```

Las pruebas cubren:

- política de contraseña y bloqueo por intentos fallidos;
- normalización Unicode;
- validación de importaciones;
- detección y fusión de duplicados;
- exclusión de borradores y valoraciones propias de las analíticas;
- snapshots inmutables;
- rankings solo con informes aprobados;
- generación de PDF;
- control optimista de concurrencia;
- reconciliación entre alineaciones y evaluaciones.

## PDF

```text
Completo:   7 páginas · 71.636 bytes
Ejecutivo:  5 páginas · 66.198 bytes
```

Se revisaron visualmente portada, campos de formación, alineaciones, fichas individuales y página metodológica. No se detectaron textos cortados, solapamientos ni glifos rotos en las muestras generadas.

## Migraciones

```text
0001_initial_2_0 (head)
23 tablas creadas
```

## Backup y restauración

Se creó una copia técnica con datos de prueba y se restauró en otra base vacía. Conteos verificados tras la restauración:

```text
usuarios:       1
temporadas:     1
competiciones:  1
equipos:        2
partidos:       1
```

## Limitación de esta validación

El entorno de construcción no dispone del paquete `streamlit`, por lo que no se realizó una prueba end-to-end de navegador ni una validación visual de todas las pantallas interactivas. Los módulos compilan, la lógica de datos, migraciones, importación, exportación, seguridad, versionado, PDF y restauración han sido ejecutados. Tras instalar `requirements.txt`, queda pendiente la aceptación final en navegador y la prueba contra el proyecto PostgreSQL/Supabase definitivo.
