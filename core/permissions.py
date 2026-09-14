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
    # Reporting remains available to Informador and to Director/Admin when those
    # users need to review or intervene in legacy report workflows.
    return has_any(user, ROLE_REPORTER, ROLE_DIRECTOR, ROLE_ADMIN)


def can_scout(user: dict | None) -> bool:
    # 4.1: sporting roles are capabilities, not a hierarchy. Being Admin or DD
    # does not automatically make somebody a Scout. Add the Scout role explicitly
    # when one person performs both functions.
    return has_any(user, ROLE_SCOUT)


def can_direct(user: dict | None) -> bool:
    # 4.1: Administration manages data/users; sporting decisions belong to an
    # explicit Dirección Deportiva role. An Admin can receive both roles if needed.
    return has_any(user, ROLE_DIRECTOR)


def can_admin(user: dict | None) -> bool:
    return has_any(user, ROLE_ADMIN)


def navigation_for(user: dict | None) -> list[str]:
    items = ["Inicio", "Jornada", "Jugadores"]
    if can_direct(user):
        items.append("Plantilla")
    if can_admin(user):
        items.append("Administración")
    return items
