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

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "username": "admin1",
                    "role": "ADMIN",
                    "is_active": True,
                }
            ]
        },
    }


# PreQC
class PreQcInput(BaseModel):
    flags_json: Optional[str] = None
    slice_count: Optional[int] = None
    expected_segments_json: Optional[str] = None


# Case Registration
class CaseRegisterItem(BaseModel):
    """케이스 등록 요청 항목"""
    case_uid: str = Field(..., min_length=1, max_length=100, description="케이스 고유 ID")
    original_name: Optional[str] = Field(None, max_length=200, description="원본 폴더명")
    display_name: Optional[str] = Field(None, max_length=200, description="표시명 (하위 호환)")
    nas_path: Optional[str] = Field(None, max_length=500, description="NAS 폴더 경로")
    hospital: Optional[str] = Field(None, max_length=200, description="병원명")
    slice_thickness_mm: Optional[float] = Field(None, description="슬라이스 두께 (mm)")
    project_name: str = Field(..., min_length=1, description="프로젝트명")
    part_name: str = Field(..., min_length=1, description="부위명")
    difficulty: Difficulty = Field(Difficulty.NORMAL, description="난이도 (EASY/NORMAL/HARD/VERY_HARD)")
    metadata_json: Optional[str] = Field(None, description="추가 메타데이터 (JSON 문자열)")
    preqc: Optional[PreQcInput] = Field(None, description="Pre-QC 입력 데이터")
    wwl: Optional[str] = Field(None, max_length=50, description="Window Width/Level (예: 350/40)")
    memo: Optional[str] = Field(None, description="메모")
    tags: Optional[List[str]] = Field(None, description="태그 목록")


class BulkRegisterRequest(BaseModel):
    """케이스 일괄 등록 요청"""
    cases: list[CaseRegisterItem] = Field(..., min_length=1, description="등록할 케이스 목록")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "cases": [
                        {
                            "case_uid": "CASE_001",
                            "project_name": "Project_A",
                            "part_name": "Abdomen",
                            "hospital": "Hospital_A",
                            "difficulty": "NORMAL",
                        },
                        {
                            "case_uid": "CASE_002",
                            "project_name": "Project_A",
                            "part_name": "Chest",
                            "hospital": "Hospital_B",
                            "difficulty": "HARD",
                        },
                    ]
                }
            ]
        }
    }


class BulkRegisterResponse(BaseModel):
    """케이스 일괄 등록 응답"""
    created_count: int = Field(..., description="생성된 케이스 수")
    skipped_count: int = Field(..., description="건너뛴 케이스 수 (이미 존재)")
    created_case_uids: list[str] = Field(..., description="생성된 케이스 UID 목록")
    skipped_case_uids: list[str] = Field(..., description="건너뛴 케이스 UID 목록")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "created_count": 2,
                    "skipped_count": 0,
                    "created_case_uids": ["CASE_001", "CASE_002"],
                    "skipped_case_uids": [],
                }
            ]
        }
    }


# Assignment
class AssignRequest(BaseModel):
    """케이스 할당 요청"""
    case_id: int = Field(..., description="할당할 케이스 ID")
    user_id: int = Field(..., description="할당받을 사용자 ID")

    model_config = {
        "json_schema_extra": {
            "examples": [{"case_id": 1, "user_id": 2}]
        }
    }


class AssignResponse(BaseModel):
    """케이스 할당 응답"""
    case_id: int = Field(..., description="케이스 ID")
    case_uid: str = Field(..., description="케이스 UID")
    assigned_user_id: int = Field(..., description="할당된 사용자 ID")
    assigned_username: str = Field(..., description="할당된 사용자명")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "case_id": 1,
                    "case_uid": "CASE_001",
                    "assigned_user_id": 2,
                    "assigned_username": "worker1",
                }
            ]
        }
    }


# Event
class EventCreateRequest(BaseModel):
    """이벤트 생성 요청"""
    case_id: int = Field(..., description="케이스 ID")
    event_type: EventType = Field(..., description="이벤트 유형")
    idempotency_key: str = Field(..., min_length=1, max_length=100, description="멱등성 키 (중복 방지)")
    event_code: Optional[str] = Field(None, max_length=50, description="이벤트 코드")
    payload_json: Optional[str] = Field(None, description="추가 페이로드 (JSON)")
    expected_revision: Optional[int] = Field(None, description="낙관적 락용 예상 revision")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "case_id": 1,
                    "event_type": "ACCEPTED",
                    "idempotency_key": "accept-case1-20240115-001",
                    "expected_revision": 3,
                }
            ]
        }
    }


