# Upgrade 4.0.6

4.0.6 es un hotfix de interfaz para el editor de XI observado.

## Cambio principal

Al seleccionar un jugador en una posición, ese jugador deja de aparecer como opción en las demás posiciones del mismo XI. El selector actual conserva su propio jugador para permitir correcciones.

## Base de datos

No hay migración nueva. El head permanece en `0010_core_workspace_schema_repair_4_0_4`. Si la instalación 4.0.5 ya funciona contra Supabase, basta con sustituir el código y reiniciar Streamlit.
