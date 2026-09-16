from __future__ import annotations


def validate_postmatch_draft(draft: dict) -> tuple[list[str], list[str]]:
    """Validate the publishable post-match payload without any Streamlit dependency."""
    errors: list[str] = []
    warnings: list[str] = []
    if not str(draft.get("kickoff_time") or "").strip():
        errors.append("Falta la hora definitiva del partido. Confírmala antes de publicar.")
    own_xi = [x for x in draft.get("own_xi", []) if x.get("player_id")]
    rival_xi = [x for x in draft.get("rival_xi", []) if str(x.get("name") or "").strip()]
    if len(own_xi) > 11 or len({int(x["player_id"]) for x in own_xi}) != len(own_xi):
        errors.append("Los titulares de No Name deben ser distintos (máximo 11).")
    elif len(own_xi) < 11:
        warnings.append(f"No Name: {len(own_xi)}/11 titulares documentados. Completa el XI cuando lo conozcas.")
    rival_names = [str(x.get("name") or "").strip().lower() for x in rival_xi]
    if len(rival_xi) > 11:
        errors.append("No se pueden indicar más de 11 titulares rivales.")
    elif len(rival_xi) < 11:
        warnings.append(f"Rival: {len(rival_xi)}/11 titulares documentados. No se inventarán nombres.")
    if len(rival_names) != len(set(rival_names)):
        errors.append("Hay un nombre rival repetido en el XI.")
    for sub in draft.get("own_subs", []):
        if not (0 <= int(sub.get("minute", 0)) <= 130):
            errors.append("Hay un cambio de No Name con minuto no válido.")
    for sub in draft.get("rival_subs", []):
        if not str(sub.get("in_name") or "").strip():
            warnings.append("Hay un cambio rival sin nombre de entrada; se omitirá.")
    if not draft.get("reporter_ids"):
        errors.append("Selecciona al menos un Informador para poder publicar y generar su tarea.")
    return errors, warnings
