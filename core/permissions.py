from __future__ import annotations

ROLE_REPORTER = "reporter"
ROLE_DIRECTOR = "director"
ROLE_ADMIN = "admin"


def roles_for(user: dict | None) -> set[str]:
    if not user:
        return set()
    values = list(user.get("roles") or [])
    if user.get("role"):
        values.append(user["role"])
    return {str(value) for value in values if value}


def has_any(user: dict | None, *roles: str) -> bool:
    return bool(roles_for(user).intersection(roles))


def can_report(user: dict | None) -> bool:
    # 4.2.2: valorar/postpartido es responsabilidad explícita de Informador.
    # Administrador y Dirección Deportiva necesitan también ese rol si quieren puntuar.
    return has_any(user, ROLE_REPORTER)


def can_track_players(user: dict | None) -> bool:
    """Individual market/player tracking is a capability, not an organizational role."""
    if not user:
        return False
    return bool(user.get("can_track_players"))


def can_scout(user: dict | None) -> bool:
    # Backwards-compatible alias for legacy modules/tests. 4.2 no longer exposes
    # Scout as a normal staff role.
    return can_track_players(user)


def can_direct(user: dict | None) -> bool:
    # 4.1: Administration manages data/users; sporting decisions belong to an
    # explicit Dirección Deportiva role. An Admin can receive both roles if needed.
    return has_any(user, ROLE_DIRECTOR)


def can_admin(user: dict | None) -> bool:
    return has_any(user, ROLE_ADMIN)


def navigation_for(user: dict | None) -> list[str]:
    items = ["Inicio", "Jornada", "Jugadores"]
    if can_report(user) or can_direct(user):
        items.append("Informes")
    if can_direct(user):
        items.append("Dirección Deportiva")
    if can_admin(user):
        items.append("Administración")
    return items
