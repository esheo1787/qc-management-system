"""
Pydantic v2 Schemas for API request/response validation.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from models import ActionType, CaseStatus, Difficulty, EventType, TimeOffType, UserRole


# Auth
class AuthMeResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


# PreQC
class PreQcInput(BaseModel):
    flags_json: Optional[str] = None
    slice_count: Optional[int] = None
    expected_segments_json: Optional[str] = None


# Case Registration
class CaseRegisterItem(BaseModel):
    case_uid: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    nas_path: Optional[str] = Field(None, max_length=500)
    hospital: Optional[str] = Field(None, max_length=200)
    slice_thickness_mm: Optional[float] = None
    project_name: str = Field(..., min_length=1)
    part_name: str = Field(..., min_length=1)
    difficulty: Difficulty = Difficulty.MID
    metadata_json: Optional[str] = None
    preqc: Optional[PreQcInput] = None


class BulkRegisterRequest(BaseModel):
    cases: list[CaseRegisterItem] = Field(..., min_length=1)


class BulkRegisterResponse(BaseModel):
    created_count: int
    skipped_count: int
    created_case_uids: list[str]
    skipped_case_uids: list[str]


# Assignment
class AssignRequest(BaseModel):
    case_id: int
    user_id: int


class AssignResponse(BaseModel):
    case_id: int
    case_uid: str
    assigned_user_id: int
    assigned_username: str


# Event
class EventCreateRequest(BaseModel):
    case_id: int
    event_type: EventType
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    event_code: Optional[str] = Field(None, max_length=50)
    payload_json: Optional[str] = None
    expected_revision: Optional[int] = None  # For optimistic locking


class EventResponse(BaseModel):
    id: int
    case_id: int
    user_id: int
    event_type: EventType
    idempotency_key: str
    event_code: Optional[str]
    payload_json: Optional[str]
    created_at: datetime
    case_status: CaseStatus
    case_revision: int

    model_config = {"from_attributes": True}


# Case List
class CaseListItem(BaseModel):
    id: int
    case_uid: str
    display_name: str
    hospital: Optional[str]
    project_name: str
    part_name: str
    difficulty: Difficulty
    status: CaseStatus
    revision: int
    assigned_user_id: Optional[int]
    assigned_username: Optional[str]
    started_at: Optional[datetime]
    worker_completed_at: Optional[datetime]
    accepted_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseListResponse(BaseModel):
    total: int
    cases: list[CaseListItem]


# Case Detail
class PreQcSummaryResponse(BaseModel):
    flags_json: Optional[str]
    slice_count: Optional[int]
    expected_segments_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EventListItem(BaseModel):
    id: int
    event_type: EventType
    user_id: int
    username: str
    event_code: Optional[str]
    payload_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewNoteItem(BaseModel):
    id: int
    reviewer_user_id: int
    reviewer_username: str
    qc_summary_confirmed: bool
    note_text: str
    extra_tags_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseDetailResponse(BaseModel):
    id: int
    case_uid: str
    display_name: str
    nas_path: Optional[str]
    hospital: Optional[str]
    slice_thickness_mm: Optional[float]
    project_name: str
    part_name: str
    difficulty: Difficulty
    status: CaseStatus
    revision: int
    assigned_user_id: Optional[int]
    assigned_username: Optional[str]
    metadata_json: Optional[str]
    started_at: Optional[datetime]
    worker_completed_at: Optional[datetime]
    accepted_at: Optional[datetime]
    created_at: datetime
    preqc_summary: Optional[PreQcSummaryResponse]
    events: list[EventListItem]
    review_notes: list[ReviewNoteItem]

    model_config = {"from_attributes": True}


# Review Note
class ReviewNoteCreateRequest(BaseModel):
    case_id: int
    note_text: str = Field(..., min_length=1)
    qc_summary_confirmed: bool = False
    extra_tags_json: Optional[str] = None


class ReviewNoteResponse(BaseModel):
    id: int
    case_id: int
    reviewer_user_id: int
    qc_summary_confirmed: bool
    note_text: str
    extra_tags_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# User List (for admin)
class UserListItem(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserListItem]


# WorkLog
class WorkLogCreateRequest(BaseModel):
    case_id: int
    action_type: ActionType
    reason_code: Optional[str] = Field(None, max_length=50)


class WorkLogResponse(BaseModel):
    id: int
    case_id: int
    user_id: int
    action_type: ActionType
    reason_code: Optional[str]
    timestamp: datetime

    model_config = {"from_attributes": True}


class WorkLogItem(BaseModel):
    id: int
    action_type: ActionType
    user_id: int
    username: str
    reason_code: Optional[str]
    timestamp: datetime

    model_config = {"from_attributes": True}


# TimeOff
class TimeOffCreateRequest(BaseModel):
    user_id: int
    date: date
    type: TimeOffType


class TimeOffResponse(BaseModel):
    id: int
    user_id: int
    username: str
    date: date
    type: TimeOffType
    created_at: datetime

    model_config = {"from_attributes": True}


class TimeOffListResponse(BaseModel):
    timeoffs: list[TimeOffResponse]


# Holidays (WorkCalendar)
class HolidayUpdateRequest(BaseModel):
    holidays: list[date] = Field(..., description="List of holiday dates")


class HolidayListResponse(BaseModel):
    holidays: list[date]
    timezone: str


# Capacity Metrics
class CapacityMetrics(BaseModel):
    user_id: int
    username: str
    period_start: date
    period_end: date
    total_workdays: int  # Excluding weekends and holidays
    available_hours: float  # total_workdays * 8 - timeoff_hours
    timeoff_hours: float  # Vacation=8h, HalfDay=4h
    actual_work_hours: float  # From worklogs
    utilization_rate: float  # actual_work_hours / available_hours


class TeamCapacityResponse(BaseModel):
    period_start: date
    period_end: date
    users: list[CapacityMetrics]
    total_available_hours: float
    total_actual_hours: float
    team_utilization_rate: float


# Submit (atomic WorkLog SUBMIT + Event SUBMITTED)
class SubmitRequest(BaseModel):
    case_id: int
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    expected_revision: Optional[int] = None


class SubmitResponse(BaseModel):
    worklog_id: int
    event_id: int
    case_id: int
    case_status: CaseStatus
    case_revision: int
    work_seconds: int
    work_duration: str
    man_days: float

    model_config = {"from_attributes": True}


# Case metrics (for detail view)
class CaseMetrics(BaseModel):
    work_seconds: int
    work_duration: str
    man_days: float
    timeline: str
    is_working: bool  # Currently in active session


# Extended Case Detail with WorkLogs and Metrics
class CaseDetailWithMetricsResponse(BaseModel):
    id: int
    case_uid: str
    display_name: str
    nas_path: Optional[str]
    hospital: Optional[str]
    slice_thickness_mm: Optional[float]
    project_name: str
    part_name: str
    difficulty: Difficulty
    status: CaseStatus
    revision: int
    assigned_user_id: Optional[int]
    assigned_username: Optional[str]
    metadata_json: Optional[str]
    started_at: Optional[datetime]
    worker_completed_at: Optional[datetime]
    accepted_at: Optional[datetime]
    created_at: datetime
    preqc_summary: Optional[PreQcSummaryResponse]
    events: list[EventListItem]
    review_notes: list[ReviewNoteItem]
    worklogs: list[WorkLogItem]
    metrics: CaseMetrics

    model_config = {"from_attributes": True}


# AutoQC Summary (stored from local client)
class AutoQcSummaryCreateRequest(BaseModel):
    case_id: int
    qc_pass: bool
    missing_segments_json: Optional[str] = None
    geometry_mismatch: bool = False
    warnings_json: Optional[str] = None


class AutoQcSummaryResponse(BaseModel):
    id: int
    case_id: int
    qc_pass: bool
    missing_segments_json: Optional[str]
    geometry_mismatch: bool
    warnings_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# QC Disagreement
class QcDisagreementItem(BaseModel):
    case_id: int
    case_uid: str
    display_name: str
    hospital: Optional[str]
    part_name: str
    difficulty: Difficulty
    autoqc_pass: bool
    case_status: CaseStatus
    disagreement_type: str  # "FALSE_POSITIVE" or "FALSE_NEGATIVE"
    accepted_at: Optional[datetime]
    rework_requested_at: Optional[datetime]


class QcDisagreementListResponse(BaseModel):
    total: int
    disagreements: list[QcDisagreementItem]


class QcDisagreementStats(BaseModel):
    total_cases_with_autoqc: int
    total_disagreements: int
    disagreement_rate: float
    false_positives: int  # autoqc_pass=True but rework_requested
    false_negatives: int  # autoqc_pass=False but accepted
    by_part: dict[str, dict]  # part_name -> {total, disagreements, rate}
    by_hospital: dict[str, dict]  # hospital -> {total, disagreements, rate}
    by_difficulty: dict[str, dict]  # difficulty -> {total, disagreements, rate}


# ============================================================
# Step 5: Cohort Tagging + Definition Snapshot
# ============================================================

# Case Tag
class CaseTagItem(BaseModel):
    id: int
    case_id: int
    tag_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplyTagsRequest(BaseModel):
    case_uids: list[str] = Field(..., min_length=1)
    tag_text: str = Field(..., min_length=1, max_length=100)


class ApplyTagsResponse(BaseModel):
    tag_text: str
    applied_count: int
    skipped_count: int  # Already had the tag
    not_found_count: int


class RemoveTagRequest(BaseModel):
    case_uids: list[str] = Field(..., min_length=1)
    tag_text: str = Field(..., min_length=1, max_length=100)


class RemoveTagResponse(BaseModel):
    tag_text: str
    removed_count: int


class TagListResponse(BaseModel):
    tags: list[str]  # Unique tag names


class CasesByTagResponse(BaseModel):
    tag_text: str
    total: int
    cases: list[CaseListItem]


# Definition Snapshot
class DefinitionSnapshotCreateRequest(BaseModel):
    version_name: str = Field(..., min_length=1, max_length=100)
    content_json: str = Field(..., min_length=2)  # Must be valid JSON


class DefinitionSnapshotResponse(BaseModel):
    id: int
    version_name: str
    content_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DefinitionSnapshotListResponse(BaseModel):
    definitions: list[DefinitionSnapshotResponse]


# Project-Definition Link
class ProjectDefinitionLinkRequest(BaseModel):
    project_id: int
    definition_snapshot_id: int


class ProjectDefinitionLinkResponse(BaseModel):
    id: int
    project_id: int
    project_name: str
    definition_snapshot_id: int
    definition_version_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectDefinitionListResponse(BaseModel):
    links: list[ProjectDefinitionLinkResponse]


# Cohort Filter (for metrics queries)
class CohortFilter(BaseModel):
    tag: Optional[str] = None
    project_id: Optional[int] = None
    definition_version: Optional[str] = None
    status: Optional[CaseStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CohortSummary(BaseModel):
    filter_applied: CohortFilter
    total_cases: int
    by_status: dict[str, int]
    by_difficulty: dict[str, int]
    by_part: dict[str, int]
    by_hospital: dict[str, int]
    total_work_seconds: int
    total_man_days: float
    avg_work_seconds_per_case: float


# ============================================================
# Worker QC Feedback
# ============================================================

class WorkerQcFeedbackCreateRequest(BaseModel):
    case_id: int
    qc_result_error: bool = False  # True if worker thinks QC result is wrong
    feedback_text: Optional[str] = Field(None, max_length=2000)


class WorkerQcFeedbackResponse(BaseModel):
    id: int
    case_id: int
    user_id: int
    username: str
    qc_result_error: bool
    feedback_text: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkerQcFeedbackListResponse(BaseModel):
    feedbacks: list[WorkerQcFeedbackResponse]
