# Actualización a 4.7.4

1. **Copia de seguridad de PostgreSQL** antes de modificar código o ejecutar migraciones.
2. Sustituye el repositorio **completo**, no archivos individuales; conserva los Secrets de Streamlit Cloud fuera del ZIP.
3. Usa la configuración de producción existente, `RUN_MIGRATIONS=true` cuando corresponda al flujo de despliegue ya aprobado. Nunca manipules a mano `public.alembic_version`.
4. El código necesita el esquema de 4.7.3 (Alembic `0019_rating_release_4_7_3`). **4.7.4 no añade migraciones**. Una instalación desde 4.6 requiere ejecutar en secuencia las migraciones anteriores aplicables.
5. Verifica los casos de `VALIDACION_4_7_4.md`, primero con cuentas de prueba y datos controlados. **No borres jugadores reales para ensayar la fusión**.
6. Si la publicación de un partido falla, la transacción de preparación de los dos XI debe revertirse. Ningún encuentro histórico se publica automáticamente.

## Rollback

Si aparece un error de aplicación, vuelve al código 4.7.3 manteniendo la copia de seguridad y verificando la compatibilidad. El estado de las valoraciones retractadas o suplentes añadidos por 4.7.4 no queda automáticamente deshecho al volver al código antiguo; para restauración exacta utiliza backup y procedimiento validado. No ejecutes un downgrade destructivo ni modifiques manualmente la tabla de versiones.
