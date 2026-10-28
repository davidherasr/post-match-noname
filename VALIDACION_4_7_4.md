# Validación 4.7.4

## Resultado local

- Pruebas automatizadas: ver el resultado registrado junto al ZIP entregado.
- `python -m compileall` y `python scripts/check_release_consistency.py`.
- Tests nuevos en `tests/test_release_4_7_4.py` de permisos, retirada y reposición de notas, incorporación de suplente, estadísticas, fusión y coherencia de versión.
- No se utilizaron contraseñas ni conexión a la base real del usuario.

## Aceptación manual pendiente en Streamlit Cloud

1. **Admin:** importar dos XI válidos (`dorsal;nombre;posición`), publicar, comprobar que antes no aparece la valoración para Informadores.
2. **Coloto:** abrir partido, valorar a Chuchi y tres compañeros; guardar; entrar de nuevo; editar una nota; retirarla; volver a puntuar. Verificar que las medias no acumulan tres notas para el mismo autor y partido.
3. **Consulta:** iniciar sesión con perfil Consulta y comprobar que no hay editor; intentar una escritura indirecta y verificar rechazo sin modificación de BD.
4. **Suplente:** tras publicar, incorporar un participante confirmado por nombre/dorsal/posición/minuto y comprobar que Coloto puede valorarlo sin sustituir titulares.
5. **Analista:** registrar 35/39 pases y 7/7 duelos para un jugador del encuentro, guardarlo de nuevo, comprobar revisión idempotente y que la media subjetiva no cambia.
6. **DD:** visualizar la evolución de Chuchi en ficha y plantilla, verificar la misma media, número de partidos e Informadores; comprobar privacidad del resto.
7. **Identidades:** ensayo de fusión con dos fichas ficticias y evidencia separada; comprobar que no desaparece el histórico y que una fusión conflictiva se rechaza.
8. **Móvil:** repetir en pantalla estrecha de teléfono, comprobar acceso a guardar y volver sin pérdida de estado.
9. **Regresión:** comprobar lectura de informes antiguos, propuestas a Aarón, solicitudes, correcciones administrativas y exportación.
10. **Rendimiento real:** verificar tiempos de carga de catálogo, ficha de jugador y plantilla con volumen de datos representativo, no con base vacía.

La batería automatizada no sustituye estos diez recorridos reales. Hasta completarlos, la 4.7.4 sigue siendo **candidata para probar**, no versión certificada en producción.
