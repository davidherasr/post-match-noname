# Upgrade 4.2.2

## Desde 4.2.1 / 4.2.0

1. Sustituye **todo el código** del repositorio por el contenido de `NoName_PostMatch_4.2.2.zip`.
2. Conserva los Secrets de Streamlit Cloud. No copies un `secrets.toml` real al repositorio.
3. Haz commit/push y después `Manage app → Reboot app`.
4. No ejecutes SQL adicional: 4.2.2 no incorpora una migración nueva.
5. El head esperado continúa siendo `0012_sporting_reading_4_2`.

## Hotfix de arranque

4.2.1 podía entrar innecesariamente en el runner de Alembic en cada cold start aunque Supabase ya estuviese exactamente en `0012`. 4.2.2 lee primero el head almacenado y el head incluido en la release. Si coinciden, valida el esquema físico y continúa sin ejecutar Alembic.

Si Alembic debe migrar porque la base está por detrás, se ejecuta con normalidad. Un `KeyError` nunca se ignora salvo que, después del intento, la base esté realmente en el head y el contrato físico completo sea válido.

La pantalla de arranque también diferencia las fases `configuración`, `migraciones / validación de esquema`, `bootstrap técnico` y `carga de ajustes`, y registra el traceback completo en los logs de Streamlit Cloud.
