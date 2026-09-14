# Validación técnica · No Name PostMatch 3.9.0

## Resultado

- `python -m compileall -q .`: OK.
- `pytest -q`: **59 passed**.
- `python scripts/check_release_consistency.py`: OK.
- Alembic base vacía → `0007_product_consolidation_3_8`: OK.
- Alembic `0006_player_report_360_3_6` → `0007_product_consolidation_3_8`: OK.
- 3.9.0 no añade migración: una base 3.8 ya situada en `0007` no se transforma.

## Cobertura 3.9

La suite añade 10 pruebas de Matchday 3.9, incluyendo:

- parser 3.9 sobre `1;13/09/2026;La Cistérniga C.F.;C.D. Noname`;
- Jornada 1 elegida como ronda por defecto el 13/09/2026;
- Inicio identificando el partido como Partido de hoy;
- diagnóstico de datos reales sin inventar kickoff;
- paso a estado operativo tras confirmar una hora real;
- conteo de plantilla real;
- ausencia de 17:00 como hora predeterminada;
- ausencia de navegación hacia Misiones/Nuevo postpartido;
- Informes usando capacidades multirol y no `User.role` como selector operativo.

## Integridad del paquete

La release final debe distribuirse sin `.db`, `.sqlite`, `.sqlite3`, `.streamlit/secrets.toml`, `__pycache__`, `.pytest_cache` ni datos deportivos demo.
