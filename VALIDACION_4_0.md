# Validación técnica · No Name PostMatch 4.0.0

## Resultado de la build

- `python -m compileall -q .`: **OK**.
- `pytest -q`: **64 passed**.
- `python scripts/check_release_consistency.py`: **OK**.
- Alembic fresh → `0008_match_study_4_0`: **OK**.
- Upgrade realista generado con código 3.9 en `0007` → código 4.0 → `0008`: **OK**.
- En el upgrade 3.9→4.0 se comprobó que una formación existente se conserva y pasa a `formation_known=true`, mientras el lado sin formación permanece desconocido.

## Cobertura específica 4.0

Se prueban automáticamente:

- parser de listas Federación con distintos formatos;
- vídeo y formación independiente por lado;
- combinación formación conocida + formación desconocida en el mismo partido;
- importación de plantilla sin crear participaciones falsas;
- guardado del XI en orden de slots de la formación;
- presencia de controles de Match Study y campograma en Jornada.

## Limitación del entorno de build

El entorno de construcción no dispone del paquete `streamlit` instalado y no tiene acceso de red para instalarlo, por lo que no se ha levantado aquí un servidor Streamlit interactivo. El código Python completo compila, la lógica/repositorios/migraciones pasan la suite automatizada y la release se valida de nuevo después de empaquetar.

La conexión contra el Supabase real del usuario tampoco se ejecuta desde la build porque sus Secrets no se incluyen en el paquete.
