"""
FastAPI API Routes.
All endpoints enforce authorization at the server level.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import CaseStatus, User, UserRole
from schemas import (
    ApplyTagsRequest,
    ApplyTagsResponse,
    AssignRequest,
    AssignResponse,
    AuthMeResponse,
    AutoQcSummaryCreateRequest,
    AutoQcSummaryResponse,
    BulkRegisterRequest,
    BulkRegisterResponse,
    CaseDetailResponse,
    CaseDetailWithMetricsResponse,
    CaseListResponse,
    CasesByTagResponse,
    CohortFilter,
    CohortSummary,
    DefinitionSnapshotCreateRequest,
    DefinitionSnapshotListResponse,
    DefinitionSnapshotResponse,
    EventCreateRequest,
    EventListItem,
    EventResponse,
    HolidayListResponse,
    HolidayUpdateRequest,
    PreQcSummaryCreateRequest,
    PreQcSummaryResponse,
    ProjectDefinitionLinkRequest,
    ProjectDefinitionLinkResponse,
    ProjectDefinitionListResponse,
    QcDisagreementListResponse,
    QcDisagreementStats,
    RemoveTagRequest,
    RemoveTagResponse,
    ReviewNoteCreateRequest,
    ReviewNoteResponse,
    SubmitRequest,
    SubmitResponse,
    TagListResponse,
    TeamCapacityResponse,
    TimeOffCreateRequest,
    TimeOffListResponse,
    TimeOffResponse,
    UserListItem,
    UserListResponse,
    WorkLogCreateRequest,
    WorkLogResponse,
)
from services import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    ValidationError,
    WIPLimitError,
    add_holiday,
    apply_tags,
    assign_case,
    bulk_register_cases,
    create_definition_snapshot,
    create_review_note,
    create_timeoff,
    create_worklog,
    delete_timeoff,
    get_admin_cases,
    get_all_tags,
    get_all_timeoffs,
    get_autoqc_summary,
    get_preqc_summary,
    get_case_detail,
    get_case_detail_with_metrics,
    get_cases_by_tag,
    get_cohort_summary,
    get_definition_snapshot_by_version,
    get_definition_snapshots,
    get_holidays,
    get_project_definition_links,
    get_project_definitions,
    get_qc_disagreement_stats,
    get_qc_disagreements,
    get_recent_events,
    get_team_capacity,
    get_user_timeoffs,
    get_worker_tasks,
    link_project_definition,
    process_event,
    remove_holiday,
    remove_tags,
    save_autoqc_summary,
    save_preqc_summary,
    submit_case,
    update_holidays,
)

router = APIRouter()


def get_current_user(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate user by API key."""
    user = db.query(User).filter(User.api_key == x_api_key, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require ADMIN role."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def handle_service_error(e: ServiceError):
    """Convert service errors to HTTP exceptions."""
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=e.message)
    elif isinstance(e, ValidationError):
        raise HTTPException(status_code=400, detail=e.message)
    elif isinstance(e, ForbiddenError):
        raise HTTPException(status_code=403, detail=e.message)
    elif isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=e.message)
    elif isinstance(e, WIPLimitError):
        raise HTTPException(status_code=429, detail=e.message)
    else:
        raise HTTPException(status_code=500, detail=e.message)


# Auth
@router.get("/api/auth/me", response_model=AuthMeResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    return AuthMeResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
    )


