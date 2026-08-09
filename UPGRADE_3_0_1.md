# Actualización 3.0 → 3.0.1

Esta actualización corrige únicamente la navegación visual de Streamlit.

## Qué cambia

- Se oculta la navegación automática creada por la carpeta `pages/`.
- El login queda sin barra lateral.
- Tras iniciar sesión solo aparece el menú propio definido por No Name para el rol autenticado.
- Se reduce la barra de herramientas pública de Streamlit.

## Base de datos

No hay cambios de esquema ni nuevas migraciones. La actualización **no borra, transforma ni inserta datos en Supabase**.

Mantén exactamente los mismos Secrets de Streamlit Cloud y el mismo `DATABASE_URL`.

## Actualización

1. Sustituye en GitHub los archivos de la 3.0 por el contenido completo del paquete 3.0.1.
2. Confirma y sube los cambios a `main`.
3. En Streamlit Community Cloud ejecuta **Reboot app**.
4. Comprueba primero el login: no deben aparecer `app`, `admin`, `catalog`, `dashboard`, etc. en la izquierda.
5. Inicia sesión y comprueba que solo aparece la navegación correspondiente a tu rol.

El Main file path sigue siendo `app.py`.
