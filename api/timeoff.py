"""
TimeOff API Router.
User time-off management.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    TimeOffCreateRequest,
    TimeOffListResponse,
    TimeOffResponse,
)
from services import (
    ServiceError,
    create_timeoff,
    delete_timeoff,
    get_all_timeoffs,
    get_user_timeoffs,
)
from .deps import get_current_user, require_admin, handle_service_error

router = APIRouter()


@router.post(
    "/api/timeoff",
    response_model=TimeOffResponse,
    tags=["TimeOff"],
    summary="휴가 등록",
    description="휴가를 등록합니다. 작업자는 본인 휴가만, 관리자는 모든 사용자 휴가 등록 가능. VACATION(연차), HALF_DAY(반차) 유형 지원.",
)
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


@router.delete(
    "/api/timeoff/{timeoff_id}",
    tags=["TimeOff"],
    summary="휴가 삭제",
    description="휴가 항목을 삭제합니다. 작업자는 본인 휴가만 삭제 가능.",
)
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


@router.get(
    "/api/timeoff/me",
    response_model=TimeOffListResponse,
    tags=["TimeOff"],
    summary="내 휴가 목록 조회",
    description="현재 로그인한 사용자의 휴가 목록을 조회합니다. 날짜 범위로 필터링 가능.",
)
def get_my_timeoffs(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's time-offs."""
    return get_user_timeoffs(db, current_user.id, start_date, end_date)


@router.get(
    "/api/admin/timeoff",
    response_model=TimeOffListResponse,
    tags=["Admin - TimeOff"],
    summary="전체 휴가 목록 조회",
    description="모든 사용자의 휴가 목록을 조회합니다. 날짜 범위로 필터링 가능. ADMIN 권한 필요.",
)
def list_all_timeoffs(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all time-offs (ADMIN only)."""
    return get_all_timeoffs(db, start_date, end_date)


@router.get(
    "/api/admin/timeoff/{user_id}",
    response_model=TimeOffListResponse,
    tags=["Admin - TimeOff"],
    summary="특정 사용자 휴가 목록 조회",
    description="특정 사용자의 휴가 목록을 조회합니다. 날짜 범위로 필터링 가능. ADMIN 권한 필요.",
)
def get_user_timeoff_list(
    user_id: int,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a specific user's time-offs (ADMIN only)."""
    return get_user_timeoffs(db, user_id, start_date, end_date)
