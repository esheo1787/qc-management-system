"""
Cohort API Router.
Cohort analysis and metrics.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import CohortFilter, CohortSummary
from services import get_cohort_summary
from .deps import require_admin

router = APIRouter()


@router.post(
    "/api/admin/cohort/summary",
    response_model=CohortSummary,
    tags=["Admin - Cohort"],
    summary="코호트 요약 메트릭스 조회",
    description="필터 조건에 맞는 코호트의 요약 메트릭스를 조회합니다. 태그, 프로젝트, 정의 버전, 상태, 날짜 범위로 필터링 가능. 메트릭스는 실시간 계산됩니다. ADMIN 권한 필요.",
)
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
