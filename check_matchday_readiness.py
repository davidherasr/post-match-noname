from __future__ import annotations

from core.database import session_scope
from core.schedule import is_schedule_confirmed
from repositories import calendar as calendar_repo
from repositories import workspaces


def main() -> None:
    with session_scope() as session:
        data = workspaces.load_operational_readiness(session)

    season = data.get("active_season")
    own = data.get("own_team")
    print(f"Temporada activa: {season.name if season else 'NO'}")
    print(f"Equipo propio: {own.name if own else 'NO'}")
    print(f"Partidos cargados: {data.get('fixture_count', 0)}")
    print(f"Jornadas cargadas: {data.get('round_count', 0)}")
    print(f"Jugadores en plantilla: {data.get('own_roster_count', 0)}")

    match = data.get("today_match") or data.get("next_match")
    if match:
        prefix = "PARTIDO DE HOY" if data.get("today_match") else "PRÓXIMO PARTIDO"
        print(f"{prefix}: {match.round_name} · {match.home_team.name} - {match.away_team.name}")
        print(f"Programación: {calendar_repo.schedule_label(match)}")
        print(f"Operativo: {'SÍ' if is_schedule_confirmed(match) else 'NO · confirmar hora real'}")
    else:
        print("Próximo partido de No Name: NO ENCONTRADO")

    warnings = data.get("warnings") or []
    if warnings:
        print("\nAvisos:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
