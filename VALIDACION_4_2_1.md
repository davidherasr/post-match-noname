# Validación 4.2.1

Release funcional anterior a 4.2.2. Mantenía el head Alembic `0012_sporting_reading_4_2` y consolidó la inteligencia transversal de Dirección Deportiva.

Se detectó posteriormente en producción un `KeyError` durante el arranque de base de datos en Streamlit Cloud. 4.2.2 añade un hotfix de arranque y diagnóstico sin modificar el esquema ni los datos deportivos.
