"""Product consolidation for 3.8: canonical scouting, decisions and next actions.

Revision ID: 0007_product_consolidation_3_8
Revises: 0006_player_report_360_3_6
Create Date: 2026-08-26

This migration is deliberately additive/non-destructive. Legacy tables remain in
place for rollback/audit, while their useful current data is copied to the 3.8
canonical structures.
"""
from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "0007_product_consolidation_3_8"
down_revision = "0006_player_report_360_3_6"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_insp().get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {c["name"] for c in _insp().get_columns(table)}


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {x["name"] for x in _insp().get_indexes(table)}


def _add_index(name: str, table: str, cols: list[str], unique: bool = False) -> None:
    if table in _tables() and name not in _indexes(table):
        op.create_index(name, table, cols, unique=unique)


def _active_season_id(conn) -> int | None:
    if "seasons" not in _tables():
        return None
    row = conn.execute(sa.text("SELECT id FROM seasons WHERE active = :active ORDER BY id DESC LIMIT 1"), {"active": True}).first()
    return int(row[0]) if row else None


def _normalize_need(value: str | None) -> str:
    raw = (value or "").strip().casefold()
    if raw in {"alta", "high", "urgente", "abierta"}:
        return "Alta"
    if raw in {"media", "medium"}:
        return "Media"
    if raw in {"baja", "low"}:
        return "Baja"
    if raw in {"cubierta", "cubierto", "closed", "cerrada"}:
        return "Cubierta"
    if raw in {"no prioritaria", "no prioritario", "sin prioridad", "archivada", "archivado"}:
        return "No prioritaria"
    return "Media"


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Extend the canonical observation event without deleting legacy reviews.
    if "scout_observations" in _tables():
        cols = _columns("scout_observations")
        if "observation_level" not in cols:
            op.add_column("scout_observations", sa.Column("observation_level", sa.String(20), nullable=False, server_default="observation"))
        if "model_role_id" not in cols:
            op.add_column("scout_observations", sa.Column("model_role_id", sa.Integer(), sa.ForeignKey("game_model_roles.id", ondelete="SET NULL")))
        if "legacy_review_id" not in cols:
            op.add_column("scout_observations", sa.Column("legacy_review_id", sa.Integer(), sa.ForeignKey("scout_reviews.id", ondelete="SET NULL")))
        _add_index("ux_scout_observation_legacy_review", "scout_observations", ["legacy_review_id"], unique=True)
        _add_index("ix_scout_observation_role_level", "scout_observations", ["model_role_id", "observation_level"])

    # 2) Copy ScoutReview history once into ScoutObservation. We preserve every
    # original field; general_rating stays NULL because legacy reviews did not
    # store a canonical overall match rating.
    if {"scout_reviews", "scout_observations", "scouted_player_profiles"}.issubset(_tables()) and "legacy_review_id" in _columns("scout_observations"):
        reviews = conn.execute(sa.text("""
            SELECT r.id, r.profile_id, r.reviewer_id, r.status, r.observed_position,
                   r.technical_rating, r.tactical_rating, r.physical_rating, r.mental_rating,
                   r.current_level, r.potential_score, r.model_fit_score, r.attributes_json,
                   r.strengths, r.weaknesses, r.summary, r.recommendation,
                   r.created_at, r.updated_at, r.submitted_at, p.model_role, p.model_position
            FROM scout_reviews r
            JOIN scouted_player_profiles p ON p.id = r.profile_id
            LEFT JOIN scout_observations o ON o.legacy_review_id = r.id
            WHERE o.id IS NULL
            ORDER BY r.id
        """)).mappings().all()
        for row in reviews:
            model_role_id = None
            if row["model_role"] and "game_model_roles" in _tables():
                role = conn.execute(sa.text("""
                    SELECT id FROM game_model_roles
                    WHERE name = :name AND (:position IS NULL OR position = :position)
                    ORDER BY CASE WHEN position = :position THEN 0 ELSE 1 END, id
                    LIMIT 1
                """), {"name": row["model_role"], "position": row["model_position"]}).first()
                model_role_id = int(role[0]) if role else None
            conn.execute(sa.text("""
                INSERT INTO scout_observations
                  (profile_id, reviewer_id, match_id, mission_id, model_role_id, legacy_review_id,
                   source_type, observation_level, status, observed_at, observed_position,
                   general_rating, technical_rating, tactical_rating, physical_rating, mental_rating,
                   current_level, potential_score, model_fit_score, attributes_json, strengths,
                   weaknesses, summary, recommendation, submitted_at, created_at, updated_at)
                VALUES
                  (:profile_id, :reviewer_id, NULL, NULL, :model_role_id, :legacy_review_id,
                   'legacy_review', 'dossier', :status, :observed_at, :observed_position,
                   NULL, :technical_rating, :tactical_rating, :physical_rating, :mental_rating,
                   :current_level, :potential_score, :model_fit_score, :attributes_json, :strengths,
                   :weaknesses, :summary, :recommendation, :submitted_at, :created_at, :updated_at)
            """), {
                **dict(row), "model_role_id": model_role_id, "legacy_review_id": row["id"],
                "observed_at": row["submitted_at"] or row["updated_at"] or row["created_at"] or datetime.utcnow(),
            })

    # 3) Consolidate legacy DD decisions into PlayerSeasonDecision for the active
    # season. Existing 3.5/3.6 decisions always win; migration only fills gaps.
    season_id = _active_season_id(conn)
    if season_id and "player_season_decisions" in _tables():
        # ScoutedPlayerProfile is richer, so migrate it first.
        if "scouted_player_profiles" in _tables():
            profiles = conn.execute(sa.text("""
                SELECT p.* FROM scouted_player_profiles p
                WHERE NOT EXISTS (
                    SELECT 1 FROM player_season_decisions d
                    WHERE d.season_id = :season_id AND d.player_id = p.player_id
                ) ORDER BY p.id
            """), {"season_id": season_id}).mappings().all()
            for row in profiles:
                role_id = None
                if row.get("model_role") and "game_model_roles" in _tables():
                    role = conn.execute(sa.text("""
                        SELECT id FROM game_model_roles WHERE name = :name
                          AND (:position IS NULL OR position = :position)
                        ORDER BY CASE WHEN position = :position THEN 0 ELSE 1 END, id LIMIT 1
                    """), {"name": row.get("model_role"), "position": row.get("model_position")}).first()
                    role_id = int(role[0]) if role else None
                status = row.get("final_decision") or ({"candidate": "Observado", "in_review": "Seguimiento", "approved": "Prioritario", "discarded": "Descartado"}.get(row.get("status")) or "Observado")
                actor = row.get("approved_by") or row.get("assigned_to") or row.get("requested_by")
                if actor:
                    conn.execute(sa.text("""
                        INSERT INTO player_season_decisions
                          (season_id, player_id, model_role_id, status, priority, director_note,
                           fit_score, current_level, potential_score, criteria_json, updated_by,
                           created_at, updated_at)
                        VALUES (:season_id, :player_id, :role_id, :status, 3, :note,
                                :fit, :current, :potential, NULL, :actor, :created, :updated)
                    """), {
                        "season_id": season_id, "player_id": row["player_id"], "role_id": role_id,
                        "status": status, "note": row.get("director_summary"), "fit": row.get("fit_score"),
                        "current": row.get("current_level"), "potential": row.get("potential_score"),
                        "actor": actor, "created": row.get("created_at") or datetime.utcnow(),
                        "updated": row.get("updated_at") or datetime.utcnow(),
                    })
        if "league_player_profiles" in _tables():
            rows = conn.execute(sa.text("""
                SELECT p.* FROM league_player_profiles p
                WHERE NOT EXISTS (
                    SELECT 1 FROM player_season_decisions d
                    WHERE d.season_id = :season_id AND d.player_id = p.player_id
                ) ORDER BY p.id
            """), {"season_id": season_id}).mappings().all()
            for row in rows:
                conn.execute(sa.text("""
                    INSERT INTO player_season_decisions
                      (season_id, player_id, model_role_id, status, priority, director_note,
                       fit_score, current_level, potential_score, criteria_json, updated_by,
                       created_at, updated_at)
                    VALUES (:season_id, :player_id, NULL, :status, :priority, :note,
                            NULL, NULL, NULL, NULL, :actor, :created, :updated)
                """), {
                    "season_id": season_id, "player_id": row["player_id"],
                    "status": row.get("decision_status") or "Observado", "priority": row.get("priority") or 3,
                    "note": row.get("director_note"), "actor": row.get("updated_by"),
                    "created": row.get("created_at") or datetime.utcnow(), "updated": row.get("updated_at") or datetime.utcnow(),
                })

    # 4) One vocabulary for needs. Keep legacy status synchronized instead of
    # dropping it so old clients can still roll back safely.
    if "squad_needs" in _tables():
        rows = conn.execute(sa.text("SELECT id, need_level, status FROM squad_needs")).mappings().all()
        for row in rows:
            level = _normalize_need(row.get("need_level") or row.get("status"))
            conn.execute(sa.text("UPDATE squad_needs SET need_level=:level, status=:level WHERE id=:id"), {"level": level, "id": row["id"]})

    # 5) FollowUp + target match + assignee becomes one concrete ScoutMission.
    # FollowUps remain untouched/read-only for historical compatibility.
    if {"follow_ups", "scout_missions", "scout_mission_targets"}.issubset(_tables()):
        rows = conn.execute(sa.text("""
            SELECT f.id, f.player_id, f.status, f.priority, f.note, f.assigned_to,
                   f.target_match_id, f.created_by, f.created_at, f.updated_at, m.kickoff_at,
                   p.full_name
            FROM follow_ups f
            JOIN matches m ON m.id = f.target_match_id
            JOIN players p ON p.id = f.player_id
            WHERE f.target_match_id IS NOT NULL AND f.assigned_to IS NOT NULL
            ORDER BY f.id
        """)).mappings().all()
        for row in rows:
            exists = conn.execute(sa.text("""
                SELECT sm.id FROM scout_missions sm
                JOIN scout_mission_targets t ON t.mission_id = sm.id
                WHERE sm.match_id=:match_id AND sm.assigned_to=:assigned_to AND t.player_id=:player_id
                LIMIT 1
            """), {"match_id": row["target_match_id"], "assigned_to": row["assigned_to"], "player_id": row["player_id"]}).first()
            if exists:
                continue
            status = "completed" if str(row.get("status") or "").casefold() in {"cerrado", "closed", "descartado", "finalizado"} else "pending"
            result = conn.execute(sa.text("""
                INSERT INTO scout_missions
                  (match_id, mission_type, target_team_id, title, purpose, focus_json, priority,
                   status, assigned_to, requested_by, result_summary, due_at, completed_at,
                   created_at, updated_at)
                VALUES (:match_id, 'player', NULL, :title, :purpose, '[]', :priority,
                        :status, :assigned_to, :requested_by, NULL, :due_at, :completed_at,
                        :created_at, :updated_at)
            """), {
                "match_id": row["target_match_id"], "title": f"Observar · {row['full_name']}",
                "purpose": row.get("note"), "priority": max(1, min(3, int(row.get("priority") or 2))),
                "status": status, "assigned_to": row["assigned_to"], "requested_by": row["created_by"],
                "due_at": row.get("kickoff_at"), "completed_at": row.get("updated_at") if status == "completed" else None,
                "created_at": row.get("created_at") or datetime.utcnow(), "updated_at": row.get("updated_at") or datetime.utcnow(),
            })
            # SQLAlchemy Result.lastrowid is portable for SQLite and supported by
            # psycopg2 only inconsistently, so resolve the inserted mission by its
            # unique contextual values.
            mission = conn.execute(sa.text("""
                SELECT id FROM scout_missions WHERE match_id=:match_id AND assigned_to=:assigned_to
                  AND title=:title ORDER BY id DESC LIMIT 1
            """), {"match_id": row["target_match_id"], "assigned_to": row["assigned_to"], "title": f"Observar · {row['full_name']}"}).first()
            if mission:
                conn.execute(sa.text("""
                    INSERT INTO scout_mission_targets (mission_id, player_id, note, created_at)
                    VALUES (:mission_id, :player_id, :note, :created_at)
                """), {"mission_id": int(mission[0]), "player_id": row["player_id"], "note": row.get("note"), "created_at": row.get("created_at") or datetime.utcnow()})


def downgrade() -> None:
    # Non-destructive consolidation cannot safely be "un-copied" without risking
    # user data created after upgrade. We only remove the additive columns/indexes;
    # legacy tables and copied canonical rows remain valid historical information.
    if "scout_observations" not in _tables():
        return
    for idx in ["ix_scout_observation_role_level", "ux_scout_observation_legacy_review"]:
        if idx in _indexes("scout_observations"):
            op.drop_index(idx, table_name="scout_observations")
    cols = _columns("scout_observations")
    for col in ["legacy_review_id", "model_role_id", "observation_level"]:
        if col in cols:
            op.drop_column("scout_observations", col)
