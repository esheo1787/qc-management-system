"""
QC Disagreements API Router.
Auto-QC vs actual review disagreement analysis.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import QcDisagreementListResponse, QcDisagreementStats
from services import get_qc_disagreement_stats, get_qc_disagreements
from .deps import require_admin

router = APIRouter()


@router.get(
    "/api/admin/qc_disagreements",
    response_model=QcDisagreementListResponse,
    tags=["Admin - QC Disagreements"],
    summary="QC 불일치 목록 조회",
    description="Auto-QC 결과와 실제 검수 결과가 불일치하는 케이스 목록을 조회합니다. 부위, 병원, 난이도, 날짜 범위 필터 지원. ADMIN 권한 필요.",
)
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


@router.get(
    "/api/admin/qc_disagreements/stats",
    response_model=QcDisagreementStats,
    tags=["Admin - QC Disagreements"],
    summary="QC 불일치 통계 조회",
    description="QC 불일치 통계를 조회합니다. 불일치율, False Positive/Negative 수, 부위/병원/난이도별 통계 포함. ADMIN 권한 필요.",
)
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
