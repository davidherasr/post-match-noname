from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from sqlalchemy import select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from models.entities import (
    AppSetting, AuditLog, Competition, ConsolidatedPlayerEvaluation, ConsolidatedReport,
    Document, FollowUp, FollowUpHistory, LeaguePlayerProfile, LoginAttempt, Match, Participation, Player,
    PlayerAlias, PlayerEvaluation, PlayerMergeLog, PostMatchDraft, Report, ReportAssignment, ReportVersion,
    ScoutingList, ScoutingListItem, Season, Team, TeamRoster, User,
)
from repositories import scouting as repo


def _model_rows(session: Session, model, exclude: set[str] | None = None) -> list[dict]:
    exclude = exclude or set()
    columns = [c.key for c in sa_inspect(model).columns if c.key not in exclude]
    result = []
    for item in session.scalars(select(model)).all():
        result.append({col: getattr(item, col) for col in columns})
    return result


def analytics_export_xlsx(session: Session) -> bytes:
    output = BytesIO()
    rankings = repo.player_rankings(session, min_observations=1)
    matches = repo.list_matches(session, include_archived=True)
    reports = repo.list_reports(session)
    evaluations = _model_rows(session, PlayerEvaluation)
    participations = _model_rows(session, Participation)
    followups = _model_rows(session, FollowUp)
    players = _model_rows(session, Player, exclude={"photo_b64"})
    teams = _model_rows(session, Team, exclude={"logo_b64"})
    assignments = _model_rows(session, ReportAssignment)
    consolidations = _model_rows(session, ConsolidatedReport)
    consolidated_players = _model_rows(session, ConsolidatedPlayerEvaluation)
    league_profiles = _model_rows(session, LeaguePlayerProfile)
    scouting_lists = _model_rows(session, ScoutingList)
    scouting_list_items = _model_rows(session, ScoutingListItem)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rankings).to_excel(writer, sheet_name="ranking_validado", index=False)
        pd.DataFrame([{
            "id": m.id, "temporada": m.season.name, "competicion": m.competition.name,
            "jornada": m.round_name, "fecha": m.match_date, "local": m.home_team.name,
            "visitante": m.away_team.name,
            "resultado": f"{m.home_score}-{m.away_score}" if m.home_score is not None and m.away_score is not None else "",
            "video_disponible": m.video_available, "referencia_video": m.video_reference,
            "formacion_local_conocida": m.home_formation_known, "formacion_local": m.home_formation,
            "formacion_visitante_conocida": m.away_formation_known, "formacion_visitante": m.away_formation,
            "notas_estudio": m.study_notes,
            "estado": m.status, "revision": m.revision,
        } for m in matches]).to_excel(writer, sheet_name="partidos", index=False)
        pd.DataFrame([{
            "id": r.id, "partido_id": r.match_id, "informador": r.reporter.full_name,
            "rival": r.rival_team.name, "estado": r.status, "version": r.version,
            "revision": r.revision, "entregado": r.submitted_at, "aprobado": r.approved_at,
            "resumen": r.opponent_overview, "ideas": r.key_takeaways,
        } for r in reports]).to_excel(writer, sheet_name="informes", index=False)
        pd.DataFrame(evaluations).to_excel(writer, sheet_name="evaluaciones", index=False)
        pd.DataFrame(participations).to_excel(writer, sheet_name="participaciones", index=False)
        pd.DataFrame(players).to_excel(writer, sheet_name="jugadores", index=False)
        pd.DataFrame(teams).to_excel(writer, sheet_name="equipos", index=False)
        pd.DataFrame(assignments).to_excel(writer, sheet_name="asignaciones", index=False)
        pd.DataFrame(followups).to_excel(writer, sheet_name="seguimientos", index=False)
        pd.DataFrame(consolidations).to_excel(writer, sheet_name="consolidados", index=False)
        pd.DataFrame(consolidated_players).to_excel(writer, sheet_name="consenso_jugadores", index=False)
        pd.DataFrame(league_profiles).to_excel(writer, sheet_name="direccion_jugadores", index=False)
        pd.DataFrame(scouting_lists).to_excel(writer, sheet_name="listas", index=False)
        pd.DataFrame(scouting_list_items).to_excel(writer, sheet_name="listas_jugadores", index=False)
    return output.getvalue()


def full_export_xlsx(session: Session) -> bytes:
    return analytics_export_xlsx(session)


def technical_backup_zip(session: Session) -> bytes:
    models = [
        User, LoginAttempt, Season, Competition, Team, Player, PlayerAlias, PlayerMergeLog,
        TeamRoster, Match, Participation, ReportAssignment, Report, PlayerEvaluation,
        ReportVersion, Document, FollowUp, FollowUpHistory, ConsolidatedReport,
        ConsolidatedPlayerEvaluation, PostMatchDraft, LeaguePlayerProfile, ScoutingList, ScoutingListItem, AppSetting, AuditLog,
    ]
    payload = {
        "format": "postmatch-scout-backup-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": {model.__tablename__: _model_rows(session, model) for model in models},
    }
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("backup.json", json.dumps(payload, ensure_ascii=False, default=str, indent=2))
        archive.writestr("README.txt", "Copia técnica completa de No Name PostMatch 4.0. Contiene datos sensibles y hashes de contraseña. Guárdala de forma segura.\n")
    return output.getvalue()
