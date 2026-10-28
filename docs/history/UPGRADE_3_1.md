# Actualización a No Name PostMatch 3.1.0

## Compatibilidad con Supabase

**No cambies de proyecto Supabase, no borres tablas y no cambies `DATABASE_URL`.**

3.1.0 no introduce cambios de esquema respecto a 3.0/3.0.1. La revisión Alembic actual continúa siendo `0002_noname_3_0`.

## Actualización recomendada

1. Haz un backup técnico desde la aplicación si ya contiene información relevante.
2. Sustituye en GitHub/Codespaces el código anterior por el contenido completo del ZIP 3.1.0.
3. Comprueba que `app.py` está en la raíz del repositorio.
4. No sobrescribas ni publiques un archivo real `.streamlit/secrets.toml`.
5. Confirma y sube los cambios:

```bash
git add -A
git commit -m "No Name PostMatch 3.1.0 - performance y accesibilidad"
git push origin main
```

6. En Streamlit Cloud haz **Reboot app**.
7. Mantén `Main file path = app.py`.
8. Mantén exactamente los mismos Secrets de Supabase.

## Qué ocurre con los datos

Nada se reinicia. Equipos, jugadores, temporadas, partidos, participaciones, usuarios, informes, versiones, evaluaciones, seguimientos y documentos permanecen en la misma base.

## Rollback

Al no existir migración de esquema en 3.1.0, si la interfaz presentase un problema puedes volver temporalmente al commit 3.0.1 sin necesidad de revertir la base de datos.
