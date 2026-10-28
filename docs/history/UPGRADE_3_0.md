# Actualización 2.x → No Name PostMatch 3.0

La regla de esta versión es **preservar la base existente**.

## Procedimiento

1. Backup técnico.
2. Reemplazar todo el código del repositorio.
3. No cambiar `DATABASE_URL`.
4. No borrar tablas en Supabase.
5. Reboot de Streamlit.
6. Comprobar en logs que Alembic alcanza `0002_noname_3_0`.
7. Entrar como administrador y abrir **Nuevo postpartido**.

## Qué se conserva

- usuarios;
- temporadas;
- competiciones;
- equipos;
- jugadores y alias;
- plantillas;
- partidos y participaciones;
- informes y evaluaciones;
- snapshots/versiones;
- seguimientos;
- documentos y auditoría.

## Qué no hace la 3.0

- no elimina datos;
- no reinicia Supabase;
- no carga una plantilla deportiva de ejemplo;
- no sustituye tu administrador si ya existe;
- no obliga a reconstruir el histórico.
