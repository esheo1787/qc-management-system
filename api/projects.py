"""
Projects API Router.
Project-definition linking.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    ProjectDefinitionLinkRequest,
    ProjectDefinitionLinkResponse,
    ProjectDefinitionListResponse,
)
from services import (
    ServiceError,
    get_project_definition_links,
    get_project_definitions,
    link_project_definition,
)
from .deps import require_admin, handle_service_error

router = APIRouter()


@router.post(
    "/api/admin/projects/definition",
    response_model=ProjectDefinitionLinkResponse,
    tags=["Admin - Projects"],
    summary="프로젝트-정의 연결",
    description="프로젝트를 정의 스냅샷 버전에 연결합니다. 프로젝트별 적용 정의 버전 추적용. ADMIN 권한 필요.",
)
def link_definition_to_project(
    request: ProjectDefinitionLinkRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Link a project to a definition snapshot version (ADMIN only).
    Used to track which definition version applies to a project.
    """
    try:
        return link_project_definition(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.get(
    "/api/admin/projects/definitions",
    response_model=ProjectDefinitionListResponse,
    tags=["Admin - Projects"],
    summary="전체 프로젝트-정의 연결 목록 조회",
    description="모든 프로젝트-정의 스냅샷 연결 목록을 조회합니다. ADMIN 권한 필요.",
)
def list_project_definitions(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all project-definition links (ADMIN only)."""
    return get_project_definition_links(db)


@router.get(
    "/api/admin/projects/{project_id}/definitions",
    response_model=ProjectDefinitionListResponse,
    tags=["Admin - Projects"],
    summary="특정 프로젝트의 정의 연결 목록 조회",
    description="특정 프로젝트에 연결된 정의 스냅샷 목록을 조회합니다. ADMIN 권한 필요.",
)
def get_project_definition_list(
    project_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get definition links for a specific project (ADMIN only)."""
    return get_project_definitions(db, project_id)
