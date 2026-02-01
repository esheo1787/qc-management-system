"""
Auth API Router.
"""
from fastapi import APIRouter, Depends 

from models import User
from schemas import AuthMeResponse
from .deps import get_current_user

router = APIRouter()


@router.get(
    "/api/auth/me",
    response_model=AuthMeResponse,
    tags=["Auth"],
    summary="현재 사용자 정보 조회",
    description="X-API-Key 헤더로 인증된 현재 사용자의 정보를 반환합니다.",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    return AuthMeResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
    )
