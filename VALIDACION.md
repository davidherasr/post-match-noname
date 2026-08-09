# Validación técnica · No Name PostMatch 3.0.0

## Comprobaciones ejecutadas

- Compilación de todos los módulos Python.
- Suite de pruebas automatizadas completa.
- Generación PDF dentro de tests de repositorio.
- Flujo de alineación rival sin plantilla previa.
- Creación automática de jugadores y roster rival desde el partido.
- Copia de alineación propia entre partidos.
- Separación estricta entre histórico propio y scouting rival.
- Rankings rivales únicamente a partir de informes aprobados/finales.
- Migración Alembic desde base vacía hasta `head`.
- Migración Alembic desde `0001_initial_2_0` hasta `0002_noname_3_0`.
- Contrato interno de versión 3.0.0.

## Resultado de la suite

```text
16 passed
```

## Migraciones

```text
0001_initial_2_0
        ↓
0002_noname_3_0  (head)
```

`0002_noname_3_0` es deliberadamente no destructiva: marca la frontera de la edición No Name y conserva la base 2.x existente.

## Datos incluidos

La release no contiene base SQLite pre-poblada ni muestras deportivas. No se incluyen jugadores, equipos, partidos o informes de demostración. Los tests crean sus datos solo en bases SQLite en memoria durante la ejecución.

## Limitación de validación

El entorno de construcción no tiene instalado Streamlit, por lo que no se ha podido hacer una prueba de aceptación visual en navegador. Esa validación debe hacerse tras el despliegue en Streamlit Community Cloud. La lógica Python, repositorios, migraciones y pruebas sí se han ejecutado.
