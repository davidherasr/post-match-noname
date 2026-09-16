# Validación técnica No Name · Área Técnica 4.2.3.2

- Fuente única: paquete completo `NoName_PostMatch_4.2.3.1.zip`, derivado íntegramente en una carpeta de trabajo. No se han mezclado archivos de 4.2.1 u otras ramas.
- `python -m compileall -q app.py core views ui repositories services models reports scripts tests`: OK.
- `python scripts/check_release_consistency.py`: OK, VERSION, APP_VERSION y API de informes alineadas en `4.2.3.2`; head Alembic `0013_data_governance_4_2_3`.
- `pytest -q`: **128 passed**, incluido borrado físico con claves foráneas SQLite activadas, preservación de otros equipos y jugadores, autorización, plan obsoleto, selección reactiva, etiquetado español y cobertura completa de tablas ORM en exportación técnica.
- Dos bases temporales aisladas: migración desde cero hasta head 0013 y migración 0012→0013: OK; comprobado contrato físico de columnas.
- La selección de Informadores se implementa fuera de formularios para que se actualice al marcar y pueda guardarse. El botón «Guardar» nunca se bloquea por valores que Streamlit no hubiera transmitido todavía; verifica al pulsar que exista una cuenta elegida.
- El borrado tiene preview y huella de integridad; se ejecuta con autorización Admin en transacción y guarda una auditoría no restaurable; jamás se borra automáticamente ningún dato por nombre ni se carga un backup como efecto del despliegue.
- **No probado**: funcionamiento real de Streamlit Cloud, el navegador del usuario, PostgreSQL/Supabase de producción, ficheros externos del bucket ni restauración integral de un `pg_dump` real. No se ha conectado ni modificado la BD productiva. La exportación tabular no reemplaza backup real.
