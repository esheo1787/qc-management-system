"""
Capacity API Router.
Team capacity metrics.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import TeamCapacityResponse
from services import get_team_capacity
from .deps import require_admin

router = APIRouter()


@router.get(
    "/api/admin/capacity",
    response_model=TeamCapacityResponse,
    tags=["Admin - Capacity"],
    summary="팀 용량 메트릭스 조회",
    description="지정된 기간의 팀 용량 메트릭스를 조회합니다. 근무일, 가용 시간, 실제 작업 시간, 가동률 포함. ADMIN 권한 필요.",
)
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
