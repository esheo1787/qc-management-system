"""
Definitions API Router.
Definition snapshots for research reproducibility.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    DefinitionSnapshotCreateRequest,
    DefinitionSnapshotListResponse,
    DefinitionSnapshotResponse,
)
from services import (
    ServiceError,
    create_definition_snapshot,
    get_definition_snapshot_by_version,
    get_definition_snapshots,
)
from .deps import require_admin, handle_service_error

router = APIRouter()


@router.post(
    "/api/admin/definitions",
    response_model=DefinitionSnapshotResponse,
    tags=["Admin - Definitions"],
    summary="정의 스냅샷 생성",
    description="새로운 정의 스냅샷(고정 버전)을 생성합니다. 연구 논문의 재현성을 위해 사용. ADMIN 권한 필요.",
)
def create_definition(
    request: DefinitionSnapshotCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new definition snapshot (frozen version).
    Used for reproducibility in research papers.
    ADMIN only.
    """
    try:
        return create_definition_snapshot(db, request, current_user)
    except ServiceError as e:
        handle_service_error(e)


@router.get(
    "/api/admin/definitions",
    response_model=DefinitionSnapshotListResponse,
    tags=["Admin - Definitions"],
    summary="정의 스냅샷 목록 조회",
    description="등록된 모든 정의 스냅샷 목록을 조회합니다. ADMIN 권한 필요.",
)
def list_definitions(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all definition snapshots (ADMIN only)."""
    return get_definition_snapshots(db)


@router.get(
    "/api/admin/definitions/{version_name}",
    response_model=DefinitionSnapshotResponse,
    tags=["Admin - Definitions"],
    summary="정의 스냅샷 상세 조회",
    description="특정 버전명의 정의 스냅샷을 조회합니다. ADMIN 권한 필요.",
)
def get_definition(
    version_name: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a specific definition snapshot by version name (ADMIN only)."""
    result = get_definition_snapshot_by_version(db, version_name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Definition version '{version_name}' not found")
    return result
