# Validación y límites · 4.4.4

**Fuente exclusiva:** ZIP completo 4.4.3, extraído en una copia aislada de trabajo. **Sin acceso ni cambios en Supabase productivo.**

## Pruebas de regresión añadidas

Se incorporaron siete pruebas sobre selección explícita frente a descubrimiento por nota/muestra, navegación DD con clave lógica independiente del widget, estado del selector de temporada/jornada, confirmación de una lectura neutral (sin botón inhabilitado dentro del formulario), lectura neutral voluntaria y reutilización de su registro, filtro de jornada en SQL antes de paginar, y comprobaciones estructurales de PDF/CSS/archivo. También se actualizaron dos pruebas anteriores cuyos literales suponían una maquetación deliberadamente sustituida; no se eliminaron pruebas existentes.

## Pruebas locales ejecutadas

- `pytest -q`: **162 superadas** después de corregir una coincidencia no deseada entre «Jornada 1» y «Jornada 10–19» que se detectó durante las pruebas.
- `python -m compileall -q`: sintaxis sin errores.
- `python scripts/check_release_consistency.py`: coherencia de versión y migración objetivo 0015.
- Alembic en SQLite temporal: instalación desde cero a `0015_observation_requests_4_4_3`, tres tablas de peticiones presentes. Una actualización desde BD ya en 0015 no ejecuta nuevos scripts.
- PDF generado con nombre largo y observación de más de 1500 caracteres; se extrajo el texto y se renderizó a imagen, donde se revisó la página de evolución. Se encontró y corrigió además un nombre que invadía la columna siguiente en la tabla «Datos disponibles», verificando nuevamente la imagen.
- ZIP íntegro con archivos completos y documentación; revisar la salida de verificación final y la ejecución repetida de pruebas tras extraer el ZIP antes de distribuirlo.

## Pendiente de validar en entorno de usuario

Streamlit **no está instalado en este entorno de pruebas**. No se ha reproducido aquí una sesión del navegador de Cloud ni capturas de todas las rutas. Queda pendiente validar el fallo exacto de `StreamlitWidgetAlreadyInstantiatedError` contra el runtime, diferentes anchuras y zoom/teclado, una lectura neutral con usuario real, señal y PDF productivo, el rendimiento de DD con muchos registros y PostgreSQL aislado a partir de un backup real. No declarar Cloud validado a partir de los tests locales.

## Límite del rediseño visual

Se incluyen correcciones concretas en Inicio, DD, Jornada, Informes, formularios, Player360, ficha de equipo, CSS y PDF. **No** se ha ejecutado todavía un recorrido de todos los tamaños/permisos en navegador ni una auditoría accesible con lector de pantalla. Las herramientas de eliminación física no se han utilizado ni se han cambiado sus condiciones de seguridad. Una modificación del tema nativo de Streamlit mediante color personalizado aún requiere ensayo en Cloud para garantizar paridad con el CSS dinámico.
