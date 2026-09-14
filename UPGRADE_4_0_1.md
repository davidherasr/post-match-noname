# Actualización No Name PostMatch 4.0.1

## Por qué existe

4.0.1 corrige dos problemas de despliegue detectados en Streamlit Cloud:

1. el directorio especial `pages/` hacía visible la navegación automática de Streamlit aunque la aplicación tuviera su propio menú;
2. un fallo de conectividad PostgreSQL durante `init_db()` terminaba en un traceback completo antes de cargar la interfaz.

## Muy importante al sustituir 4.0.0

No copies 4.0.1 por encima dejando archivos antiguos. **El directorio `pages/` debe desaparecer del repositorio.**

El paquete 4.0.1 utiliza `views/` y no contiene `pages/`.

Si trabajas con Git:

```bash
git rm -r pages 2>/dev/null || true
# copia después todo el contenido de 4.0.1
git add -A
git commit -m "No Name PostMatch 4.0.1 - hotfix despliegue"
git push origin main
```

Después haz **Reboot app** en Streamlit Cloud.

## Supabase / DATABASE_URL

Se conservan el mismo Supabase y todos los datos. No se crea una base nueva.

Mantén:

```toml
RUN_MIGRATIONS = true
DEMO_MODE = false
```

Para `DATABASE_URL`, usa preferentemente la cadena PostgreSQL **Session pooler** que muestra Supabase en `Database → Connect`.

Si tu URL empieza por un host de este tipo:

```text
db.<project-ref>.supabase.co
```

es el endpoint directo. Puede requerir IPv6. En Streamlit Cloud es más robusto utilizar Session pooler.

No pegues nunca la contraseña en incidencias o capturas.

## Base de datos

No hay nueva migración respecto a 4.0.0:

```text
0008_match_study_4_0
```

La actualización es de código/arranque y no destructiva.
