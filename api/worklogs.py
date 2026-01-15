"""
WorkLogs API Router.
Work time tracking.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import WorkLogCreateRequest, WorkLogResponse
from services import ServiceError, create_worklog
from .deps import get_current_user, handle_service_error

router = APIRouter()


@router.post(
    "/api/worklogs",
    response_model=WorkLogResponse,
    tags=["WorkLogs"],
    summary="작업 로그 기록",
    description="작업 시작(START), 일시중지(PAUSE), 재개(RESUME) 로그를 기록합니다. 제출은 /api/submit을 사용하세요.",
)
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
