# Actualización de No Name · Área Técnica a 4.7.2

1. **Copia de seguridad recuperable de PostgreSQL/Supabase** y conservación del ZIP 4.7.1 y los Secrets existentes. **No exportar contraseñas en capturas ni repositorios.**
2. Sustituir **todo el código del repositorio**, no únicamente `app.py` o `experience47.py`. Actualizar también `ui/mobile472.py`, `repositories/mobile472.py` y `requirements.txt`. No mezclar versiones.
3. Instalar las dependencias: se requiere **Streamlit 1.51 o superior y menor que 2**, para los componentes bidireccionales v2. Reiniciar Streamlit Cloud después del despliegue para asegurar que las dependencias se actualizan.
4. Mantener el `DATABASE_URL` y los demás Secrets existentes, siempre fuera del control de versiones. No volver a ejecutar manualmente SQL de creación de tablas, no editar `public.alembic_version` y no manipular `supabase_migrations.schema_migrations`.
5. No hay nueva revisión de Alembic en la 4.7.2: head esperado **`0018_workspaces_4_7`**. Si se viene de 4.6 o anterior, hay que completar las migraciones anteriores con copia previa.
6. Probar con usuarios reales de perfiles Informador ocasional, Analista, DD y Admin en una base de prueba o copia restaurada antes de publicar la app para el staff.
7. **No activar un nuevo ensayo en la base de producción sin verificar** los escenarios del documento `VALIDACION_4_7_2.md`, en particular importación repetida, valoraciones individuales y restricciones de acceso.

## Ejemplo para pegar desde ChatGPT en «Cargar alineación»

```text
TITULARES
1;Chuchi;POR
2;Yago;LD
15;Asiel;DFC
SUPLENTES
12;Jugador suplente;POR
```

Una lista sin secciones:

```text
1;Chuchi
2;Yago
15;Asiel
```

solo actualiza las fichas de plantilla; no se presume que esos futbolistas participaron ni que los primeros once fueron titulares.

**Importante:** el parser no importa automáticamente una foto. La transcripción la puedes pedir en el móvil a ChatGPT y copiarla o subirla como `.txt`/`.csv`.
