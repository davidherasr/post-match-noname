from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="reporter", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    session_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("name", "country", name="uq_competition_country"),)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str | None] = mapped_column(String(80))
    logo_b64: Mapped[str | None] = mapped_column(Text)
    logo_mime: Mapped[str | None] = mapped_column(String(80))
    is_own_team: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    nationality: Mapped[str | None] = mapped_column(String(80))
    preferred_foot: Mapped[str | None] = mapped_column(String(20))
    primary_position: Mapped[str | None] = mapped_column(String(20))
    aliases: Mapped[str | None] = mapped_column(Text)
    photo_b64: Mapped[str | None] = mapped_column(Text)
    photo_mime: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("normalized_name", "date_of_birth", name="uq_player_identity"),
    )


class PlayerAlias(Base):
    __tablename__ = "player_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    player: Mapped[Player] = relationship()
    __table_args__ = (UniqueConstraint("normalized_alias", name="uq_player_alias"),)


class PlayerMergeLog(Base):
    __tablename__ = "player_merge_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_player_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class TeamRoster(Base):
    __tablename__ = "team_rosters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    shirt_number: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined_at: Mapped[date | None] = mapped_column(Date)
    left_at: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    team: Mapped[Team] = relationship()
    season: Mapped[Season] = relationship()
    player: Mapped[Player] = relationship()

    __table_args__ = (
        UniqueConstraint("team_id", "season_id", "player_id", name="uq_roster_player"),
    )


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    round_name: Mapped[str] = mapped_column(String(80), nullable=False)
    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    venue: Mapped[str | None] = mapped_column(String(160))
    home_formation: Mapped[str | None] = mapped_column(String(40))
    away_formation: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    report_due_at: Mapped[datetime | None] = mapped_column(DateTime)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    season: Mapped[Season] = relationship()
    competition: Mapped[Competition] = relationship()
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])

    __table_args__ = (
        CheckConstraint("home_team_id <> away_team_id", name="ck_match_different_teams"),
    )


class Participation(Base):
    __tablename__ = "participations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    shirt_number: Mapped[int | None] = mapped_column(Integer)
    starter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[str | None] = mapped_column(String(20))
    minute_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minute_out: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    captain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    match: Mapped[Match] = relationship()
    team: Mapped[Team] = relationship()
    player: Mapped[Player] = relationship()

    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="uq_match_player"),
        CheckConstraint("minute_in >= 0", name="ck_minute_in"),
        CheckConstraint("minute_out >= minute_in", name="ck_minute_order"),
    )


class ReportAssignment(Base):
    __tablename__ = "report_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    match: Mapped[Match] = relationship(foreign_keys=[match_id])
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    __table_args__ = (UniqueConstraint("match_id", "user_id", name="uq_match_assignment_user"),)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    own_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    rival_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    rival_level: Mapped[str | None] = mapped_column(String(40))
    opponent_overview: Mapped[str | None] = mapped_column(Text)
    own_team_note: Mapped[str | None] = mapped_column(Text)
    key_takeaways: Mapped[str | None] = mapped_column(Text)
    standout_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime)

    match: Mapped[Match] = relationship()
    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])
    own_team: Mapped[Team] = relationship(foreign_keys=[own_team_id])
    rival_team: Mapped[Team] = relationship(foreign_keys=[rival_team_id])

    __table_args__ = (
        UniqueConstraint("match_id", "reporter_id", name="uq_match_reporter"),
    )


class PlayerEvaluation(Base):
    __tablename__ = "player_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    participation_id: Mapped[int | None] = mapped_column(ForeignKey("participations.id", ondelete="SET NULL"))
    evaluation_scope: Mapped[str] = mapped_column(String(20), default="rival", nullable=False)
    observation_status: Mapped[str] = mapped_column(String(30), default="evaluated", nullable=False)
    general_rating: Mapped[float | None] = mapped_column(Float)
    technical_rating: Mapped[float | None] = mapped_column(Float)
    tactical_rating: Mapped[float | None] = mapped_column(Float)
    physical_rating: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[str | None] = mapped_column(String(20))
    recommendation: Mapped[str | None] = mapped_column(String(80))
    strengths: Mapped[str | None] = mapped_column(Text)
    short_note: Mapped[str | None] = mapped_column(Text)
    detailed_note: Mapped[str | None] = mapped_column(Text)
    standout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pdf_include: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    report: Mapped[Report] = relationship()
    player: Mapped[Player] = relationship()
    team: Mapped[Team] = relationship()
    participation: Mapped[Participation | None] = relationship()

    __table_args__ = (UniqueConstraint("report_id", "player_id", name="uq_report_player"),)


class ReportVersion(Base):
    __tablename__ = "report_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    report: Mapped[Report] = relationship()
    __table_args__ = (UniqueConstraint("report_id", "version", name="uq_report_version"),)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    report_version_id: Mapped[int | None] = mapped_column(ForeignKey("report_versions.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), default="full", nullable=False)
    storage_bucket: Mapped[str | None] = mapped_column(String(120))
    storage_path: Mapped[str | None] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(80))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    storage_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("report_id", "version", "document_type", name="uq_report_document_version_type"),
    )


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Seguimiento", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    next_review_date: Mapped[date | None] = mapped_column(Date)
    target_match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    closed_reason: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    player: Mapped[Player] = relationship()
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assigned_to])
    target_match: Mapped[Match | None] = relationship(foreign_keys=[target_match_id])
    __table_args__ = (UniqueConstraint("player_id", name="uq_followup_player"),)


class FollowUpHistory(Base):
    __tablename__ = "follow_up_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    follow_up_id: Mapped[int] = mapped_column(ForeignKey("follow_ups.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ConsolidatedReport(Base):
    __tablename__ = "consolidated_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    rival_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    overview: Mapped[str | None] = mapped_column(Text)
    key_takeaways: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)

    match: Mapped[Match] = relationship()
    rival_team: Mapped[Team] = relationship()
    __table_args__ = (UniqueConstraint("match_id", "rival_team_id", name="uq_consolidated_match_rival"),)


class ConsolidatedPlayerEvaluation(Base):
    __tablename__ = "consolidated_player_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consolidated_report_id: Mapped[int] = mapped_column(ForeignKey("consolidated_reports.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    final_rating: Mapped[float | None] = mapped_column(Float)
    final_recommendation: Mapped[str | None] = mapped_column(String(80))
    consensus_note: Mapped[str | None] = mapped_column(Text)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dispersion: Mapped[float | None] = mapped_column(Float)
    confidence_summary: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    player: Mapped[Player] = relationship()
    __table_args__ = (
        UniqueConstraint("consolidated_report_id", "player_id", name="uq_consolidated_player"),
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)
    before_json: Mapped[str | None] = mapped_column(Text)
    after_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
