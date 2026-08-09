# Hotfix 2.1.1

## Error corregido

La versión desplegada podía fallar con:

```text
TypeError en render(user, mode="work")
TypeError en render(user, mode="archive")
```

La causa es una mezcla de archivos: `app.py` 2.1 llamaba a la nueva API con `mode`, mientras `pages/reports.py` seguía perteneciendo a 2.0 y solo admitía `render(user)`.

## Cambios

- Entradas estables `render_work()` y `render_archive()`.
- Comprobación explícita de compatibilidad entre `app.py` y `pages/reports.py`.
- Mensaje legible si GitHub contiene archivos mezclados.
- Script `python scripts/check_release_consistency.py`.
- ZIP preparado con `app.py` en la raíz para reemplazar directamente el repositorio.

## Actualización correcta

1. Haz una copia de tus Secrets.
2. Borra del repositorio los archivos anteriores, excepto `.git` y tus Secrets de Streamlit Cloud.
3. Sube **todo** el contenido de este ZIP a la raíz.
4. Comprueba que existen `app.py`, `pages/reports.py`, `requirements.txt` y `VERSION`.
5. En Streamlit Cloud, pulsa **Reboot app** o elimina caché y reinicia.

Main file path: `app.py`.
