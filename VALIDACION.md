# Validación técnica - PostMatch Scout 2.1

Fecha de validación: 4 de agosto de 2026.

## Alcance comprobado

- 43 módulos Python y aproximadamente 6.702 líneas de código.
- Compilación completa mediante `python -m compileall -q .`.
- 12 pruebas automatizadas superadas con `pytest -q`.
- Flujo de muestra con dos informadores, valoraciones simplificadas, entrega, aprobación y snapshot inmutable.
- Entrega válida sin impresión general del rival.
- Automatismo de destacado a partir de 8,0.
- Inclusión en PDF predeterminada y anulable manualmente.
- Sincronización automática del MVP rival.
- PDF completo y ejecutivo generados y abiertos correctamente.
- Preflight PDF correcto: documentos no cifrados, no escaneados y sin XFA.
- Renderizado visual de 7 páginas del PDF completo y 4 páginas del ejecutivo.
- Tablas PDF adaptadas al nuevo modelo, sin columnas vacías de decisión o confianza.

## Resultado de pruebas

```text
12 passed
```

Las pruebas cubren:

- seguridad y bloqueo de accesos;
- normalización de nombres;
- importaciones;
- duplicados y fusión;
- exclusión de borradores y valoraciones propias de las analíticas;
- snapshots inmutables;
- generación PDF;
- control de concurrencia;
- reconciliación de alineaciones;
- nota cero como no observado;
- destacado automático;
- anulación manual de checks;
- entrega sin resumen general.

## PDF

```text
Completo:   7 páginas - 67.809 bytes
Ejecutivo:  4 páginas - 59.282 bytes
```

Se revisaron visualmente la portada, el resumen rival, las alineaciones y las fichas individuales. No se detectaron textos cortados, solapamientos ni glifos rotos.

## Base de datos

La versión 2.1 utiliza el mismo esquema que la versión 2.0. No requiere una migración adicional y conserva la revisión Alembic:

```text
0001_initial_2_0 (head)
```

## Limitación de esta validación

El entorno de construcción no dispone del paquete `streamlit`, por lo que no se ejecutó una prueba end-to-end de navegador. La instalación del paquete tampoco fue posible desde el índice disponible en este entorno. La sintaxis, lógica de datos, reglas automáticas, pruebas, PDF, importaciones y persistencia han sido comprobadas. Queda pendiente la prueba visual final después del despliegue en Streamlit Community Cloud.