class EventResponse(BaseModel):
    """이벤트 응답"""
    id: int = Field(..., description="이벤트 ID")
    case_id: int = Field(..., description="케이스 ID")
    user_id: int = Field(..., description="이벤트 생성자 ID")
    event_type: EventType = Field(..., description="이벤트 유형")
    idempotency_key: str = Field(..., description="멱등성 키")
    event_code: Optional[str] = Field(None, description="이벤트 코드")
    payload_json: Optional[str] = Field(None, description="추가 페이로드")
    created_at: datetime = Field(..., description="생성 시각")
    case_status: CaseStatus = Field(..., description="변경 후 케이스 상태")
    case_revision: int = Field(..., description="변경 후 케이스 revision")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 10,
                    "case_id": 1,
                    "user_id": 1,
                    "event_type": "ACCEPTED",
                    "idempotency_key": "accept-case1-20240115-001",
                    "event_code": None,
                    "payload_json": None,
                    "created_at": "2024-01-15T14:30:00",
                    "case_status": "ACCEPTED",
                    "case_revision": 4,
                }
            ]
        },
    }


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
    """작업 로그 생성 요청"""
    case_id: int = Field(..., description="케이스 ID")
    action_type: ActionType = Field(..., description="작업 유형 (START/PAUSE/RESUME)")
    reason_code: Optional[str] = Field(None, max_length=50, description="사유 코드 (PAUSE 시)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"case_id": 1, "action_type": "START"},
                {"case_id": 1, "action_type": "PAUSE", "reason_code": "BREAK"},
            ]
        }
    }


class WorkLogResponse(BaseModel):
    """작업 로그 응답"""
    id: int = Field(..., description="WorkLog ID")
    case_id: int = Field(..., description="케이스 ID")
    user_id: int = Field(..., description="사용자 ID")
    action_type: ActionType = Field(..., description="작업 유형")
    reason_code: Optional[str] = Field(None, description="사유 코드")
    timestamp: datetime = Field(..., description="기록 시각")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 5,
                    "case_id": 1,
                    "user_id": 2,
                    "action_type": "START",
                    "reason_code": None,
                    "timestamp": "2024-01-15T09:00:00",
                }
            ]
        },
    }


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
    """휴가 등록 요청"""
    user_id: int
    date: date
    type: TimeOffType

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"user_id": 2, "date": "2024-01-20", "type": "VACATION"},
                {"user_id": 2, "date": "2024-01-21", "type": "HALF_DAY"},
            ]
        }
    }


class TimeOffResponse(BaseModel):
    """휴가 응답"""
    id: int
    user_id: int
    username: str
    date: date
    type: TimeOffType
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "user_id": 2,
                    "username": "worker1",
                    "date": "2024-01-20",
                    "type": "VACATION",
                    "created_at": "2024-01-15T10:00:00",
                }
            ]
        },
    }


class TimeOffListResponse(BaseModel):
    """휴가 목록 응답"""
    timeoffs: list[TimeOffResponse]


# Holidays (WorkCalendar)
class HolidayUpdateRequest(BaseModel):
    """공휴일 전체 업데이트 요청"""
    holidays: list[date] = Field(..., description="공휴일 날짜 목록")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"holidays": ["2024-01-01", "2024-02-09", "2024-02-10", "2024-03-01"]}
            ]
        }
    }


class HolidayListResponse(BaseModel):
    """공휴일 목록 응답"""
    holidays: list[date] = Field(..., description="공휴일 날짜 목록")
    timezone: str = Field(..., description="타임존")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "holidays": ["2024-01-01", "2024-02-09", "2024-02-10", "2024-03-01"],
                    "timezone": "Asia/Seoul",
                }
            ]
        }
    }


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
    """케이스 제출 요청"""
    case_id: int = Field(..., description="제출할 케이스 ID")
    idempotency_key: str = Field(..., min_length=1, max_length=100, description="멱등성 키")
    expected_revision: Optional[int] = Field(None, description="낙관적 락용 예상 revision")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "case_id": 1,
                    "idempotency_key": "submit-case1-20240115-001",
                    "expected_revision": 2,
                }
            ]
        }
    }


class SubmitResponse(BaseModel):
    """케이스 제출 응답"""
    worklog_id: int = Field(..., description="생성된 WorkLog ID")
    event_id: int = Field(..., description="생성된 Event ID")
    case_id: int = Field(..., description="케이스 ID")
    case_status: CaseStatus = Field(..., description="변경 후 케이스 상태")
    case_revision: int = Field(..., description="변경 후 revision")
    work_seconds: int = Field(..., description="총 작업 시간 (초)")
    work_duration: str = Field(..., description="작업 시간 (포맷팅)")
    man_days: float = Field(..., description="공수 (Man-Days, 8시간=1MD)")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "worklog_id": 15,
                    "event_id": 12,
                    "case_id": 1,
                    "case_status": "SUBMITTED",
                    "case_revision": 3,
                    "work_seconds": 3600,
                    "work_duration": "1시간 0분",
                    "man_days": 0.125,
                }
            ]
        },
    }


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
