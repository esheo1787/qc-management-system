"""
API Dependencies and shared utilities.
Authentication, authorization, error handling.
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole
from services import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ForbiddenError,
    ConflictError,
    WIPLimitError,
)

# =============================================================================
# API Tags Definition for OpenAPI/Swagger Documentation
# =============================================================================
TAGS_METADATA = [
    {
        "name": "Health",
        "description": "서비스 상태 확인 API. 헬스 체크 및 서비스 정상 동작 여부 확인. 인증 불필요.",
    },
    {
        "name": "Auth",
        "description": "인증 관련 API. API Key를 통한 사용자 인증 및 현재 사용자 정보 조회.",
    },
    {
        "name": "Admin - Case Management",
        "description": "관리자 전용 케이스 관리 API. 케이스 등록, 할당, 조회, 상세 정보 확인.",
    },
    {
        "name": "Admin - Users",
        "description": "관리자 전용 사용자 관리 API. 사용자 목록 조회.",
    },
    {
        "name": "Admin - Events",
        "description": "관리자 전용 이벤트 조회 API. 최근 이벤트 히스토리 확인.",
    },
    {
        "name": "Admin - Review Notes",
        "description": "관리자 전용 검수 노트 API. 케이스에 검수 메모 추가.",
    },
    {
        "name": "Admin - TimeOff",
        "description": "관리자 전용 휴가 관리 API. 전체 휴가 조회 및 특정 사용자 휴가 조회.",
    },
    {
        "name": "Admin - Holidays",
        "description": "관리자 전용 공휴일 관리 API. 공휴일 추가, 삭제, 전체 업데이트.",
    },
    {
        "name": "Admin - Capacity",
        "description": "관리자 전용 팀 용량 분석 API. 팀원별 가용 시간, 실제 작업 시간, 가동률 조회.",
    },
    {
        "name": "Admin - QC Disagreements",
        "description": "관리자 전용 QC 불일치 분석 API. Auto-QC 결과와 실제 검수 결과의 불일치 분석.",
    },
    {
        "name": "Admin - Tags",
        "description": "관리자 전용 태그 관리 API. 코호트 그룹핑을 위한 케이스 태깅.",
    },
    {
        "name": "Admin - Definitions",
        "description": "관리자 전용 정의 스냅샷 API. 연구 재현성을 위한 정의 버전 관리.",
    },
    {
        "name": "Admin - Projects",
        "description": "관리자 전용 프로젝트-정의 연결 API. 프로젝트별 정의 버전 매핑.",
    },
    {
        "name": "Admin - Cohort",
        "description": "관리자 전용 코호트 분석 API. 필터 기반 코호트 메트릭스 조회.",
    },
    {
        "name": "Worker - Tasks",
        "description": "작업자 전용 태스크 API. 본인에게 할당된 케이스 목록 조회.",
    },
    {
        "name": "Events",
        "description": "이벤트 생성 API. 케이스 상태 전이를 위한 이벤트 기록.",
    },
    {
        "name": "WorkLogs",
        "description": "작업 로그 API. 작업 시작/일시중지/재개 기록.",
    },
    {
        "name": "Submit",
        "description": "케이스 제출 API. WorkLog SUBMIT과 Event SUBMITTED를 원자적으로 생성.",
    },
    {
        "name": "TimeOff",
        "description": "휴가 관리 API. 본인 휴가 등록, 조회, 삭제.",
    },
    {
        "name": "Holidays",
        "description": "공휴일 조회 API. 등록된 공휴일 목록 확인.",
    },
    {
        "name": "PreQC Summary",
        "description": "Pre-QC 요약 API. 로컬 클라이언트에서 실행된 Pre-QC 결과 저장 및 조회.",
    },
    {
        "name": "AutoQC Summary",
        "description": "Auto-QC 요약 API. 로컬 클라이언트에서 실행된 Auto-QC 결과 저장 및 조회.",
    },
]


def get_current_user(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate user by API key."""
    user = db.query(User).filter(User.api_key == x_api_key, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require ADMIN role."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def handle_service_error(e: ServiceError):
    """Convert service errors to HTTP exceptions."""
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=e.message)
    elif isinstance(e, ValidationError):
        raise HTTPException(status_code=400, detail=e.message)
    elif isinstance(e, ForbiddenError):
        raise HTTPException(status_code=403, detail=e.message)
    elif isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=e.message)
    elif isinstance(e, WIPLimitError):
        raise HTTPException(status_code=429, detail=e.message)
    else:
        raise HTTPException(status_code=500, detail=e.message)
