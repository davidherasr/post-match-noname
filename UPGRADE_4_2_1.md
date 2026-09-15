# Upgrade 4.2.1

## Desde 4.2.0

1. Sustituye el código completo por la release 4.2.1.
2. Conserva tus Secrets de Streamlit/Supabase; no los copies dentro del repositorio.
3. Haz commit/push y reinicia la app.
4. No ejecutes SQL adicional: 4.2.1 no incorpora una migración nueva.
5. Alembic debe seguir mostrando `0012_sporting_reading_4_2 (head)`.

## Qué cambia

- Dirección Deportiva incorpora lectura transversal entre jornadas para jugadores, equipos y discrepancias.
- Inicio abre directamente la bandeja de jugadores señalados de DD.
- Solo usuarios con rol **Informador** pueden crear/editar valoraciones y postpartidos. Admin y DD no heredan esa capacidad.
- El seguimiento individual continúa controlado por `can_track_players`.
- Se retiran del paquete las vistas antiguas de Scout/DD y los workspaces dejan de cargar misiones Scout heredadas.
- No se elimina información histórica de observaciones o misiones ya guardadas.

## Comprobación recomendada tras desplegar

- Entra con un Admin puro: debe administrar, pero no poder escribir un postpartido.
- Entra con un DD puro: debe ver Dirección Deportiva, pero no guardar una lectura neutral.
- Entra con un Informador: debe poder puntuar/postpartido.
- En DD → Lectura deportiva, comprueba las pestañas Panorama, Jugadores señalados, Equipos, Discrepancias y Partidos recientes.
- Si tu usuario hace seguimiento individual, verifica que mantiene activado el permiso específico en Administración → Usuarios.
