# Validación de release · 4.4.3

**Fuente:** ZIP completo de 4.4.2 como única base, editado en copia independiente. Sin acceso a Supabase ni modificaciones de la base productiva.

## Comprobaciones efectivamente ejecutadas

- `pytest -q --disable-warnings --maxfail=1`: **155 pruebas superadas**, incluidas ocho nuevas para permisos de DD e Informador, petición/expansión sin duplicados, vínculo al informe, rechazo voluntario, participación no confirmada, respuesta aplazada repetible, edición neutral que mantiene IDs y borrado protegido.
- `python -m compileall -q`: sintaxis de aplicación, vistas, repositorios, migraciones y pruebas verificada.
- `python scripts/check_release_consistency.py`: VERSION, APP_VERSION, contrato de reports, rutas, migración 0015 y módulos requeridos coherentes.
- En SQLite aislado, aplicación **original 4.4.2** migrada realmente a Alembic 0014, comprobado que NO existen tablas de peticiones; después ejecutada la migración de este código a 0015 y comprobada la aparición de las tres tablas. Independientemente, instalación desde cero a 0015.
- Integridad de ZIP final, exclusión de `.db`, secretos y cachés, comprobación de extracción y reejecución de pruebas sobre el ZIP extraído: registrar resultado al final del empaquetado.

## Casos de aceptación que quedan pendientes

- Arranque efectivo en Streamlit Cloud con PostgreSQL/Supabase existente, confirmación de versión 0015, prueba de inicio de sesión y roles con registros reales.
- Prueba visual en navegador a 375/768/1366 px de los botones `st.pills` de notas y de formularios de lectura breve y respuesta; instalación de Streamlit no disponible en el entorno de build (fallo de resolución de red al descargar dependencia).
- Ensayo de restauración del backup real y migración PostgreSQL 0014→0015 en una réplica, concurrencia de creación/respuesta de solicitudes y limpieza de documentos almacenados. La migración no toca los documentos.
- Prueba de uso con Informadores reales para medir duración de la lectura breve; ~1 minuto es un objetivo UX, no una métrica medida.

No declarar la versión validada en producción hasta completar esas comprobaciones. Si aparece un problema, recuperar el error y emitir un hotfix derivado **exclusivamente** de este ZIP, sin reescribir histórico ni reiniciar Supabase.
