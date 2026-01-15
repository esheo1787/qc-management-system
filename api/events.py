"""
Events API Router.
Event creation and listing.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    EventCreateRequest,
    EventListItem,
    EventResponse,
    SubmitRequest,
    SubmitResponse,
)
from services import (
    ServiceError,
    get_recent_events,
    process_event,
    submit_case,
)
from .deps import get_current_user, require_admin, handle_service_error

router = APIRouter()


@router.get(
    "/api/admin/events",
    response_model=list[EventListItem],
    tags=["Admin - Events"],
    summary="최근 이벤트 목록 조회",
    description="최근 발생한 이벤트 목록을 조회합니다. 케이스 상태 변경 히스토리 추적용. ADMIN 권한 필요.",
)
def list_recent_events(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get recent events."""
    return get_recent_events(db, limit)


@router.post(
    "/api/events",
    response_model=EventResponse,
    tags=["Events"],
    summary="이벤트 생성 (상태 전이)",
    description="케이스 상태 전이를 위한 이벤트를 생성합니다. idempotency_key로 중복 요청 방지. expected_revision으로 낙관적 락 지원.",
)
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


@router.post(
    "/api/submit",
    response_model=SubmitResponse,
    tags=["Submit"],
    summary="케이스 제출",
    description="케이스를 검수 요청 상태로 제출합니다. WorkLog SUBMIT과 Event SUBMITTED를 원자적으로 생성. 작업 시간 메트릭스(work_seconds, man_days) 반환.",
)
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
