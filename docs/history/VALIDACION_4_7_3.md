# Validación local de 4.7.3

## Pruebas ejecutadas

- `pytest -q`: **248 pruebas superadas**, incluidas pruebas de permisos, doble XI obligatorio, parser estricto, estado privado, permiso explícito para valorar, edición idempotente, seguridad de IDs, no mezclar suplentes con participantes y migración de SQLite desde un esquema 0015 anterior.
- `python -m compileall -q .`: compilación completa sin errores.
- `python scripts/check_release_consistency.py`: verificación de versión y head `0019_rating_release_4_7_3`.
- **Previsualización del campo** generada por `ui/lineup473.py`: probada en Chromium a 390 px, once marcadores, sin desbordamiento horizontal; esta prueba es del SVG, no de la app Streamlit.
- ZIP comprobado con CRC; sin bytecode ni archivos temporales.

## Pruebas pendientes en despliegue

1. Abrir un partido no publicado como Coloto: no debe ofrecerse la valoración.
2. Intentar publicar con solo 10 titulares de cada equipo, o sin posición: bloqueo y mensaje.
3. Pegar 11 titulares por equipo en CSV válido, confirmar; ambos deben quedar asociados a sus equipos, sin duplicaciones.
4. Valorar a Chuchi y a un jugador del rival con usuario Informador; guardar sin nota colectiva.
5. Modificar la puntuación anterior: contar una sola observación vigente del mismo autor/partido/jugador.
6. Verificar como Aarón que ambas notas aparecen con sus fuentes, pero que Coloto no puede leer las opiniones de Roma.
7. Marcar favorito expresamente: aparece propuesta a DD; nota alta sin favorito no crea propuesta.
8. Intentar publicar como Informador ocasional: no autorizado. Probar permiso delegado de Analista y Director.
9. Partidos aplazados, jugadores homónimos, nombres corregidos y CSV Windows-1252.
10. Intentar reemplazar un XI después de publicación: debe bloquearse para proteger las valoraciones.

## Límites de esta validación

No se ha levantado la aplicación Streamlit real en un navegador porque Streamlit no está instalado en este entorno. No se ha ejecutado una migración sobre PostgreSQL/Supabase remoto. Los tests y la vista previa aislada **no sustituyen** pruebas de autenticación y flujo real en Cloud.
