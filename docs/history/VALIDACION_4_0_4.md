# Validación técnica · No Name PostMatch 4.0.4

Release orientada al `ProgrammingError` observado en producción al abrir Inicio.

Se valida:

- compilación Python;
- suite pytest;
- consistencia de release;
- Alembic desde base vacía;
- upgrade 0009 → 0010;
- reparación de una base marcada en 0009 pero con columnas opcionales antiguas ausentes;
- consulta ligera de próximo partido sin `joinedload` de Competition ni hidratación completa de Match.
