ROLES = {
    "admin": "Administrador",
    "reporter": "Informador",
    "director": "Dirección deportiva",
}

MATCH_STATUSES = {
    "draft": "Borrador",
    "published": "Publicado",
    "closed": "Cerrado",
    "archived": "Archivado",
}

REPORT_STATUSES = {
    "draft": "Borrador",
    "submitted": "Entregado",
    "returned": "Devuelto para corregir",
    "approved": "Aprobado",
    "final": "Finalizado (legado)",
}

ASSIGNMENT_STATUSES = {
    "pending": "Pendiente",
    "in_progress": "En curso",
    "submitted": "Entregado",
    "approved": "Aprobado",
    "returned": "Devuelto",
    "waived": "No requerido",
}

OBSERVATION_STATUSES = {
    "evaluated": "Evaluado",
    "insufficient": "Sin elementos suficientes",
    "not_observed": "No observado",
    "video_review": "Revisar en vídeo",
}

EVALUATION_SCOPES = {
    "rival": "Jugador rival",
    "own": "Jugador propio",
}

RECOMMENDATIONS = [
    "Sin interés",
    "Anotar en base de datos",
    "Seguimiento recomendado",
    "Jugador interesante",
    "Prioridad de seguimiento",
]

CONFIDENCE_LEVELS = ["Baja", "Media", "Alta"]

FOLLOW_UP_STATUSES = [
    "Pendiente de primera revisión",
    "Seguimiento",
    "Nueva observación programada",
    "En valoración de dirección deportiva",
    "Descartado",
    "Cerrado",
]

POSITIONS = [
    "POR", "LD", "DFC", "LI", "CAD", "CAI", "MCD", "MC", "MP", "ED", "EI", "SD", "DC", "Otro",
]

FORMATIONS = [
    "4-3-3", "4-2-3-1", "4-4-2", "4-1-4-1", "4-3-1-2", "4-4-1-1",
    "3-4-3", "3-4-2-1", "3-5-2", "3-1-4-2", "5-4-1", "5-3-2", "Personalizada",
]

STRENGTH_TAGS = [
    "Técnica", "Visión", "Último pase", "Conducción", "Desborde", "Finalización",
    "Juego aéreo", "Duelos", "Velocidad", "Resistencia", "Colocación", "Anticipación",
    "Salida de balón", "Centros", "Personalidad", "Polivalencia",
]

PDF_MODES = {
    "executive": "Resumen",
    "full": "Completo",
}
