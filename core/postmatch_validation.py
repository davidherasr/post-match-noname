from __future__ import annotations


def validate_postmatch_draft(draft: dict) -> tuple[list[str], list[str]]:
    """Validate the publishable post-match payload without any Streamlit dependency."""
    errors: list[str] = []
    warnings: list[str] = []
    if not str(draft.get("kickoff_time") or "").strip():
        errors.append("Falta la hora definitiva del partido. Confírmala antes de publicar.")
    own_xi = [x for x in draft.get("own_xi", []) if x.get("player_id")]
    rival_xi = [x for x in draft.get("rival_xi", []) if str(x.get("name") or "").strip()]
    if len(own_xi) != 11 or len({int(x["player_id"]) for x in own_xi}) != 11:
        errors.append("El XI de No Name debe tener 11 jugadores distintos.")
    rival_names = [str(x.get("name") or "").strip().lower() for x in rival_xi]
    if len(rival_xi) != 11:
        errors.append("Completa los 11 titulares rivales.")
    if len(rival_names) != len(set(rival_names)):
        errors.append("Hay un nombre rival repetido en el XI.")
    for sub in draft.get("own_subs", []):
        if not (0 <= int(sub.get("minute", 0)) <= 130):
            errors.append("Hay un cambio de No Name con minuto no válido.")
    for sub in draft.get("rival_subs", []):
        if not str(sub.get("in_name") or "").strip():
            warnings.append("Hay un cambio rival sin nombre de entrada; se omitirá.")
    if not draft.get("reporter_ids"):
        warnings.append("No hay informadores asignados; el partido se publicará igualmente.")
    return errors, warnings
