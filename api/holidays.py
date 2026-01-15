"""
Holidays API Router.
Work calendar and holiday management.
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import HolidayListResponse, HolidayUpdateRequest
from services import (
    ServiceError,
    add_holiday,
    get_holidays,
    remove_holiday,
    update_holidays,
)
from .deps import get_current_user, require_admin, handle_service_error

router = APIRouter()


@router.get(
    "/api/holidays",
    response_model=HolidayListResponse,
    tags=["Holidays"],
    summary="공휴일 목록 조회",
    description="등록된 공휴일 목록을 조회합니다. 인증된 사용자 접근 가능.",
)
def list_holidays(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the list of holidays."""
    return get_holidays(db)


@router.put(
    "/api/admin/holidays",
    response_model=HolidayListResponse,
    tags=["Admin - Holidays"],
    summary="공휴일 목록 전체 업데이트",
    description="공휴일 목록을 전체 교체합니다. 기존 공휴일은 삭제되고 새 목록으로 대체됩니다. ADMIN 권한 필요.",
)
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


@router.post(
    "/api/admin/holidays/{holiday_date}",
    response_model=HolidayListResponse,
    tags=["Admin - Holidays"],
    summary="공휴일 추가",
    description="단일 공휴일을 추가합니다. ADMIN 권한 필요.",
)
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


@router.delete(
    "/api/admin/holidays/{holiday_date}",
    response_model=HolidayListResponse,
    tags=["Admin - Holidays"],
    summary="공휴일 삭제",
    description="단일 공휴일을 삭제합니다. ADMIN 권한 필요.",
)
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
