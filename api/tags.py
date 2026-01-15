"""
Tags API Router.
Cohort tagging for cases.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    ApplyTagsRequest,
    ApplyTagsResponse,
    CasesByTagResponse,
    RemoveTagRequest,
    RemoveTagResponse,
    TagListResponse,
)
from services import (
    ServiceError,
    apply_tags,
    get_all_tags,
    get_cases_by_tag,
    remove_tags,
)
from .deps import require_admin, handle_service_error

router = APIRouter()


@router.post(
    "/api/admin/tags/apply",
    response_model=ApplyTagsResponse,
    tags=["Admin - Tags"],
    summary="태그 일괄 적용",
    description="여러 케이스에 태그를 일괄 적용합니다. case_uid 목록으로 대상 지정. 연구 코호트 그룹핑용. ADMIN 권한 필요.",
)
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


@router.post(
    "/api/admin/tags/remove",
    response_model=RemoveTagResponse,
    tags=["Admin - Tags"],
    summary="태그 일괄 제거",
    description="여러 케이스에서 태그를 일괄 제거합니다. ADMIN 권한 필요.",
)
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


@router.get(
    "/api/admin/tags",
    response_model=TagListResponse,
    tags=["Admin - Tags"],
    summary="전체 태그 목록 조회",
    description="등록된 모든 고유 태그 목록을 조회합니다. ADMIN 권한 필요.",
)
def list_all_tags(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get list of all unique tags (ADMIN only)."""
    return get_all_tags(db)


@router.get(
    "/api/admin/tags/{tag_text}/cases",
    response_model=CasesByTagResponse,
    tags=["Admin - Tags"],
    summary="태그별 케이스 목록 조회",
    description="특정 태그가 적용된 모든 케이스 목록을 조회합니다. ADMIN 권한 필요.",
)
def get_cases_with_tag(
    tag_text: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all cases with a specific tag (ADMIN only)."""
    return get_cases_by_tag(db, tag_text)