# Admin: Case Management
@router.post("/api/admin/cases/bulk_register", response_model=BulkRegisterResponse)
def bulk_register(
    request: BulkRegisterRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Register multiple cases at once."""
    try:
        return bulk_register_cases(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.post("/api/admin/assign", response_model=AssignResponse)
def assign(
    request: AssignRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Assign a case to a worker."""
    try:
        return assign_case(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.get("/api/admin/cases", response_model=CaseListResponse)
def list_cases(
    status: Optional[CaseStatus] = Query(None),
    project_id: Optional[int] = Query(None),
    assigned_user_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List cases with optional filters."""
    return get_admin_cases(db, status, project_id, assigned_user_id, limit, offset)


@router.get("/api/admin/cases/{case_id}", response_model=CaseDetailResponse)
def get_case(
    case_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get case detail."""
    try:
        return get_case_detail(db, case_id)
    except ServiceError as e:
        handle_service_error(e)


@router.get("/api/admin/cases/{case_id}/metrics", response_model=CaseDetailWithMetricsResponse)
def get_case_with_metrics(
    case_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get case detail with worklogs and computed metrics."""
    try:
        return get_case_detail_with_metrics(db, case_id)
    except ServiceError as e:
        handle_service_error(e)


@router.get("/api/admin/events", response_model=list[EventListItem])
def list_recent_events(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get recent events."""
    return get_recent_events(db, limit)


@router.get("/api/admin/users", response_model=UserListResponse)
def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all users."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return UserListResponse(
        users=[
            UserListItem(
                id=u.id,
                username=u.username,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at,
            )
            for u in users
        ]
    )


@router.post("/api/admin/review_notes", response_model=ReviewNoteResponse)
def add_review_note(
    request: ReviewNoteCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Add a review note to a case."""
    try:
        return create_review_note(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


# Worker: My Tasks
@router.get("/api/me/tasks", response_model=CaseListResponse)
def get_my_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get tasks assigned to current worker."""
    if current_user.role != UserRole.WORKER:
        raise HTTPException(status_code=403, detail="Only workers can access this endpoint")
    return get_worker_tasks(db, current_user)


# Events (authenticated)
@router.post("/api/events", response_model=EventResponse)
def create_event(
    request: EventCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an event (state transition)."""
    try:
        return process_event(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


# WorkLogs (authenticated)
@router.post("/api/worklogs", response_model=WorkLogResponse)
def add_worklog(
    request: WorkLogCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a worklog entry.
    Handles START/PAUSE/RESUME actions.
    For SUBMIT, use /api/submit instead.
    """
    try:
        return create_worklog(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


# Submit (atomic WorkLog SUBMIT + Event SUBMITTED)
@router.post("/api/submit", response_model=SubmitResponse)
def submit(
    request: SubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a case for review.
    Atomically creates WorkLog SUBMIT + Event SUBMITTED.
    Returns work time metrics.
    """
    try:
        return submit_case(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


# ============================================================
# TimeOff Endpoints
# ============================================================

@router.post("/api/timeoff", response_model=TimeOffResponse)
def create_timeoff_entry(
    request: TimeOffCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a time-off entry.
    Workers can only create for themselves.
    Admins can create for any user.
    """
    try:
        return create_timeoff(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.delete("/api/timeoff/{timeoff_id}")
def delete_timeoff_entry(
    timeoff_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a time-off entry.
    Workers can only delete their own.
    """
    try:
        delete_timeoff(db, timeoff_id, current_user)
        return {"message": "Time-off deleted"}
    except ServiceError as e:
        handle_service_error(e)


@router.get("/api/timeoff/me", response_model=TimeOffListResponse)
def get_my_timeoffs(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's time-offs."""
    return get_user_timeoffs(db, current_user.id, start_date, end_date)


@router.get("/api/admin/timeoff", response_model=TimeOffListResponse)
def list_all_timeoffs(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all time-offs (ADMIN only)."""
    return get_all_timeoffs(db, start_date, end_date)


@router.get("/api/admin/timeoff/{user_id}", response_model=TimeOffListResponse)
def get_user_timeoff_list(
    user_id: int,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a specific user's time-offs (ADMIN only)."""
    return get_user_timeoffs(db, user_id, start_date, end_date)


# ============================================================
# Holiday Endpoints
# ============================================================

@router.get("/api/holidays", response_model=HolidayListResponse)
def list_holidays(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the list of holidays."""
    return get_holidays(db)


@router.put("/api/admin/holidays", response_model=HolidayListResponse)
def set_holidays(
    request: HolidayUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update the full list of holidays (ADMIN only)."""
    try:
        return update_holidays(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.post("/api/admin/holidays/{holiday_date}", response_model=HolidayListResponse)
def add_single_holiday(
    holiday_date: date,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Add a single holiday (ADMIN only)."""
    try:
        return add_holiday(db, holiday_date, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.delete("/api/admin/holidays/{holiday_date}", response_model=HolidayListResponse)
def remove_single_holiday(
    holiday_date: date,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove a single holiday (ADMIN only)."""
    try:
        return remove_holiday(db, holiday_date, current_user)
    except ServiceError as e:
        handle_service_error(e)


# ============================================================
# Capacity Metrics Endpoints
# ============================================================

@router.get("/api/admin/capacity", response_model=TeamCapacityResponse)
def get_capacity_metrics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get team capacity metrics for a date range (ADMIN only).
    Includes workdays, available hours, actual hours, and utilization rate.
    """
    return get_team_capacity(db, start_date, end_date)


# ============================================================
# PreQC Summary Endpoints
# ============================================================

@router.post("/api/preqc_summary", response_model=PreQcSummaryResponse)
def save_preqc(
    request: PreQcSummaryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save Pre-QC summary from local client.
    NOTE: Server does NOT run Pre-QC. It only stores the summary.
    Actual QC runs on local PC (offline-first, cost=0).
    """
    try:
        return save_preqc_summary(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.get("/api/preqc_summary/{case_id}", response_model=PreQcSummaryResponse)
def get_preqc(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Pre-QC summary for a case."""
    result = get_preqc_summary(db, case_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"PreQC summary not found for case {case_id}")
    return result


# ============================================================
# AutoQC Summary Endpoints
# ============================================================

@router.post("/api/autoqc_summary", response_model=AutoQcSummaryResponse)
def save_autoqc(
    request: AutoQcSummaryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save Auto-QC summary from local client.
    NOTE: Server does NOT run Auto-QC. It only stores the summary.
    Actual QC runs on local PC (offline-first, cost=0).
    """
    try:
        return save_autoqc_summary(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.get("/api/autoqc_summary/{case_id}", response_model=AutoQcSummaryResponse)
def get_autoqc(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Auto-QC summary for a case."""
    result = get_autoqc_summary(db, case_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"AutoQC summary not found for case {case_id}")
    return result


# ============================================================
# QC Disagreement Endpoints
# ============================================================

@router.get("/api/admin/qc_disagreements", response_model=QcDisagreementListResponse)
def list_qc_disagreements(
    part_name: Optional[str] = Query(None),
    hospital: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get list of QC disagreements (ADMIN only).
    Supports filters by part, hospital, difficulty, and date range.
    """
    return get_qc_disagreements(db, part_name, hospital, difficulty, start_date, end_date)


@router.get("/api/admin/qc_disagreements/stats", response_model=QcDisagreementStats)
def get_qc_disagreement_statistics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get QC disagreement statistics (ADMIN only).
    Includes disagreement rate by part, hospital, and difficulty.
    """
    return get_qc_disagreement_stats(db, start_date, end_date)


# ============================================================
# Step 5: Cohort Tagging Endpoints
# ============================================================

@router.post("/api/admin/tags/apply", response_model=ApplyTagsResponse)
def apply_tag_to_cases(
    request: ApplyTagsRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Apply a tag to multiple cases by case_uid (ADMIN only).
    Used for cohort grouping in research.
    """
    try:
        return apply_tags(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.post("/api/admin/tags/remove", response_model=RemoveTagResponse)
def remove_tag_from_cases(
    request: RemoveTagRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Remove a tag from multiple cases (ADMIN only).
    """
    try:
        return remove_tags(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.get("/api/admin/tags", response_model=TagListResponse)
def list_all_tags(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get list of all unique tags (ADMIN only)."""
    return get_all_tags(db)


@router.get("/api/admin/tags/{tag_text}/cases", response_model=CasesByTagResponse)
def get_cases_with_tag(
    tag_text: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all cases with a specific tag (ADMIN only)."""
    return get_cases_by_tag(db, tag_text)


# ============================================================
# Step 5: Definition Snapshot Endpoints
# ============================================================

@router.post("/api/admin/definitions", response_model=DefinitionSnapshotResponse)
def create_definition(
    request: DefinitionSnapshotCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new definition snapshot (frozen version).
    Used for reproducibility in research papers.
    ADMIN only.
    """
    try:
        return create_definition_snapshot(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.get("/api/admin/definitions", response_model=DefinitionSnapshotListResponse)
def list_definitions(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all definition snapshots (ADMIN only)."""
    return get_definition_snapshots(db)


@router.get("/api/admin/definitions/{version_name}", response_model=DefinitionSnapshotResponse)
def get_definition(
    version_name: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a specific definition snapshot by version name (ADMIN only)."""
    result = get_definition_snapshot_by_version(db, version_name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Definition version '{version_name}' not found")
    return result


# ============================================================
# Step 5: Project-Definition Link Endpoints
# ============================================================

@router.post("/api/admin/projects/definition", response_model=ProjectDefinitionLinkResponse)
def link_definition_to_project(
    request: ProjectDefinitionLinkRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Link a project to a definition snapshot version (ADMIN only).
    Used to track which definition version applies to a project.
    """
    try:
        return link_project_definition(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.get("/api/admin/projects/definitions", response_model=ProjectDefinitionListResponse)
def list_project_definitions(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all project-definition links (ADMIN only)."""
    return get_project_definition_links(db)


@router.get("/api/admin/projects/{project_id}/definitions", response_model=ProjectDefinitionListResponse)
def get_project_definition_list(
    project_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get definition links for a specific project (ADMIN only)."""
    return get_project_definitions(db, project_id)


# ============================================================
# Step 5: Cohort Summary Endpoint
# ============================================================

@router.post("/api/admin/cohort/summary", response_model=CohortSummary)
def get_cohort_metrics(
    cohort_filter: CohortFilter,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get summary metrics for a cohort defined by filters (ADMIN only).
    Supports filtering by tag, project, definition_version, status, and date range.
    Metrics are computed on-the-fly.
    """
    return get_cohort_summary(db, cohort_filter)
