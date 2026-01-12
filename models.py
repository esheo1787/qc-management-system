"""
SQLAlchemy 2.0 Database Models.
All datetime fields are timezone-aware (Asia/Seoul).
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from datetime import date as date_type

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config import TIMEZONE


def now_kst() -> datetime:
    """Return current datetime in Asia/Seoul timezone."""
    return datetime.now(TIMEZONE)


# Enums
class UserRole(str, PyEnum):
    ADMIN = "ADMIN"
    WORKER = "WORKER"


class CaseStatus(str, PyEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    REWORK = "REWORK"
    ACCEPTED = "ACCEPTED"


class EventType(str, PyEnum):
    STARTED = "STARTED"
    SUBMITTED = "SUBMITTED"
    REWORK_REQUESTED = "REWORK_REQUESTED"
    ACCEPTED = "ACCEPTED"


class Difficulty(str, PyEnum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"


class ActionType(str, PyEnum):
    START = "START"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    SUBMIT = "SUBMIT"
    REWORK_START = "REWORK_START"


class TimeOffType(str, PyEnum):
    VACATION = "VACATION"  # Full day off (8h)
    HALF_DAY = "HALF_DAY"  # Half day off (4h)


# Base class
class Base(DeclarativeBase):
    pass


# Models
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    assigned_cases: Mapped[list["Case"]] = relationship(
        "Case", back_populates="assigned_user", foreign_keys="Case.assigned_user_id"
    )
    events: Mapped[list["Event"]] = relationship("Event", back_populates="user")
    review_notes: Mapped[list["ReviewNote"]] = relationship(
        "ReviewNote", back_populates="reviewer"
    )
    worklogs: Mapped[list["WorkLog"]] = relationship("WorkLog", back_populates="user")
    timeoffs: Mapped[list["UserTimeOff"]] = relationship("UserTimeOff", back_populates="user")
    worker_qc_feedbacks: Mapped[list["WorkerQcFeedback"]] = relationship(
        "WorkerQcFeedback", back_populates="user"
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="project")
    definition_links: Mapped[list["ProjectDefinitionLink"]] = relationship(
        "ProjectDefinitionLink", back_populates="project", order_by="ProjectDefinitionLink.created_at"
    )


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="part")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_uid: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    nas_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hospital: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    slice_thickness_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False
    )
    part_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parts.id"), nullable=False
    )

    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty), default=Difficulty.MID, nullable=False
    )
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus), default=CaseStatus.TODO, nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    assigned_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    worker_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="cases")
    part: Mapped["Part"] = relationship("Part", back_populates="cases")
    assigned_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="assigned_cases", foreign_keys=[assigned_user_id]
    )
    preqc_summary: Mapped[Optional["PreQcSummary"]] = relationship(
        "PreQcSummary", back_populates="case", uselist=False
    )
    events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="case", order_by="Event.created_at"
    )
    review_notes: Mapped[list["ReviewNote"]] = relationship(
        "ReviewNote", back_populates="case", order_by="ReviewNote.created_at"
    )
    worklogs: Mapped[list["WorkLog"]] = relationship(
        "WorkLog", back_populates="case", order_by="WorkLog.timestamp"
    )
    autoqc_summary: Mapped[Optional["AutoQcSummary"]] = relationship(
        "AutoQcSummary", back_populates="case", uselist=False
    )
    tags: Mapped[list["CaseTag"]] = relationship(
        "CaseTag", back_populates="case", order_by="CaseTag.created_at"
    )
    worker_qc_feedbacks: Mapped[list["WorkerQcFeedback"]] = relationship(
        "WorkerQcFeedback", back_populates="case", order_by="WorkerQcFeedback.created_at"
    )


class PreQcSummary(Base):
    __tablename__ = "preqc_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), unique=True, nullable=False
    )
    flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    slice_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expected_segments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="preqc_summary")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    event_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="events")
    user: Mapped["User"] = relationship("User", back_populates="events")


class ReviewNote(Base):
    __tablename__ = "review_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False
    )
    reviewer_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    qc_summary_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    extra_tags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="review_notes")
    reviewer: Mapped["User"] = relationship("User", back_populates="review_notes")


class AppConfig(Base):
    __tablename__ = "app_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)


class WorkLog(Base):
    __tablename__ = "worklogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="worklogs")
    user: Mapped["User"] = relationship("User", back_populates="worklogs")


class UserTimeOff(Base):
    __tablename__ = "user_timeoffs"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    type: Mapped[TimeOffType] = mapped_column(Enum(TimeOffType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="timeoffs")


class WorkCalendar(Base):
    __tablename__ = "work_calendars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    holidays_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Seoul")


class AutoQcSummary(Base):
    """
    Auto-QC summary from local client.
    Server only stores the summary - actual QC runs on local PC.
    """
    __tablename__ = "autoqc_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), unique=True, nullable=False
    )
    qc_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    missing_segments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    geometry_mismatch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    warnings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="autoqc_summary")


# ============================================================
# Step 5: Cohort Tagging + Definition Snapshot
# ============================================================

class CaseTag(Base):
    """
    Tag for research cohort grouping.
    Multiple tags can be applied to a single case.
    """
    __tablename__ = "case_tags"
    __table_args__ = (
        UniqueConstraint("case_id", "tag_text", name="uq_case_tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False
    )
    tag_text: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="tags")


class DefinitionSnapshot(Base):
    """
    Frozen definition version for reproducibility.
    Stores segment definitions, QC rules, etc. as JSON.
    """
    __tablename__ = "definition_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    project_links: Mapped[list["ProjectDefinitionLink"]] = relationship(
        "ProjectDefinitionLink", back_populates="definition_snapshot"
    )


class ProjectDefinitionLink(Base):
    """
    Links a project to a specific definition snapshot version.
    Enables version tracking per project.
    """
    __tablename__ = "project_definition_links"
    __table_args__ = (
        UniqueConstraint("project_id", "definition_snapshot_id", name="uq_project_definition"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False
    )
    definition_snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("definition_snapshots.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="definition_links")
    definition_snapshot: Mapped["DefinitionSnapshot"] = relationship(
        "DefinitionSnapshot", back_populates="project_links"
    )


class WorkerQcFeedback(Base):
    """
    Worker feedback on Auto-QC results.
    Workers can report if QC results are incorrect and describe additional fixes.
    Submitted before case submission.
    """
    __tablename__ = "worker_qc_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    qc_result_error: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # True if worker thinks QC result is wrong
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="worker_qc_feedbacks")
    user: Mapped["User"] = relationship("User", back_populates="worker_qc_feedbacks")
