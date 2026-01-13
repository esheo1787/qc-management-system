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
    # 작업자 상태 변경
    STARTED = "STARTED"
    SUBMITTED = "SUBMITTED"
    REWORK_REQUESTED = "REWORK_REQUESTED"
    ACCEPTED = "ACCEPTED"

    # 어드민 액션
    ASSIGN = "ASSIGN"  # 케이스 배정
    REASSIGN = "REASSIGN"  # 재배정
    REJECT = "REJECT"  # 검수 반려 (REWORK_REQUESTED와 별도)

    # 작업자 피드백 액션
    FEEDBACK_CREATED = "FEEDBACK_CREATED"
    FEEDBACK_UPDATED = "FEEDBACK_UPDATED"
    FEEDBACK_DELETED = "FEEDBACK_DELETED"
    FEEDBACK_SUBMIT = "FEEDBACK_SUBMIT"  # QC 피드백 제출 (제출 버튼과 함께)

    # 작업자 기타 액션
    CANCEL = "CANCEL"  # 작업 취소
    EDIT = "EDIT"  # 정보 수정


class Difficulty(str, PyEnum):
    EASY = "EASY"
    NORMAL = "NORMAL"
    HARD = "HARD"
    VERY_HARD = "VERY_HARD"


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
    reviewer_qc_feedbacks: Mapped[list["ReviewerQcFeedback"]] = relationship(
        "ReviewerQcFeedback", back_populates="reviewer"
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
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)  # 하위 호환용
    original_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # 원본 폴더명
    nas_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 폴더 경로
    hospital: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    slice_thickness_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False
    )
    part_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parts.id"), nullable=False
    )

    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty), default=Difficulty.NORMAL, nullable=False
    )
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus), default=CaseStatus.TODO, nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    assigned_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 추가 필드
    wwl: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Window Width/Level (예: "350/40")
    memo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 작업자 메모
    tags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 배열 (예: '["원본", "카데바"]')

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
    reviewer_qc_feedbacks: Mapped[list["ReviewerQcFeedback"]] = relationship(
        "ReviewerQcFeedback", back_populates="case", order_by="ReviewerQcFeedback.created_at"
    )


class PreQcSummary(Base):
    __tablename__ = "preqc_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), unique=True, nullable=False
    )

    # 기본 정보
    folder_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    slice_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spacing_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # [x, y, z]
    volume_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 슬라이스 두께
    slice_thickness_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    slice_thickness_flag: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # OK, WARN, THICK

    # 노이즈
    noise_sigma_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    noise_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # LOW, MODERATE, HIGH

    # 조영제
    delta_hu: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contrast_flag: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # GOOD, BORDERLINE, POOR

    # 혈관 가시성
    vessel_voxel_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    edge_strength: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vascular_visibility_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0~5
    vascular_visibility_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # EXCELLENT, USABLE, BORDERLINE, POOR

    # 기타
    difficulty: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # EASY, NORMAL, HARD, VERY_HARD
    flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_segments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    status: "PASS" | "WARN" | "INCOMPLETE"
      - PASS: 문제 없음
      - WARN: 경미한 문제, 재작업 필요
      - INCOMPLETE: 심각한 문제, 재작업 필요 + 작업자 평가 반영
    """
    __tablename__ = "autoqc_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), unique=True, nullable=False
    )
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default=None)

    # 세그먼트 관련
    missing_segments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    name_mismatches_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_segments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 이슈 관련
    issues_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issue_count_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 기존 필드 (하위 호환)
    geometry_mismatch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    warnings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 수정 추적
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # QC 실행 횟수
    previous_issue_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 이전 총 이슈 수

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
    Workers can report QC issue fixes, additional fixes, and memos.
    One feedback per case per worker (upsert pattern).
    """
    __tablename__ = "worker_qc_feedbacks"
    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_case_worker_feedback"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # QC 이슈 수정 여부 (issues_json 파싱해서 각 이슈별 체크)
    # [{"issue_id": 1, "segment": "IVC", "code": "SEGMENT_NAME_MISMATCH", "fixed": true}]
    qc_fixes_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 추가 수정 사항 (QC에 없지만 수정한 것)
    # [{"segment": "Renal_Artery", "description": "구멍 메움"}]
    additional_fixes_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 메모
    memo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 하위 호환 필드 (기존 feedback)
    qc_result_error: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # True if worker thinks QC result is wrong
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=now_kst
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="worker_qc_feedbacks")
    user: Mapped["User"] = relationship("User", back_populates="worker_qc_feedbacks")


class ReviewerQcFeedback(Base):
    """
    검수자 QC 불일치 기록.
    Auto-QC 결과와 검수자 판단이 다른 경우 상세 내용 기록.
    """
    __tablename__ = "reviewer_qc_feedbacks"
    __table_args__ = (
        UniqueConstraint("case_id", "reviewer_id", name="uq_case_reviewer_feedback"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False
    )
    reviewer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # 불일치 여부
    has_disagreement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 불일치 유형: "MISSED" (놓친 문제) / "FALSE_ALARM" (잘못된 경고)
    disagreement_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # 상세 내용
    disagreement_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 해당 세그먼트 목록: ["IVC", "Aorta"]
    disagreement_segments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 검수 메모 (일반 메모)
    review_memo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=now_kst
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="reviewer_qc_feedbacks")
    reviewer: Mapped["User"] = relationship("User", back_populates="reviewer_qc_feedbacks")
