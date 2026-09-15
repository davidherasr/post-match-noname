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
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    session_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    # 4.2 · capability independent from organizational roles. Only users who
    # actually perform individual player tracking need this permission.
    can_track_players: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[User] = relationship()
    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_role"),)


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
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime)
    schedule_status: Mapped[str] = mapped_column(String(30), default="provisional", nullable=False)
    fixture_type: Mapped[str] = mapped_column(String(30), default="league", nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    venue: Mapped[str | None] = mapped_column(String(160))
    home_formation: Mapped[str | None] = mapped_column(String(40))
    away_formation: Mapped[str | None] = mapped_column(String(40))
    # 4.0 · Match Study context. Formation knowledge is independent per team:
    # one side can have a known XI/shape while the other is intentionally roster-only.
    video_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    video_reference: Mapped[str | None] = mapped_column(Text)
    home_formation_known: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    away_formation_known: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    study_notes: Mapped[str | None] = mapped_column(Text)
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


class StaffSportingWeight(Base):
    __tablename__ = "staff_sporting_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    own_match_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    neutral_match_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    updater: Mapped[User] = relationship(foreign_keys=[updated_by])
    __table_args__ = (UniqueConstraint("user_id", name="uq_staff_sporting_weight_user"),)


class MatchOpinion(Base):
    __tablename__ = "match_opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    home_team_rating: Mapped[float | None] = mapped_column(Float)
    away_team_rating: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    match: Mapped["Match"] = relationship()
    user: Mapped[User] = relationship()
    __table_args__ = (UniqueConstraint("match_id", "user_id", name="uq_match_opinion_user"),)


class MatchOpinionPlayer(Base):
    __tablename__ = "match_opinion_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opinion_id: Mapped[int] = mapped_column(ForeignKey("match_opinions.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    opinion: Mapped[MatchOpinion] = relationship()
    player: Mapped[Player] = relationship()
    team: Mapped[Team] = relationship()
    __table_args__ = (UniqueConstraint("opinion_id", "player_id", name="uq_match_opinion_player"),)


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
    # 4.2 · team-performance ratings are distinct from individual player ratings.
    own_team_rating: Mapped[float | None] = mapped_column(Float)
    rival_team_rating: Mapped[float | None] = mapped_column(Float)
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


class PostMatchDraft(Base):
    __tablename__ = "postmatch_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    season_id: Mapped[int | None] = mapped_column(ForeignKey("seasons.id", ondelete="SET NULL"))
    title: Mapped[str | None] = mapped_column(String(180))
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    creator: Mapped[User] = relationship()
    season: Mapped[Season | None] = relationship()


class LeaguePlayerProfile(Base):
    __tablename__ = "league_player_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    decision_status: Mapped[str] = mapped_column(String(40), default="Base", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    director_note: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    player: Mapped[Player] = relationship()
    updater: Mapped[User] = relationship()
    __table_args__ = (UniqueConstraint("player_id", name="uq_league_player_profile"),)


class ScoutingList(Base):
    __tablename__ = "scouting_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    list_type: Mapped[str] = mapped_column(String(30), default="custom", nullable=False)
    formation: Mapped[str | None] = mapped_column(String(40))
    season_id: Mapped[int | None] = mapped_column(ForeignKey("seasons.id", ondelete="SET NULL"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    season: Mapped[Season | None] = relationship()
    creator: Mapped[User] = relationship()


class ScoutingListItem(Base):
    __tablename__ = "scouting_list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("scouting_lists.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[str | None] = mapped_column(String(20))
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    scouting_list: Mapped[ScoutingList] = relationship()
    player: Mapped[Player] = relationship()
    __table_args__ = (UniqueConstraint("list_id", "player_id", name="uq_scouting_list_player"),)


class ScoutedPlayerProfile(Base):
    __tablename__ = "scouted_player_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="candidate", nullable=False)
    model_position: Mapped[str | None] = mapped_column(String(20))
    model_role: Mapped[str | None] = mapped_column(String(80))
    fit_score: Mapped[float | None] = mapped_column(Float)
    current_level: Mapped[float | None] = mapped_column(Float)
    potential_score: Mapped[float | None] = mapped_column(Float)
    final_decision: Mapped[str | None] = mapped_column(String(50))
    director_summary: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)

    player: Mapped[Player] = relationship()
    requester: Mapped[User] = relationship(foreign_keys=[requested_by])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assigned_to])
    approver: Mapped[User | None] = relationship(foreign_keys=[approved_by])
    __table_args__ = (UniqueConstraint("player_id", name="uq_scouted_player_profile"),)


class ScoutReview(Base):
    __tablename__ = "scout_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("scouted_player_profiles.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    observed_position: Mapped[str | None] = mapped_column(String(20))
    technical_rating: Mapped[float | None] = mapped_column(Float)
    tactical_rating: Mapped[float | None] = mapped_column(Float)
    physical_rating: Mapped[float | None] = mapped_column(Float)
    mental_rating: Mapped[float | None] = mapped_column(Float)
    current_level: Mapped[float | None] = mapped_column(Float)
    potential_score: Mapped[float | None] = mapped_column(Float)
    model_fit_score: Mapped[float | None] = mapped_column(Float)
    attributes_json: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[str | None] = mapped_column(Text)
    weaknesses: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)

    profile: Mapped[ScoutedPlayerProfile] = relationship()
    reviewer: Mapped[User] = relationship()
    __table_args__ = (UniqueConstraint("profile_id", "reviewer_id", name="uq_scout_review_reviewer"),)


