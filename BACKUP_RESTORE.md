# Backup y restauración

## Crear

Desde **Administración > Backup**, descarga el ZIP técnico. Contiene todas las tablas, relaciones, configuración, versiones y hashes de contraseña.

## Restaurar

Sobre una base vacía:

```bash
python scripts/restore_backup.py backup.zip
```

Para reemplazar una base existente:

```bash
python scripts/restore_backup.py backup.zip --replace
```

La opción `--replace` elimina el contenido actual. Crea antes otra copia y prueba siempre en un entorno separado.

Los registros de documentos conservan sus rutas y checksums; los archivos PDF solo podrán recuperarse si las rutas de Storage siguen existiendo o si las copias locales se han preservado.
