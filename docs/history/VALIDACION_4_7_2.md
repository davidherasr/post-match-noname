# Validación de No Name · Área Técnica 4.7.2

**Ejecutado en este entorno**

- `pytest -q`: **232 pruebas superadas**, incluidas 11 pruebas específicas del nuevo flujo en `tests/test_release_4_7_2.py`.
- `compileall`: todos los módulos Python nuevos compilan.
- `scripts/check_release_consistency.py`: revisión coherente 4.7.2; Alembic esperado `0018_workspaces_4_7`.
- **Chromium, componente móvil independiente:** selección colectiva 7/10, Chuchi 8/10, texto, favorito, pulsación Guardar y estructura enviada al callback; sin desbordamiento horizontal a 390 px.
- **Chromium, editor de postpartido independiente:** editar dos comentarios y verificar que Guardar borrador manda `publish=false` y Compartir manda `publish=true`; sin desbordamiento horizontal.

**No ejecutado:** sesión completa de Streamlit Cloud con PostgreSQL real, autenticación, permisos efectivos en navegador y datos históricos productivos. La validación de los componentes sueltos no equivale a una prueba end-to-end de toda la aplicación.

## Prueba funcional que debe realizarse en la app desplegada

| Prueba | Cuenta | Resultado esperado |
|---|---|---|
| Móvil 390 px, solo puntuación | Coloto/Diego/Viti | Abrir último partido, poner 7 y guardar, sin scroll horizontal ni formularios extra |
| Jugadores de Noname con XI | Informador | Lista por nombre y dorsal, nota individual y guardado sin duplicar |
| Sin XI, plantilla propia | Informador | Nombres disponibles con aviso de plantilla no confirmada |
| Rival sin nombres | Informador | Puestos orientativos: portero, lateral, etc.; no aparece jugador ficticio |
| Favorito | Informador y DD | La observación compartida genera una propuesta, no un fichaje automático |
| Nota 9 sin favorito | DD | No aparece ninguna propuesta por la puntuación por sí sola |
| Alineación simple `7;Nombre` | David/Roma/DD | Guarda la plantilla pero no crea un XI |
| Alineación TITULARES/SUPLENTES | David/Roma/DD | Guarda integrantes y participaciones por rol; suplentes no se cuentan como titulares |
| Acceso a importador | Informador `own_only` | No puede editar alineación oficial |
| Duplicados de identidad | Administración | Corrección/fusión controlada, no sobreescribe informes privados |
| Guardar borrador | Analista | DD no ve el borrador ni su agregado |
| Compartir borrador | Analista y DD | DD recibe publicación persistente, sin duplicado al abrirla |
| Notificación X/estrella | DD | Visto y guardado son estados distintos que sobreviven nueva sesión |
| Eliminar jugador | Admin | Antes del borrado se presenta impacto y se exige confirmación y copia |
| Último partido aplazado | Todos | El aplazado no es la tarea prioritaria |
| Partidos antiguos y expedientes | Todos | Sin pérdidas, ni acceso a opiniones privadas de compañeros |

**Condición de publicación:** no considerar la 4.7.2 estable hasta completar al menos los recorridos de Informador, Analista, DD y Admin sobre una copia de la base real.
