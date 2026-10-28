# Upgrade 4.1.0

## Qué cambia

4.1.0 cambia el flujo de producto, no el esquema de datos. El trabajo queda separado en tres responsabilidades:

1. **Administración**: usuarios/roles, calendario, horarios, equipos, plantillas y calidad de datos.
2. **Dirección Deportiva**: decide qué partidos/equipos/jugadores requieren seguimiento y asigna el trabajo.
3. **Scout**: ejecuta el encargo y registra observaciones.

Los roles son combinables, pero ya no se heredan por jerarquía. Un usuario Admin que también sea DD o Scout debe tener esos roles asignados explícitamente.

## Contraseñas provisionales

Administración puede usar credenciales temporales simples de mínimo 4 caracteres, por ejemplo `1234`, siempre que el cambio de contraseña sea obligatorio. El usuario queda bloqueado en la pantalla de cambio hasta crear una contraseña definitiva que cumpla la política fuerte.

## Scouting

Se elimina el selector Barrido / Observación / Dossier. Seleccionar varios jugadores produce apuntes rápidos; seleccionar uno abre la observación individual. El dossier se consulta en Player Report 360 y se construye con el historial.

## Base de datos

No hay migración nueva. Mantén el mismo `DATABASE_URL`, Secrets y Supabase. El head sigue siendo `0010_core_workspace_schema_repair_4_0_4`.

Tu Supabase ya migrado a 0010 no necesita ninguna acción SQL adicional para 4.1.0.
