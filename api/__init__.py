"""
API Router Package.
Domain-separated routers for better organization.
"""
from fastapi import APIRouter

from .deps import get_current_user, require_admin, handle_service_error, TAGS_METADATA
from .auth import router as auth_router
from .cases import router as cases_router
from .events import router as events_router
from .worklogs import router as worklogs_router
from .timeoff import router as timeoff_router
from .holidays import router as holidays_router
from .capacity import router as capacity_router
from .qc_summary import router as qc_summary_router
from .qc_disagreements import router as qc_disagreements_router
from .tags import router as tags_router
from .definitions import router as definitions_router
from .projects import router as projects_router
from .cohort import router as cohort_router

# Main router that includes all sub-routers
router = APIRouter()

router.include_router(auth_router)
router.include_router(cases_router)
router.include_router(events_router)
router.include_router(worklogs_router)
router.include_router(timeoff_router)
router.include_router(holidays_router)
router.include_router(capacity_router)
router.include_router(qc_summary_router)
router.include_router(qc_disagreements_router)
router.include_router(tags_router)
router.include_router(definitions_router)
router.include_router(projects_router)
router.include_router(cohort_router)

__all__ = [
    "router",
    "TAGS_METADATA",
    "get_current_user",
    "require_admin",
    "handle_service_error",
]
