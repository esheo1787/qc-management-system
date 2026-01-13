"""
Pydantic v2 Schemas for API request/response validation.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from models import ActionType, CaseStatus, Difficulty, EventType, TimeOffType, UserRole
from typing import List


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
    case_uid: str = Field(..., min_length=1, max_length=100)  # 케이스 ID
    original_name: Optional[str] = Field(None, max_length=200)  # 원본 이름 (폴더명)
    display_name: Optional[str] = Field(None, max_length=200)  # 하위 호환용
    nas_path: Optional[str] = Field(None, max_length=500)  # 폴더 경로
    hospital: Optional[str] = Field(None, max_length=200)
    slice_thickness_mm: Optional[float] = None  # 두께(mm)
    project_name: str = Field(..., min_length=1)  # 프로젝트
    part_name: str = Field(..., min_length=1)  # 부위
    difficulty: Difficulty = Difficulty.NORMAL  # 난이도
    metadata_json: Optional[str] = None
    preqc: Optional[PreQcInput] = None
    # 추가 필드
    wwl: Optional[str] = Field(None, max_length=50)  # Window Width/Level (예: "350/40")
    memo: Optional[str] = None
    tags: Optional[List[str]] = None  # 태그 목록


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
    # 추가 필드
    wwl: Optional[str] = None
    memo: Optional[str] = None
    tags_json: Optional[str] = None

    model_config = {"from_attributes": True}


class CaseListResponse(BaseModel):
    total: int
    cases: list[CaseListItem]


# Case Detail
class PreQcSummaryResponse(BaseModel):
    id: int
    case_id: int

    # 기본 정보
    folder_path: Optional[str]
    slice_count: Optional[int]
    spacing_json: Optional[str]
    volume_file: Optional[str]

    # 슬라이스 두께
    slice_thickness_mm: Optional[float]
    slice_thickness_flag: Optional[str]

    # 노이즈
    noise_sigma_mean: Optional[float]
    noise_level: Optional[str]

    # 조영제
    delta_hu: Optional[float]
    contrast_flag: Optional[str]

    # 혈관 가시성
    vessel_voxel_ratio: Optional[float]
    edge_strength: Optional[float]
    vascular_visibility_score: Optional[float]
    vascular_visibility_level: Optional[str]

    # 기타
    difficulty: Optional[str]
    flags_json: Optional[str]
    expected_segments_json: Optional[str]
    notes: Optional[str]

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
    # 추가 필드
    wwl: Optional[str] = None
    memo: Optional[str] = None
    tags_json: Optional[str] = None

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


# PreQC Summary (stored from local client)
class PreQcSummaryCreateRequest(BaseModel):
    case_id: int

    # 기본 정보
    folder_path: Optional[str] = Field(None, max_length=500)
    slice_count: Optional[int] = None
    spacing: Optional[List[float]] = None  # JSON으로 변환하여 저장
    volume_file: Optional[str] = Field(None, max_length=255)

    # 슬라이스 두께
    slice_thickness_mm: Optional[float] = None
    slice_thickness_flag: Optional[str] = Field(None, max_length=20)  # "OK", "WARN", "THICK"

    # 노이즈
    noise_sigma_mean: Optional[float] = None
    noise_level: Optional[str] = Field(None, max_length=20)  # "LOW", "MODERATE", "HIGH"

    # 조영제
    delta_hu: Optional[float] = None
    contrast_flag: Optional[str] = Field(None, max_length=20)  # "GOOD", "BORDERLINE", "POOR"

    # 혈관 가시성
    vessel_voxel_ratio: Optional[float] = None
    edge_strength: Optional[float] = None
    vascular_visibility_score: Optional[float] = None
    vascular_visibility_level: Optional[str] = Field(None, max_length=20)  # "EXCELLENT", "USABLE", "BORDERLINE", "POOR"

    # 기타
    difficulty: Optional[str] = Field(None, max_length=10)  # "EASY", "NORMAL", "HARD", "VERY_HARD"
    flags: Optional[List[str]] = None  # JSON으로 변환하여 저장
    expected_segments: Optional[List[str]] = None  # JSON으로 변환하여 저장
    notes: Optional[str] = None

    # 하위 호환 필드
    flags_json: Optional[str] = None
    expected_segments_json: Optional[str] = None


# AutoQC Summary (stored from local client)
class AutoQcSummaryCreateRequest(BaseModel):
    case_id: int
    status: Optional[str] = None  # "PASS", "WARN", "INCOMPLETE"

    # 세그먼트 관련
    missing_segments: Optional[list[str]] = None  # 누락된 필수 세그먼트
    name_mismatches: Optional[list[dict]] = None  # 이름 불일치 [{"expected": "IVC", "found": "ivc", "type": "case_mismatch"}]
    extra_segments: Optional[list[str]] = None  # 추가 세그먼트 (기록용)

    # 이슈 관련
    issues: Optional[list[dict]] = None  # 전체 이슈 목록
    issue_count: Optional[dict] = None  # {"warn_level": 1, "incomplete_level": 0}

    # 기존 필드 (하위 호환)
    geometry_mismatch: bool = False
    warnings_json: Optional[str] = None


class AutoQcSummaryResponse(BaseModel):
    id: int
    case_id: int
    status: Optional[str]  # "PASS", "WARN", "INCOMPLETE"

    # 세그먼트 관련
    missing_segments_json: Optional[str]
    name_mismatches_json: Optional[str]
    extra_segments_json: Optional[str]

    # 이슈 관련
    issues_json: Optional[str]
    issue_count_json: Optional[str]

    # 기존 필드 (하위 호환)
    geometry_mismatch: bool
    warnings_json: Optional[str]

    # 수정 추적
    revision: int = 1  # QC 실행 횟수
    previous_issue_count: Optional[int] = None  # 이전 총 이슈 수

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
    autoqc_status: Optional[str]  # "PASS", "WARN", "INCOMPLETE"
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
    false_positives: int  # autoqc PASS but rework_requested
    false_negatives: int  # autoqc WARN/INCOMPLETE but accepted
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

# QC 이슈 수정 항목
class QcFixItem(BaseModel):
    issue_id: int  # Auto-QC issues_json에서의 인덱스
    segment: str
    code: str  # MISSING_REQUIRED, SEGMENT_NAME_MISMATCH, OVERLAP, etc.
    fixed: bool = False


# 추가 수정 항목 (QC에 없지만 수정한 것)
class AdditionalFixItem(BaseModel):
    segment: str
    description: str


class WorkerQcFeedbackCreateRequest(BaseModel):
    case_id: int
    # 새로운 필드
    qc_fixes: Optional[List[QcFixItem]] = None  # QC 이슈별 수정 여부
    additional_fixes: Optional[List[AdditionalFixItem]] = None  # 추가 수정 사항
    memo: Optional[str] = Field(None, max_length=2000)  # 작업 메모
    # 하위 호환
    qc_result_error: bool = False  # True if worker thinks QC result is wrong
    feedback_text: Optional[str] = Field(None, max_length=2000)


class WorkerQcFeedbackResponse(BaseModel):
    id: int
    case_id: int
    user_id: int
    username: str
    # 새로운 필드
    qc_fixes_json: Optional[str]
    additional_fixes_json: Optional[str]
    memo: Optional[str]
    # 하위 호환
    qc_result_error: bool
    feedback_text: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class WorkerQcFeedbackListResponse(BaseModel):
    feedbacks: list[WorkerQcFeedbackResponse]


# QC 이슈 수정율 계산용
class FeedbackStats(BaseModel):
    total_issues: int  # 전체 이슈 수
    fixed_issues: int  # 수정 완료된 이슈 수
    fix_rate: float  # fixed_issues / total_issues
