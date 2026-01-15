"""
Case Management API Router.
Admin case management + Worker tasks.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import CaseStatus, User, UserRole
from schemas import (
    AssignRequest,
    AssignResponse,
    BulkRegisterRequest,
    BulkRegisterResponse,
    CaseDetailResponse,
    CaseDetailWithMetricsResponse,
    CaseListResponse,
    ReviewNoteCreateRequest,
    ReviewNoteResponse,
    UserListItem,
    UserListResponse,
)
from services import (
    ServiceError,
    assign_case,
    bulk_register_cases,
    create_review_note,
    get_admin_cases,
    get_case_detail,
    get_case_detail_with_metrics,
    get_worker_tasks,
)
from .deps import get_current_user, require_admin, handle_service_error

router = APIRouter()


# Admin: Case Management
@router.post(
    "/api/admin/cases/bulk_register",
    response_model=BulkRegisterResponse,
    tags=["Admin - Case Management"],
    summary="케이스 일괄 등록",
    description="여러 케이스를 한 번에 등록합니다. 중복된 case_uid는 건너뜁니다. ADMIN 권한 필요.",
)
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


@router.post(
    "/api/admin/assign",
    response_model=AssignResponse,
    tags=["Admin - Case Management"],
    summary="케이스 작업자 할당",
    description="특정 케이스를 작업자에게 할당합니다. ADMIN 권한 필요.",
)
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


@router.get(
    "/api/admin/cases",
    response_model=CaseListResponse,
    tags=["Admin - Case Management"],
    summary="케이스 목록 조회",
    description="필터 조건에 맞는 케이스 목록을 조회합니다. status, project_id, assigned_user_id로 필터링 가능. ADMIN 권한 필요.",
)
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


@router.get(
    "/api/admin/cases/{case_id}",
    response_model=CaseDetailResponse,
    tags=["Admin - Case Management"],
    summary="케이스 상세 조회",
    description="특정 케이스의 상세 정보를 조회합니다. PreQC 요약, 이벤트 히스토리, 검수 노트 포함. ADMIN 권한 필요.",
)
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


@router.get(
    "/api/admin/cases/{case_id}/metrics",
    response_model=CaseDetailWithMetricsResponse,
    tags=["Admin - Case Management"],
    summary="케이스 상세 + 메트릭스 조회",
    description="케이스 상세 정보와 함께 작업 로그, 작업 시간 메트릭스를 조회합니다. work_seconds, man_days, timeline 포함. ADMIN 권한 필요.",
)
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


@router.get(
    "/api/admin/users",
    response_model=UserListResponse,
    tags=["Admin - Users"],
    summary="사용자 목록 조회",
    description="등록된 모든 사용자 목록을 조회합니다. ADMIN 권한 필요.",
)
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


@router.post(
    "/api/admin/review_notes",
    response_model=ReviewNoteResponse,
    tags=["Admin - Review Notes"],
    summary="검수 노트 추가",
    description="케이스에 검수 노트를 추가합니다. QC 요약 확인 여부, 추가 태그 포함 가능. ADMIN 권한 필요.",
)
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
@router.get(
    "/api/me/tasks",
    response_model=CaseListResponse,
    tags=["Worker - Tasks"],
    summary="내 할당 작업 목록 조회",
    description="현재 로그인한 작업자에게 할당된 케이스 목록을 조회합니다. WORKER 권한만 접근 가능.",
)
def get_my_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get tasks assigned to current worker."""
    if current_user.role != UserRole.WORKER:
        raise HTTPException(status_code=403, detail="Only workers can access this endpoint")
    return get_worker_tasks(db, current_user)