class ScoutMission(Base):
    __tablename__ = "scout_missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    mission_type: Mapped[str] = mapped_column(String(40), default="player", nullable=False)
    target_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text)
    focus_json: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    assigned_to: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    match: Mapped[Match] = relationship()
    target_team: Mapped[Team | None] = relationship()
    assignee: Mapped[User] = relationship(foreign_keys=[assigned_to])
    requester: Mapped[User] = relationship(foreign_keys=[requested_by])


class ScoutMissionTarget(Base):
    __tablename__ = "scout_mission_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("scout_missions.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    mission: Mapped[ScoutMission] = relationship()
    player: Mapped[Player] = relationship()
    __table_args__ = (UniqueConstraint("mission_id", "player_id", name="uq_scout_mission_player"),)


class ScoutObservation(Base):
    __tablename__ = "scout_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # profile_id is retained as a compatibility/identity bridge. New scouting flows
    # use ScoutObservation as the only observation event source of truth.
    profile_id: Mapped[int] = mapped_column(ForeignKey("scouted_player_profiles.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id", ondelete="SET NULL"))
    mission_id: Mapped[int | None] = mapped_column(ForeignKey("scout_missions.id", ondelete="SET NULL"))
    model_role_id: Mapped[int | None] = mapped_column(ForeignKey("game_model_roles.id", ondelete="SET NULL"))
    legacy_review_id: Mapped[int | None] = mapped_column(ForeignKey("scout_reviews.id", ondelete="SET NULL"), unique=True)
    source_type: Mapped[str] = mapped_column(String(30), default="specific", nullable=False)
    observation_level: Mapped[str] = mapped_column(String(20), default="observation", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    observed_position: Mapped[str | None] = mapped_column(String(20))
    general_rating: Mapped[float | None] = mapped_column(Float)
    technical_rating: Mapped[float | None] = mapped_column(Float)
    tactical_rating: Mapped[float | None] = mapped_column(Float)
    physical_rating: Mapped[float | None] = mapped_column(Float)
    mental_rating: Mapped[float | None] = mapped_column(Float)
    current_level: Mapped[float | None] = mapped_column(Float)
    potential_score: Mapped[float | None] = mapped_column(Float)
    model_fit_score: Mapped[float | None] = mapped_column(Float)
    attributes_json: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[str | None] = mapped_column(Text)
    weaknesses: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(String(80))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    profile: Mapped[ScoutedPlayerProfile] = relationship()
    reviewer: Mapped[User] = relationship()
    match: Mapped[Match | None] = relationship()
    mission: Mapped[ScoutMission | None] = relationship()
    model_role: Mapped["GameModelRole | None"] = relationship(foreign_keys=[model_role_id])
    legacy_review: Mapped[ScoutReview | None] = relationship(foreign_keys=[legacy_review_id])


class GameModelRole(Base):
    __tablename__ = "game_model_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    creator: Mapped[User] = relationship()
    __table_args__ = (UniqueConstraint("name", "position", name="uq_game_model_role"),)


class GameModelCriterion(Base):
    __tablename__ = "game_model_criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("game_model_roles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="Táctico", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    role: Mapped[GameModelRole] = relationship()
    __table_args__ = (UniqueConstraint("role_id", "name", name="uq_model_role_criterion"),)


class SquadNeed(Base):
    __tablename__ = "squad_needs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    model_role_id: Mapped[int] = mapped_column(ForeignKey("game_model_roles.id", ondelete="CASCADE"), nullable=False)
    need_level: Mapped[str] = mapped_column(String(20), default="Media", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Abierta", nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    season: Mapped[Season] = relationship()
    model_role: Mapped[GameModelRole] = relationship()
    updater: Mapped[User] = relationship()
    __table_args__ = (UniqueConstraint("season_id", "model_role_id", name="uq_squad_need_role"),)


class PlayerSeasonDecision(Base):
    __tablename__ = "player_season_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    model_role_id: Mapped[int | None] = mapped_column(ForeignKey("game_model_roles.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(40), default="Base", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    director_note: Mapped[str | None] = mapped_column(Text)
    fit_score: Mapped[float | None] = mapped_column(Float)
    current_level: Mapped[float | None] = mapped_column(Float)
    potential_score: Mapped[float | None] = mapped_column(Float)
    criteria_json: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    season: Mapped[Season] = relationship()
    player: Mapped[Player] = relationship()
    model_role: Mapped[GameModelRole | None] = relationship()
    updater: Mapped[User] = relationship()
    __table_args__ = (UniqueConstraint("season_id", "player_id", name="uq_player_season_decision"),)


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
