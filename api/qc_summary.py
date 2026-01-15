"""
QC Summary API Router.
Pre-QC and Auto-QC summary storage.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    AutoQcSummaryCreateRequest,
    AutoQcSummaryResponse,
    PreQcSummaryCreateRequest,
    PreQcSummaryResponse,
)
from services import (
    ServiceError,
    get_autoqc_summary,
    get_preqc_summary,
    save_autoqc_summary,
    save_preqc_summary,
)
from .deps import get_current_user, handle_service_error

router = APIRouter()


# PreQC Summary Endpoints
@router.post(
    "/api/preqc_summary",
    response_model=PreQcSummaryResponse,
    tags=["PreQC Summary"],
    summary="Pre-QC 요약 저장",
    description="로컬 클라이언트에서 실행된 Pre-QC 결과 요약을 저장합니다. 서버는 QC를 실행하지 않고 요약만 저장합니다 (offline-first, cost=0).",
)
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


@router.get(
    "/api/preqc_summary/{case_id}",
    response_model=PreQcSummaryResponse,
    tags=["PreQC Summary"],
    summary="Pre-QC 요약 조회",
    description="특정 케이스의 Pre-QC 요약을 조회합니다. 슬라이스 두께, 노이즈 레벨, 조영제 상태, 혈관 가시성 등 포함.",
)
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


# AutoQC Summary Endpoints
@router.post(
    "/api/autoqc_summary",
    response_model=AutoQcSummaryResponse,
    tags=["AutoQC Summary"],
    summary="Auto-QC 요약 저장",
    description="로컬 클라이언트에서 실행된 Auto-QC 결과 요약을 저장합니다. 서버는 QC를 실행하지 않고 요약만 저장합니다 (offline-first, cost=0).",
)
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


@router.get(
    "/api/autoqc_summary/{case_id}",
    response_model=AutoQcSummaryResponse,
    tags=["AutoQC Summary"],
    summary="Auto-QC 요약 조회",
    description="특정 케이스의 Auto-QC 요약을 조회합니다. 상태(PASS/WARN/INCOMPLETE), 누락 세그먼트, 이름 불일치, 이슈 목록 포함.",
)
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
