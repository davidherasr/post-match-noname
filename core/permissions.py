from __future__ import annotations

ROLE_REPORTER = "reporter"
ROLE_SCOUT = "scout"
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
    return has_any(user, ROLE_REPORTER, ROLE_DIRECTOR, ROLE_ADMIN)


def can_scout(user: dict | None) -> bool:
    return has_any(user, ROLE_SCOUT, ROLE_DIRECTOR, ROLE_ADMIN)


def can_direct(user: dict | None) -> bool:
    return has_any(user, ROLE_DIRECTOR, ROLE_ADMIN)


def can_admin(user: dict | None) -> bool:
    return has_any(user, ROLE_ADMIN)


def navigation_for(user: dict | None) -> list[str]:
    # Product navigation is deliberately independent from a manually selected
    # operating role. Roles only determine capabilities inside each workspace.
    items = ["Inicio", "Jornada", "Jugadores"]
    if can_direct(user):
        items.append("Plantilla")
    if can_admin(user):
        items.append("Administración")
    return items
