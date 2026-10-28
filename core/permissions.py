from __future__ import annotations

ROLE_REPORTER = 'reporter'
ROLE_DIRECTOR = 'director'
ROLE_ADMIN = 'admin'


def roles_for(user: dict | None) -> set[str]:
    if not user:
        return set()
    return {str(x) for x in list(user.get('roles') or []) + ([user['role']] if user.get('role') else []) if x}


def has_any(user: dict | None, *roles: str) -> bool:
    return bool(roles_for(user).intersection(roles))


def can_report(user: dict | None) -> bool:
    return has_any(user, ROLE_REPORTER)


def can_direct(user: dict | None) -> bool:
    return has_any(user, ROLE_DIRECTOR)


def can_admin(user: dict | None) -> bool:
    return has_any(user, ROLE_ADMIN)


def can_track_players(user: dict | None) -> bool:
    return bool(user and user.get('can_track_players'))


def can_scout(user: dict | None) -> bool:
    return can_track_players(user)


def working_profile(user: dict | None) -> str:
    if can_direct(user):
        return 'director'
    if can_admin(user) and not can_report(user):
        return 'admin'
    if can_report(user):
        profile = (user or {}).get('participation_profile') or 'full'
        return 'own' if profile == 'own_only' else ('consult' if profile == 'viewer' else 'analyst')
    return 'consult'


def navigation_for(user: dict | None) -> list[str]:
    profile = working_profile(user)
    if profile == 'director':
        items = ['Inicio', 'Dirección Deportiva', 'Plantilla', 'Jugadores', 'Partidos']
        if can_report(user):
            items += ['Mis aportaciones', 'Mis solicitudes']
    elif profile == 'admin':
        items = ['Administración', 'Partidos', 'Jugadores']
    elif profile == 'own':
        items = ['Mis partidos', 'Mis valoraciones', 'Mis solicitudes']
    elif profile == 'analyst':
        items = ['Inicio', 'Partidos', 'Jugadores', 'Mis aportaciones', 'Mis solicitudes']
    else:
        items = ['Inicio', 'Partidos', 'Jugadores']
    if can_admin(user) and 'Administración' not in items:
        items.append('Administración')
    return items
