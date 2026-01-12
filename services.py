"""
Business logic services.
All state changes go through Event-based transitions.
WorkLog handles time tracking separately.
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from config import TIMEZONE

from models import (
    ActionType,
    AppConfig,
    AutoQcSummary,
    Case,
    CaseStatus,
    CaseTag,
    DefinitionSnapshot,
    Event,
    EventType,
    Part,
    PreQcSummary,
    Project,
    ProjectDefinitionLink,
    ReviewNote,
    TimeOffType,
    User,
    UserRole,
    UserTimeOff,
    WorkCalendar,
    WorkLog,
    now_kst,
)
from schemas import (
    ApplyTagsRequest,
    ApplyTagsResponse,
    AssignRequest,
    AssignResponse,
    AutoQcSummaryCreateRequest,
    AutoQcSummaryResponse,
    BulkRegisterRequest,
    BulkRegisterResponse,
    CapacityMetrics,
    CaseDetailResponse,
    CaseDetailWithMetricsResponse,
    CaseListItem,
    CaseListResponse,
    CaseMetrics,
    CasesByTagResponse,
    CohortFilter,
    CohortSummary,
    DefinitionSnapshotCreateRequest,
    DefinitionSnapshotListResponse,
    DefinitionSnapshotResponse,
    EventCreateRequest,
    EventListItem,
    EventResponse,
    HolidayListResponse,
    HolidayUpdateRequest,
    PreQcSummaryResponse,
    ProjectDefinitionLinkRequest,
    ProjectDefinitionLinkResponse,
    ProjectDefinitionListResponse,
    QcDisagreementItem,
    QcDisagreementListResponse,
    QcDisagreementStats,
    RemoveTagRequest,
    RemoveTagResponse,
    ReviewNoteCreateRequest,
    ReviewNoteItem,
    ReviewNoteResponse,
    SubmitRequest,
    SubmitResponse,
    TagListResponse,
    TeamCapacityResponse,
    TimeOffCreateRequest,
    TimeOffListResponse,
    TimeOffResponse,
    WorkLogCreateRequest,
    WorkLogItem,
    WorkLogResponse,
)
from metrics import (
    compute_capacity_metrics,
    compute_man_days,
    compute_timeline,
    compute_work_seconds,
    format_duration,
    get_timeline_dates,
)


class ServiceError(Exception):
    """Base service error."""

    def __init__(self, message: str, code: str = "SERVICE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ConflictError(ServiceError):
    """Optimistic lock conflict."""

    def __init__(self, message: str = "Conflict: resource was modified"):
        super().__init__(message, "CONFLICT")


class ValidationError(ServiceError):
    """Validation error."""

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class NotFoundError(ServiceError):
    """Resource not found."""

    def __init__(self, message: str):
        super().__init__(message, "NOT_FOUND")


class ForbiddenError(ServiceError):
    """Permission denied."""

    def __init__(self, message: str):
        super().__init__(message, "FORBIDDEN")


class WIPLimitError(ServiceError):
    """WIP limit exceeded."""

    def __init__(self, message: str):
        super().__init__(message, "WIP_LIMIT_EXCEEDED")


# State transition rules
VALID_TRANSITIONS: dict[tuple[CaseStatus, EventType], CaseStatus] = {
    (CaseStatus.TODO, EventType.STARTED): CaseStatus.IN_PROGRESS,
    (CaseStatus.REWORK, EventType.STARTED): CaseStatus.IN_PROGRESS,
    (CaseStatus.IN_PROGRESS, EventType.SUBMITTED): CaseStatus.SUBMITTED,
    (CaseStatus.SUBMITTED, EventType.REWORK_REQUESTED): CaseStatus.REWORK,
    (CaseStatus.SUBMITTED, EventType.ACCEPTED): CaseStatus.ACCEPTED,
}

# Default config values
DEFAULT_CONFIG = {
    "workday_hours": 8,
    "wip_limit": 1,
    "auto_timeout_minutes": 120,
    "difficulty_weights": {"LOW": 1.0, "MID": 1.5, "HIGH": 2.0},
}


def get_config(db: Session, key: str) -> any:
    """Get config value from AppConfig table."""
    config = db.query(AppConfig).filter(AppConfig.key == key).first()
    if config:
        return json.loads(config.value_json)
    return DEFAULT_CONFIG.get(key)


def get_or_create_project(db: Session, name: str) -> Project:
    """Get or create a project by name."""
    project = db.query(Project).filter(Project.name == name).first()
    if not project:
        project = Project(name=name, is_active=True)
        db.add(project)
        db.flush()
    return project


def get_or_create_part(db: Session, name: str) -> Part:
    """Get or create a part by name."""
    part = db.query(Part).filter(Part.name == name).first()
    if not part:
        part = Part(name=name, is_active=True)
        db.add(part)
        db.flush()
    return part


def get_user_wip_count(db: Session, user_id: int, exclude_paused: bool = True) -> int:
    """
    Count user's IN_PROGRESS cases.

    Args:
        db: Database session
        user_id: User ID
        exclude_paused: If True, exclude cases where last worklog is PAUSE

    Returns:
        Count of active WIP cases
    """
    cases = db.query(Case).filter(
        Case.assigned_user_id == user_id,
        Case.status == CaseStatus.IN_PROGRESS,
    ).all()

    if not exclude_paused:
        return len(cases)

    # Filter out paused cases
    active_count = 0
    for case in cases:
        last_log = (
            db.query(WorkLog)
            .filter(WorkLog.case_id == case.id)
            .order_by(WorkLog.timestamp.desc())
            .first()
        )
        # Count only if actively working (not paused)
        if last_log and last_log.action_type in (ActionType.START, ActionType.RESUME, ActionType.REWORK_START):
            active_count += 1

    return active_count


def check_wip_limit(db: Session, user_id: int) -> None:
    """Check if user can start a new case (WIP limit)."""
    wip_limit = get_config(db, "wip_limit")
    current_wip = get_user_wip_count(db, user_id)
    if current_wip >= wip_limit:
        raise WIPLimitError(
            f"WIP limit exceeded: you have {current_wip} case(s) in progress (limit: {wip_limit})"
        )


def get_last_worklog_action(db: Session, case_id: int) -> Optional[ActionType]:
    """Get the last worklog action for a case."""
    last_log = (
        db.query(WorkLog)
        .filter(WorkLog.case_id == case_id)
        .order_by(WorkLog.timestamp.desc())
        .first()
    )
    return last_log.action_type if last_log else None


def validate_worklog_sequence(
    last_action: Optional[ActionType],
    new_action: ActionType,
    case_status: CaseStatus,
) -> None:
    """Validate worklog action sequence."""
    if new_action == ActionType.START:
        if case_status not in (CaseStatus.TODO, CaseStatus.REWORK):
            raise ValidationError(f"Cannot START: case status is {case_status.value}")
        if last_action is not None and last_action not in (ActionType.SUBMIT,):
            raise ValidationError(f"Cannot START: last action was {last_action.value}")

    elif new_action == ActionType.REWORK_START:
        if case_status != CaseStatus.REWORK:
            raise ValidationError("REWORK_START only allowed for REWORK status")
        if last_action not in (None, ActionType.SUBMIT):
            raise ValidationError(f"Cannot REWORK_START: last action was {last_action.value}")

    elif new_action == ActionType.PAUSE:
        if last_action not in (ActionType.START, ActionType.RESUME, ActionType.REWORK_START):
            raise ValidationError(f"Cannot PAUSE: not in active session (last: {last_action})")

    elif new_action == ActionType.RESUME:
        if last_action != ActionType.PAUSE:
            raise ValidationError(f"Cannot RESUME: not paused (last: {last_action})")

    elif new_action == ActionType.SUBMIT:
        if case_status != CaseStatus.IN_PROGRESS:
            raise ValidationError(f"Cannot SUBMIT: case status is {case_status.value}")
        if last_action not in (ActionType.START, ActionType.RESUME, ActionType.REWORK_START, ActionType.PAUSE):
            raise ValidationError(f"Cannot SUBMIT: invalid sequence (last: {last_action})")


def bulk_register_cases(
    db: Session, request: BulkRegisterRequest, current_user: User
) -> BulkRegisterResponse:
    """
    Register multiple cases at once (ADMIN only).
    Skips cases with duplicate case_uid.
    """
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can register cases")

    created_uids: list[str] = []
    skipped_uids: list[str] = []

    with db.begin():
        for item in request.cases:
            existing = db.query(Case).filter(Case.case_uid == item.case_uid).first()
            if existing:
                skipped_uids.append(item.case_uid)
                continue

            project = get_or_create_project(db, item.project_name)
            part = get_or_create_part(db, item.part_name)

            case = Case(
                case_uid=item.case_uid,
                display_name=item.display_name,
                nas_path=item.nas_path,
                hospital=item.hospital,
                slice_thickness_mm=item.slice_thickness_mm,
                project_id=project.id,
                part_id=part.id,
                difficulty=item.difficulty,
                status=CaseStatus.TODO,
                revision=1,
                metadata_json=item.metadata_json,
            )
            db.add(case)
            db.flush()

            if item.preqc:
                preqc = PreQcSummary(
                    case_id=case.id,
                    flags_json=item.preqc.flags_json,
                    slice_count=item.preqc.slice_count,
                    expected_segments_json=item.preqc.expected_segments_json,
                )
                db.add(preqc)

            created_uids.append(item.case_uid)

    return BulkRegisterResponse(
        created_count=len(created_uids),
        skipped_count=len(skipped_uids),
        created_case_uids=created_uids,
        skipped_case_uids=skipped_uids,
    )


def assign_case(
    db: Session, request: AssignRequest, current_user: User
) -> AssignResponse:
    """Assign a case to a worker (ADMIN only)."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can assign cases")

    with db.begin():
        case = db.query(Case).filter(Case.id == request.case_id).first()
        if not case:
            raise NotFoundError(f"Case {request.case_id} not found")

        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise NotFoundError(f"User {request.user_id} not found")

        if user.role != UserRole.WORKER:
            raise ValidationError("Can only assign to WORKER role users")

        if not user.is_active:
            raise ValidationError("Cannot assign to inactive user")

        case.assigned_user_id = user.id
        db.flush()

    return AssignResponse(
        case_id=case.id,
        case_uid=case.case_uid,
        assigned_user_id=user.id,
        assigned_username=user.username,
    )


def process_event(
    db: Session, request: EventCreateRequest, current_user: User
) -> EventResponse:
    """
    Process an event and transition case status.
    Uses idempotency key and optimistic locking.
    Note: For STARTED/SUBMITTED, prefer using WorkLog-based functions.
    """
    with db.begin():
        existing_event = (
            db.query(Event)
            .filter(Event.idempotency_key == request.idempotency_key)
            .first()
        )
        if existing_event:
            case = db.query(Case).filter(Case.id == existing_event.case_id).first()
            return EventResponse(
                id=existing_event.id,
                case_id=existing_event.case_id,
                user_id=existing_event.user_id,
                event_type=existing_event.event_type,
                idempotency_key=existing_event.idempotency_key,
                event_code=existing_event.event_code,
                payload_json=existing_event.payload_json,
                created_at=existing_event.created_at,
                case_status=case.status,
                case_revision=case.revision,
            )

        case = db.query(Case).filter(Case.id == request.case_id).first()
        if not case:
            raise NotFoundError(f"Case {request.case_id} not found")

        if case.status == CaseStatus.ACCEPTED:
            raise ValidationError("No events allowed after ACCEPTED status")

        transition_key = (case.status, request.event_type)
        if transition_key not in VALID_TRANSITIONS:
            raise ValidationError(
                f"Invalid transition: {case.status.value} + {request.event_type.value}"
            )

        new_status = VALID_TRANSITIONS[transition_key]

        if request.event_type in (EventType.STARTED, EventType.SUBMITTED):
            if current_user.role == UserRole.WORKER:
                if case.assigned_user_id != current_user.id:
                    raise ForbiddenError("You are not assigned to this case")
        elif request.event_type in (EventType.REWORK_REQUESTED, EventType.ACCEPTED):
            if current_user.role != UserRole.ADMIN:
                raise ForbiddenError("Only ADMIN can rework/accept cases")

        if request.expected_revision is not None:
            if case.revision != request.expected_revision:
                raise ConflictError(
                    f"Revision conflict: expected {request.expected_revision}, got {case.revision}"
                )

        now = now_kst()
        event = Event(
            case_id=case.id,
            user_id=current_user.id,
            event_type=request.event_type,
            idempotency_key=request.idempotency_key,
            event_code=request.event_code,
            payload_json=request.payload_json,
            created_at=now,
        )
        db.add(event)

        case.status = new_status

        if request.event_type == EventType.STARTED:
            case.started_at = now
        elif request.event_type == EventType.SUBMITTED:
            case.worker_completed_at = now
        elif request.event_type == EventType.ACCEPTED:
            case.accepted_at = now
        elif request.event_type == EventType.REWORK_REQUESTED:
            case.revision += 1

        db.flush()

        return EventResponse(
            id=event.id,
            case_id=event.case_id,
            user_id=event.user_id,
            event_type=event.event_type,
            idempotency_key=event.idempotency_key,
            event_code=event.event_code,
            payload_json=event.payload_json,
            created_at=event.created_at,
            case_status=case.status,
            case_revision=case.revision,
        )


def create_worklog(
    db: Session, request: WorkLogCreateRequest, current_user: User
) -> WorkLogResponse:
    """
    Create a worklog entry.
    Handles START with WIP limit check and Event creation.
    """
    with db.begin():
        case = db.query(Case).filter(Case.id == request.case_id).first()
        if not case:
            raise NotFoundError(f"Case {request.case_id} not found")

        # Permission check
        if current_user.role == UserRole.WORKER:
            if case.assigned_user_id != current_user.id:
                raise ForbiddenError("You are not assigned to this case")

        # Get last action and validate sequence
        last_action = get_last_worklog_action(db, case.id)
        validate_worklog_sequence(last_action, request.action_type, case.status)

        now = now_kst()

        # Handle START action specially
        if request.action_type == ActionType.START:
            # Check WIP limit
            check_wip_limit(db, current_user.id)

            # Create Event STARTED
            import uuid
            idempotency_key = f"{case.id}-STARTED-{uuid.uuid4().hex[:8]}"
            event = Event(
                case_id=case.id,
                user_id=current_user.id,
                event_type=EventType.STARTED,
                idempotency_key=idempotency_key,
                created_at=now,
            )
            db.add(event)

            # Update case status
            case.status = CaseStatus.IN_PROGRESS
            case.started_at = now

        elif request.action_type == ActionType.REWORK_START:
            # Check WIP limit
            check_wip_limit(db, current_user.id)

            # Create Event STARTED for rework
            import uuid
            idempotency_key = f"{case.id}-STARTED-REV{case.revision}-{uuid.uuid4().hex[:8]}"
            event = Event(
                case_id=case.id,
                user_id=current_user.id,
                event_type=EventType.STARTED,
                idempotency_key=idempotency_key,
                created_at=now,
            )
            db.add(event)

            # Update case status
            case.status = CaseStatus.IN_PROGRESS

        # Create worklog
        worklog = WorkLog(
            case_id=case.id,
            user_id=current_user.id,
            action_type=request.action_type,
            reason_code=request.reason_code,
            timestamp=now,
        )
        db.add(worklog)
        db.flush()

        return WorkLogResponse(
            id=worklog.id,
            case_id=worklog.case_id,
            user_id=worklog.user_id,
            action_type=worklog.action_type,
            reason_code=worklog.reason_code,
            timestamp=worklog.timestamp,
        )


def submit_case(
    db: Session, request: SubmitRequest, current_user: User
) -> SubmitResponse:
    """
    Submit a case atomically.
    Creates WorkLog SUBMIT + Event SUBMITTED in one transaction.
    """
    with db.begin():
        # Check idempotency
        existing_event = (
            db.query(Event)
            .filter(Event.idempotency_key == request.idempotency_key)
            .first()
        )
        if existing_event:
            case = db.query(Case).filter(Case.id == existing_event.case_id).first()
            worklogs = db.query(WorkLog).filter(WorkLog.case_id == case.id).order_by(WorkLog.timestamp).all()
            auto_timeout = get_config(db, "auto_timeout_minutes")
            workday_hours = get_config(db, "workday_hours")
            work_seconds = compute_work_seconds(worklogs, auto_timeout)
            return SubmitResponse(
                worklog_id=0,
                event_id=existing_event.id,
                case_id=case.id,
                case_status=case.status,
                case_revision=case.revision,
                work_seconds=work_seconds,
                work_duration=format_duration(work_seconds),
                man_days=compute_man_days(work_seconds, workday_hours),
            )

        case = db.query(Case).filter(Case.id == request.case_id).first()
        if not case:
            raise NotFoundError(f"Case {request.case_id} not found")

        # Permission check
        if current_user.role == UserRole.WORKER:
            if case.assigned_user_id != current_user.id:
                raise ForbiddenError("You are not assigned to this case")

        # Validate state
        if case.status != CaseStatus.IN_PROGRESS:
            raise ValidationError(f"Cannot submit: case status is {case.status.value}")

        # Validate worklog sequence
        last_action = get_last_worklog_action(db, case.id)
        validate_worklog_sequence(last_action, ActionType.SUBMIT, case.status)

        # Optimistic lock
        if request.expected_revision is not None:
            if case.revision != request.expected_revision:
                raise ConflictError(
                    f"Revision conflict: expected {request.expected_revision}, got {case.revision}"
                )

        now = now_kst()

        # Create WorkLog SUBMIT
        worklog = WorkLog(
            case_id=case.id,
            user_id=current_user.id,
            action_type=ActionType.SUBMIT,
            timestamp=now,
        )
        db.add(worklog)

        # Create Event SUBMITTED
        event = Event(
            case_id=case.id,
            user_id=current_user.id,
            event_type=EventType.SUBMITTED,
            idempotency_key=request.idempotency_key,
            created_at=now,
        )
        db.add(event)

        # Update case
        case.status = CaseStatus.SUBMITTED
        case.worker_completed_at = now

        db.flush()

        # Calculate metrics
        worklogs = db.query(WorkLog).filter(WorkLog.case_id == case.id).order_by(WorkLog.timestamp).all()
        auto_timeout = get_config(db, "auto_timeout_minutes")
        workday_hours = get_config(db, "workday_hours")
        work_seconds = compute_work_seconds(worklogs, auto_timeout)

        return SubmitResponse(
            worklog_id=worklog.id,
            event_id=event.id,
            case_id=case.id,
            case_status=case.status,
            case_revision=case.revision,
            work_seconds=work_seconds,
            work_duration=format_duration(work_seconds),
            man_days=compute_man_days(work_seconds, workday_hours),
        )


def get_worker_tasks(db: Session, worker: User) -> CaseListResponse:
    """Get tasks assigned to a worker (TODO, IN_PROGRESS, REWORK)."""
    cases = (
        db.query(Case)
        .filter(
            Case.assigned_user_id == worker.id,
            Case.status.in_([CaseStatus.TODO, CaseStatus.IN_PROGRESS, CaseStatus.REWORK]),
        )
        .order_by(Case.created_at.desc())
        .all()
    )

    items = []
    for c in cases:
        items.append(
            CaseListItem(
                id=c.id,
                case_uid=c.case_uid,
                display_name=c.display_name,
                hospital=c.hospital,
                project_name=c.project.name,
                part_name=c.part.name,
                difficulty=c.difficulty,
                status=c.status,
                revision=c.revision,
                assigned_user_id=c.assigned_user_id,
                assigned_username=c.assigned_user.username if c.assigned_user else None,
                started_at=c.started_at,
                worker_completed_at=c.worker_completed_at,
                accepted_at=c.accepted_at,
                created_at=c.created_at,
            )
        )

    return CaseListResponse(total=len(items), cases=items)


def get_admin_cases(
    db: Session,
    status: Optional[CaseStatus] = None,
    project_id: Optional[int] = None,
    assigned_user_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> CaseListResponse:
    """Get cases with optional filters (ADMIN)."""
    query = db.query(Case)

    if status:
        query = query.filter(Case.status == status)
    if project_id:
        query = query.filter(Case.project_id == project_id)
    if assigned_user_id:
        query = query.filter(Case.assigned_user_id == assigned_user_id)

    total = query.count()
    cases = query.order_by(Case.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for c in cases:
        items.append(
            CaseListItem(
                id=c.id,
                case_uid=c.case_uid,
                display_name=c.display_name,
                hospital=c.hospital,
                project_name=c.project.name,
                part_name=c.part.name,
                difficulty=c.difficulty,
                status=c.status,
                revision=c.revision,
                assigned_user_id=c.assigned_user_id,
                assigned_username=c.assigned_user.username if c.assigned_user else None,
                started_at=c.started_at,
                worker_completed_at=c.worker_completed_at,
                accepted_at=c.accepted_at,
                created_at=c.created_at,
            )
        )

    return CaseListResponse(total=total, cases=items)


def get_case_detail(db: Session, case_id: int) -> CaseDetailResponse:
    """Get detailed case information including events and notes."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise NotFoundError(f"Case {case_id} not found")

    preqc = None
    if case.preqc_summary:
        preqc = PreQcSummaryResponse(
            flags_json=case.preqc_summary.flags_json,
            slice_count=case.preqc_summary.slice_count,
            expected_segments_json=case.preqc_summary.expected_segments_json,
            created_at=case.preqc_summary.created_at,
        )

    events = [
        EventListItem(
            id=e.id,
            event_type=e.event_type,
            user_id=e.user_id,
            username=e.user.username,
            event_code=e.event_code,
            payload_json=e.payload_json,
            created_at=e.created_at,
        )
        for e in case.events
    ]

    notes = [
        ReviewNoteItem(
            id=n.id,
            reviewer_user_id=n.reviewer_user_id,
            reviewer_username=n.reviewer.username,
            qc_summary_confirmed=n.qc_summary_confirmed,
            note_text=n.note_text,
            extra_tags_json=n.extra_tags_json,
            created_at=n.created_at,
        )
        for n in case.review_notes
    ]

    return CaseDetailResponse(
        id=case.id,
        case_uid=case.case_uid,
        display_name=case.display_name,
        nas_path=case.nas_path,
        hospital=case.hospital,
        slice_thickness_mm=case.slice_thickness_mm,
        project_name=case.project.name,
        part_name=case.part.name,
        difficulty=case.difficulty,
        status=case.status,
        revision=case.revision,
        assigned_user_id=case.assigned_user_id,
        assigned_username=case.assigned_user.username if case.assigned_user else None,
        metadata_json=case.metadata_json,
        started_at=case.started_at,
        worker_completed_at=case.worker_completed_at,
        accepted_at=case.accepted_at,
        created_at=case.created_at,
        preqc_summary=preqc,
        events=events,
        review_notes=notes,
    )


def get_case_detail_with_metrics(db: Session, case_id: int) -> CaseDetailWithMetricsResponse:
    """Get detailed case information including worklogs and computed metrics."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise NotFoundError(f"Case {case_id} not found")

    preqc = None
    if case.preqc_summary:
        preqc = PreQcSummaryResponse(
            flags_json=case.preqc_summary.flags_json,
            slice_count=case.preqc_summary.slice_count,
            expected_segments_json=case.preqc_summary.expected_segments_json,
            created_at=case.preqc_summary.created_at,
        )

    events = [
        EventListItem(
            id=e.id,
            event_type=e.event_type,
            user_id=e.user_id,
            username=e.user.username,
            event_code=e.event_code,
            payload_json=e.payload_json,
            created_at=e.created_at,
        )
        for e in case.events
    ]

    notes = [
        ReviewNoteItem(
            id=n.id,
            reviewer_user_id=n.reviewer_user_id,
            reviewer_username=n.reviewer.username,
            qc_summary_confirmed=n.qc_summary_confirmed,
            note_text=n.note_text,
            extra_tags_json=n.extra_tags_json,
            created_at=n.created_at,
        )
        for n in case.review_notes
    ]

    worklogs = [
        WorkLogItem(
            id=w.id,
            action_type=w.action_type,
            user_id=w.user_id,
            username=w.user.username,
            reason_code=w.reason_code,
            timestamp=w.timestamp,
        )
        for w in case.worklogs
    ]

    # Compute metrics
    auto_timeout = get_config(db, "auto_timeout_minutes")
    workday_hours = get_config(db, "workday_hours")
    work_seconds = compute_work_seconds(case.worklogs, auto_timeout)
    first_start, last_end = get_timeline_dates(case.worklogs)

    # Check if currently working
    last_action = get_last_worklog_action(db, case.id)
    is_working = last_action in (ActionType.START, ActionType.RESUME, ActionType.REWORK_START)

    metrics = CaseMetrics(
        work_seconds=work_seconds,
        work_duration=format_duration(work_seconds),
        man_days=compute_man_days(work_seconds, workday_hours),
        timeline=compute_timeline(first_start, last_end),
        is_working=is_working,
    )

    return CaseDetailWithMetricsResponse(
        id=case.id,
        case_uid=case.case_uid,
        display_name=case.display_name,
        nas_path=case.nas_path,
        hospital=case.hospital,
        slice_thickness_mm=case.slice_thickness_mm,
        project_name=case.project.name,
        part_name=case.part.name,
        difficulty=case.difficulty,
        status=case.status,
        revision=case.revision,
        assigned_user_id=case.assigned_user_id,
        assigned_username=case.assigned_user.username if case.assigned_user else None,
        metadata_json=case.metadata_json,
        started_at=case.started_at,
        worker_completed_at=case.worker_completed_at,
        accepted_at=case.accepted_at,
        created_at=case.created_at,
        preqc_summary=preqc,
        events=events,
        review_notes=notes,
        worklogs=worklogs,
        metrics=metrics,
    )


def create_review_note(
    db: Session, request: ReviewNoteCreateRequest, current_user: User
) -> ReviewNoteResponse:
    """Create a review note (ADMIN only for now)."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can create review notes")

    with db.begin():
        case = db.query(Case).filter(Case.id == request.case_id).first()
        if not case:
            raise NotFoundError(f"Case {request.case_id} not found")

        note = ReviewNote(
            case_id=case.id,
            reviewer_user_id=current_user.id,
            qc_summary_confirmed=request.qc_summary_confirmed,
            note_text=request.note_text,
            extra_tags_json=request.extra_tags_json,
        )
        db.add(note)
        db.flush()

        return ReviewNoteResponse(
            id=note.id,
            case_id=note.case_id,
            reviewer_user_id=note.reviewer_user_id,
            qc_summary_confirmed=note.qc_summary_confirmed,
            note_text=note.note_text,
            extra_tags_json=note.extra_tags_json,
            created_at=note.created_at,
        )


def get_recent_events(db: Session, limit: int = 50) -> list[EventListItem]:
    """Get recent events for admin dashboard."""
    events = (
        db.query(Event)
        .order_by(Event.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        EventListItem(
            id=e.id,
            event_type=e.event_type,
            user_id=e.user_id,
            username=e.user.username,
            event_code=e.event_code,
            payload_json=e.payload_json,
            created_at=e.created_at,
        )
        for e in events
    ]


# ============================================================
# TimeOff Services
# ============================================================

def create_timeoff(
    db: Session, request: TimeOffCreateRequest, current_user: User
) -> TimeOffResponse:
    """
    Create a time-off entry.
    ADMIN can create for any user, WORKER can only create for self.
    """
    with db.begin():
        # Permission check
        if current_user.role == UserRole.WORKER:
            if request.user_id != current_user.id:
                raise ForbiddenError("Workers can only register their own time-off")

        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise NotFoundError(f"User {request.user_id} not found")

        # Check for duplicate
        existing = (
            db.query(UserTimeOff)
            .filter(UserTimeOff.user_id == request.user_id, UserTimeOff.date == request.date)
            .first()
        )
        if existing:
            raise ValidationError(f"Time-off already registered for {request.date}")

        timeoff = UserTimeOff(
            user_id=request.user_id,
            date=request.date,
            type=request.type,
        )
        db.add(timeoff)
        db.flush()

        return TimeOffResponse(
            id=timeoff.id,
            user_id=timeoff.user_id,
            username=user.username,
            date=timeoff.date,
            type=timeoff.type,
            created_at=timeoff.created_at,
        )


def delete_timeoff(db: Session, timeoff_id: int, current_user: User) -> None:
    """
    Delete a time-off entry.
    ADMIN can delete any, WORKER can only delete their own.
    """
    with db.begin():
        timeoff = db.query(UserTimeOff).filter(UserTimeOff.id == timeoff_id).first()
        if not timeoff:
            raise NotFoundError(f"TimeOff {timeoff_id} not found")

        if current_user.role == UserRole.WORKER:
            if timeoff.user_id != current_user.id:
                raise ForbiddenError("Workers can only delete their own time-off")

        db.delete(timeoff)


def get_user_timeoffs(
    db: Session,
    user_id: int,
    start_date: Optional["date"] = None,
    end_date: Optional["date"] = None,
) -> TimeOffListResponse:
    """Get time-offs for a specific user."""
    from datetime import date as date_type

    query = db.query(UserTimeOff).filter(UserTimeOff.user_id == user_id)

    if start_date:
        query = query.filter(UserTimeOff.date >= start_date)
    if end_date:
        query = query.filter(UserTimeOff.date <= end_date)

    timeoffs = query.order_by(UserTimeOff.date.desc()).all()

    return TimeOffListResponse(
        timeoffs=[
            TimeOffResponse(
                id=t.id,
                user_id=t.user_id,
                username=t.user.username,
                date=t.date,
                type=t.type,
                created_at=t.created_at,
            )
            for t in timeoffs
        ]
    )


def get_all_timeoffs(
    db: Session,
    start_date: Optional["date"] = None,
    end_date: Optional["date"] = None,
) -> TimeOffListResponse:
    """Get all time-offs (ADMIN only)."""
    from datetime import date as date_type

    query = db.query(UserTimeOff)

    if start_date:
        query = query.filter(UserTimeOff.date >= start_date)
    if end_date:
        query = query.filter(UserTimeOff.date <= end_date)

    timeoffs = query.order_by(UserTimeOff.date.desc()).all()

    return TimeOffListResponse(
        timeoffs=[
            TimeOffResponse(
                id=t.id,
                user_id=t.user_id,
                username=t.user.username,
                date=t.date,
                type=t.type,
                created_at=t.created_at,
            )
            for t in timeoffs
        ]
    )


# ============================================================
# Holiday (WorkCalendar) Services
# ============================================================

def get_work_calendar(db: Session) -> WorkCalendar:
    """Get or create the work calendar."""
    calendar = db.query(WorkCalendar).first()
    if not calendar:
        calendar = WorkCalendar(holidays_json="[]", timezone="Asia/Seoul")
        db.add(calendar)
        db.commit()
        db.refresh(calendar)
    return calendar


def get_holidays(db: Session) -> HolidayListResponse:
    """Get the list of holidays."""
    from datetime import date as date_type

    calendar = get_work_calendar(db)
    holidays_list = json.loads(calendar.holidays_json)

    # Convert strings to date objects
    holidays = [date_type.fromisoformat(d) for d in holidays_list]

    return HolidayListResponse(
        holidays=sorted(holidays),
        timezone=calendar.timezone,
    )


def update_holidays(
    db: Session, request: HolidayUpdateRequest, current_user: User
) -> HolidayListResponse:
    """Update the list of holidays (ADMIN only)."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can update holidays")

    with db.begin():
        calendar = get_work_calendar(db)

        # Convert dates to strings for JSON storage
        holidays_str = [d.isoformat() for d in sorted(request.holidays)]
        calendar.holidays_json = json.dumps(holidays_str)
        db.flush()

    return HolidayListResponse(
        holidays=sorted(request.holidays),
        timezone=calendar.timezone,
    )


def add_holiday(db: Session, holiday_date: "date", current_user: User) -> HolidayListResponse:
    """Add a single holiday (ADMIN only)."""
    from datetime import date as date_type

    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can add holidays")

    with db.begin():
        calendar = get_work_calendar(db)
        holidays_list = json.loads(calendar.holidays_json)

        date_str = holiday_date.isoformat()
        if date_str not in holidays_list:
            holidays_list.append(date_str)
            holidays_list.sort()
            calendar.holidays_json = json.dumps(holidays_list)
            db.flush()

    holidays = [date_type.fromisoformat(d) for d in holidays_list]
    return HolidayListResponse(holidays=sorted(holidays), timezone=calendar.timezone)


def remove_holiday(db: Session, holiday_date: "date", current_user: User) -> HolidayListResponse:
    """Remove a single holiday (ADMIN only)."""
    from datetime import date as date_type

    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can remove holidays")

    with db.begin():
        calendar = get_work_calendar(db)
        holidays_list = json.loads(calendar.holidays_json)

        date_str = holiday_date.isoformat()
        if date_str in holidays_list:
            holidays_list.remove(date_str)
            calendar.holidays_json = json.dumps(holidays_list)
            db.flush()

    holidays = [date_type.fromisoformat(d) for d in holidays_list]
    return HolidayListResponse(holidays=sorted(holidays), timezone=calendar.timezone)


# ============================================================
# Capacity Metrics Services
# ============================================================

def get_team_capacity(
    db: Session,
    start_date: "date",
    end_date: "date",
) -> TeamCapacityResponse:
    """
    Compute capacity metrics for all workers in a date range.
    """
    from datetime import date as date_type

    # Get holidays
    calendar = get_work_calendar(db)
    holidays_list = json.loads(calendar.holidays_json)
    holidays = [date_type.fromisoformat(d) for d in holidays_list]

    # Get all active workers
    workers = db.query(User).filter(User.role == UserRole.WORKER, User.is_active == True).all()

    # Config
    workday_hours = get_config(db, "workday_hours")
    auto_timeout = get_config(db, "auto_timeout_minutes")

    user_metrics = []
    total_available = 0.0
    total_actual = 0.0

    for worker in workers:
        # Get user's time-offs
        timeoffs = (
            db.query(UserTimeOff)
            .filter(
                UserTimeOff.user_id == worker.id,
                UserTimeOff.date >= start_date,
                UserTimeOff.date <= end_date,
            )
            .all()
        )

        # Get user's worklogs in the period
        worklogs = (
            db.query(WorkLog)
            .filter(
                WorkLog.user_id == worker.id,
                WorkLog.timestamp >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE),
                WorkLog.timestamp <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE),
            )
            .order_by(WorkLog.timestamp)
            .all()
        )

        metrics = compute_capacity_metrics(
            user_id=worker.id,
            username=worker.username,
            start_date=start_date,
            end_date=end_date,
            holidays=holidays,
            timeoffs=timeoffs,
            worklogs=worklogs,
            workday_hours=workday_hours,
            auto_timeout_minutes=auto_timeout,
        )

        user_metrics.append(CapacityMetrics(**metrics))
        total_available += metrics["available_hours"]
        total_actual += metrics["actual_work_hours"]

    # Team utilization
    team_utilization = round(total_actual / total_available, 4) if total_available > 0 else 0.0

    return TeamCapacityResponse(
        period_start=start_date,
        period_end=end_date,
        users=user_metrics,
        total_available_hours=round(total_available, 2),
        total_actual_hours=round(total_actual, 2),
        team_utilization_rate=team_utilization,
    )


# ============================================================
# AutoQC Summary Services
# ============================================================

def save_autoqc_summary(
    db: Session, request: AutoQcSummaryCreateRequest, current_user: User
) -> AutoQcSummaryResponse:
    """
    Save Auto-QC summary from local client.
    NOTE: Server does NOT run Auto-QC - it only stores the summary.
    The actual QC runs on local PC (offline-first, cost=0).
    """
    with db.begin():
        case = db.query(Case).filter(Case.id == request.case_id).first()
        if not case:
            raise NotFoundError(f"Case {request.case_id} not found")

        # Check if summary already exists
        existing = db.query(AutoQcSummary).filter(
            AutoQcSummary.case_id == request.case_id
        ).first()

        if existing:
            # Update existing
            existing.qc_pass = request.qc_pass
            existing.missing_segments_json = request.missing_segments_json
            existing.geometry_mismatch = request.geometry_mismatch
            existing.warnings_json = request.warnings_json
            existing.created_at = now_kst()
            db.flush()

            return AutoQcSummaryResponse(
                id=existing.id,
                case_id=existing.case_id,
                qc_pass=existing.qc_pass,
                missing_segments_json=existing.missing_segments_json,
                geometry_mismatch=existing.geometry_mismatch,
                warnings_json=existing.warnings_json,
                created_at=existing.created_at,
            )
        else:
            # Create new
            summary = AutoQcSummary(
                case_id=request.case_id,
                qc_pass=request.qc_pass,
                missing_segments_json=request.missing_segments_json,
                geometry_mismatch=request.geometry_mismatch,
                warnings_json=request.warnings_json,
            )
            db.add(summary)
            db.flush()

            return AutoQcSummaryResponse(
                id=summary.id,
                case_id=summary.case_id,
                qc_pass=summary.qc_pass,
                missing_segments_json=summary.missing_segments_json,
                geometry_mismatch=summary.geometry_mismatch,
                warnings_json=summary.warnings_json,
                created_at=summary.created_at,
            )


def get_autoqc_summary(db: Session, case_id: int) -> Optional[AutoQcSummaryResponse]:
    """Get Auto-QC summary for a case."""
    summary = db.query(AutoQcSummary).filter(AutoQcSummary.case_id == case_id).first()
    if not summary:
        return None

    return AutoQcSummaryResponse(
        id=summary.id,
        case_id=summary.case_id,
        qc_pass=summary.qc_pass,
        missing_segments_json=summary.missing_segments_json,
        geometry_mismatch=summary.geometry_mismatch,
        warnings_json=summary.warnings_json,
        created_at=summary.created_at,
    )


# ============================================================
# QC Disagreement Services
# ============================================================

def get_qc_disagreements(
    db: Session,
    part_name: Optional[str] = None,
    hospital: Optional[str] = None,
    difficulty: Optional[str] = None,
    start_date: Optional["date"] = None,
    end_date: Optional["date"] = None,
) -> QcDisagreementListResponse:
    """
    Get list of QC disagreements.

    Disagreement = (autoqc.qc_pass=False AND accepted=True)
                   OR (autoqc.qc_pass=True AND rework_requested=True)
    """
    from datetime import date as date_type

    # Get all cases with AutoQC summary
    query = (
        db.query(Case, AutoQcSummary)
        .join(AutoQcSummary, Case.id == AutoQcSummary.case_id)
        .join(Part, Case.part_id == Part.id)
    )

    # Apply filters
    if part_name:
        query = query.filter(Part.name == part_name)
    if hospital:
        query = query.filter(Case.hospital == hospital)
    if difficulty:
        query = query.filter(Case.difficulty == difficulty)
    if start_date:
        query = query.filter(Case.created_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE))
    if end_date:
        query = query.filter(Case.created_at <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE))

    results = query.all()

    disagreements = []

    for case, autoqc in results:
        # Check for disagreement
        has_rework_event = any(e.event_type == EventType.REWORK_REQUESTED for e in case.events)
        is_accepted = case.status == CaseStatus.ACCEPTED

        disagreement_type = None

        # FALSE_NEGATIVE: AutoQC said FAIL but human accepted
        if not autoqc.qc_pass and is_accepted:
            disagreement_type = "FALSE_NEGATIVE"

        # FALSE_POSITIVE: AutoQC said PASS but rework was requested
        if autoqc.qc_pass and has_rework_event:
            disagreement_type = "FALSE_POSITIVE"

        if disagreement_type:
            # Find rework event timestamp
            rework_event = next(
                (e for e in case.events if e.event_type == EventType.REWORK_REQUESTED),
                None
            )

            disagreements.append(QcDisagreementItem(
                case_id=case.id,
                case_uid=case.case_uid,
                display_name=case.display_name,
                hospital=case.hospital,
                part_name=case.part.name,
                difficulty=case.difficulty,
                autoqc_pass=autoqc.qc_pass,
                case_status=case.status,
                disagreement_type=disagreement_type,
                accepted_at=case.accepted_at,
                rework_requested_at=rework_event.created_at if rework_event else None,
            ))

    return QcDisagreementListResponse(
        total=len(disagreements),
        disagreements=disagreements,
    )


def get_qc_disagreement_stats(
    db: Session,
    start_date: Optional["date"] = None,
    end_date: Optional["date"] = None,
) -> QcDisagreementStats:
    """
    Calculate QC disagreement statistics.
    """
    from datetime import date as date_type

    # Get all cases with AutoQC summary
    query = (
        db.query(Case, AutoQcSummary)
        .join(AutoQcSummary, Case.id == AutoQcSummary.case_id)
        .join(Part, Case.part_id == Part.id)
    )

    if start_date:
        query = query.filter(Case.created_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE))
    if end_date:
        query = query.filter(Case.created_at <= datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE))

    results = query.all()

    total_cases = len(results)
    false_positives = 0
    false_negatives = 0

    # Stats by category
    by_part: dict = {}
    by_hospital: dict = {}
    by_difficulty: dict = {}

    for case, autoqc in results:
        has_rework_event = any(e.event_type == EventType.REWORK_REQUESTED for e in case.events)
        is_accepted = case.status == CaseStatus.ACCEPTED

        is_disagreement = False
        if not autoqc.qc_pass and is_accepted:
            false_negatives += 1
            is_disagreement = True
        if autoqc.qc_pass and has_rework_event:
            false_positives += 1
            is_disagreement = True

        # Update by_part stats
        part_name = case.part.name
        if part_name not in by_part:
            by_part[part_name] = {"total": 0, "disagreements": 0}
        by_part[part_name]["total"] += 1
        if is_disagreement:
            by_part[part_name]["disagreements"] += 1

        # Update by_hospital stats
        hosp = case.hospital or "Unknown"
        if hosp not in by_hospital:
            by_hospital[hosp] = {"total": 0, "disagreements": 0}
        by_hospital[hosp]["total"] += 1
        if is_disagreement:
            by_hospital[hosp]["disagreements"] += 1

        # Update by_difficulty stats
        diff = case.difficulty.value
        if diff not in by_difficulty:
            by_difficulty[diff] = {"total": 0, "disagreements": 0}
        by_difficulty[diff]["total"] += 1
        if is_disagreement:
            by_difficulty[diff]["disagreements"] += 1

    # Calculate rates
    total_disagreements = false_positives + false_negatives
    disagreement_rate = round(total_disagreements / total_cases, 4) if total_cases > 0 else 0.0

    for stats in [by_part, by_hospital, by_difficulty]:
        for key in stats:
            t = stats[key]["total"]
            d = stats[key]["disagreements"]
            stats[key]["rate"] = round(d / t, 4) if t > 0 else 0.0

    return QcDisagreementStats(
        total_cases_with_autoqc=total_cases,
        total_disagreements=total_disagreements,
        disagreement_rate=disagreement_rate,
        false_positives=false_positives,
        false_negatives=false_negatives,
        by_part=by_part,
        by_hospital=by_hospital,
        by_difficulty=by_difficulty,
    )


# ============================================================
# Step 5: Cohort Tagging Services
# ============================================================

def apply_tags(
    db: Session, request: ApplyTagsRequest, current_user: User
) -> ApplyTagsResponse:
    """
    Apply a tag to multiple cases by case_uid.
    ADMIN only.
    """
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can apply tags")

    applied_count = 0
    skipped_count = 0
    not_found_count = 0

    with db.begin():
        for case_uid in request.case_uids:
            case = db.query(Case).filter(Case.case_uid == case_uid).first()
            if not case:
                not_found_count += 1
                continue

            # Check if tag already exists
            existing = db.query(CaseTag).filter(
                CaseTag.case_id == case.id,
                CaseTag.tag_text == request.tag_text,
            ).first()

            if existing:
                skipped_count += 1
            else:
                tag = CaseTag(case_id=case.id, tag_text=request.tag_text)
                db.add(tag)
                applied_count += 1

    return ApplyTagsResponse(
        tag_text=request.tag_text,
        applied_count=applied_count,
        skipped_count=skipped_count,
        not_found_count=not_found_count,
    )


def remove_tags(
    db: Session, request: RemoveTagRequest, current_user: User
) -> RemoveTagResponse:
    """
    Remove a tag from multiple cases.
    ADMIN only.
    """
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can remove tags")

    removed_count = 0

    with db.begin():
        for case_uid in request.case_uids:
            case = db.query(Case).filter(Case.case_uid == case_uid).first()
            if not case:
                continue

            tag = db.query(CaseTag).filter(
                CaseTag.case_id == case.id,
                CaseTag.tag_text == request.tag_text,
            ).first()

            if tag:
                db.delete(tag)
                removed_count += 1

    return RemoveTagResponse(
        tag_text=request.tag_text,
        removed_count=removed_count,
    )


def get_all_tags(db: Session) -> TagListResponse:
    """Get all unique tag names."""
    tags = db.query(CaseTag.tag_text).distinct().order_by(CaseTag.tag_text).all()
    return TagListResponse(tags=[t[0] for t in tags])


def get_cases_by_tag(db: Session, tag_text: str) -> CasesByTagResponse:
    """Get all cases with a specific tag."""
    tagged_case_ids = db.query(CaseTag.case_id).filter(CaseTag.tag_text == tag_text).all()
    case_ids = [t[0] for t in tagged_case_ids]

    if not case_ids:
        return CasesByTagResponse(tag_text=tag_text, total=0, cases=[])

    cases = db.query(Case).filter(Case.id.in_(case_ids)).order_by(Case.created_at.desc()).all()

    items = [
        CaseListItem(
            id=c.id,
            case_uid=c.case_uid,
            display_name=c.display_name,
            hospital=c.hospital,
            project_name=c.project.name,
            part_name=c.part.name,
            difficulty=c.difficulty,
            status=c.status,
            revision=c.revision,
            assigned_user_id=c.assigned_user_id,
            assigned_username=c.assigned_user.username if c.assigned_user else None,
            started_at=c.started_at,
            worker_completed_at=c.worker_completed_at,
            accepted_at=c.accepted_at,
            created_at=c.created_at,
        )
        for c in cases
    ]

    return CasesByTagResponse(tag_text=tag_text, total=len(items), cases=items)


# ============================================================
# Step 5: Definition Snapshot Services
# ============================================================

def create_definition_snapshot(
    db: Session, request: DefinitionSnapshotCreateRequest, current_user: User
) -> DefinitionSnapshotResponse:
    """
    Create a new definition snapshot (frozen version).
    ADMIN only.
    """
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can create definition snapshots")

    # Validate JSON
    try:
        json.loads(request.content_json)
    except json.JSONDecodeError:
        raise ValidationError("content_json must be valid JSON")

    with db.begin():
        # Check for duplicate version name
        existing = db.query(DefinitionSnapshot).filter(
            DefinitionSnapshot.version_name == request.version_name
        ).first()
        if existing:
            raise ValidationError(f"Version '{request.version_name}' already exists")

        snapshot = DefinitionSnapshot(
            version_name=request.version_name,
            content_json=request.content_json,
        )
        db.add(snapshot)
        db.flush()

        return DefinitionSnapshotResponse(
            id=snapshot.id,
            version_name=snapshot.version_name,
            content_json=snapshot.content_json,
            created_at=snapshot.created_at,
        )


def get_definition_snapshots(db: Session) -> DefinitionSnapshotListResponse:
    """Get all definition snapshots."""
    snapshots = db.query(DefinitionSnapshot).order_by(DefinitionSnapshot.created_at.desc()).all()

    return DefinitionSnapshotListResponse(
        definitions=[
            DefinitionSnapshotResponse(
                id=s.id,
                version_name=s.version_name,
                content_json=s.content_json,
                created_at=s.created_at,
            )
            for s in snapshots
        ]
    )


def get_definition_snapshot_by_version(
    db: Session, version_name: str
) -> Optional[DefinitionSnapshotResponse]:
    """Get a specific definition snapshot by version name."""
    snapshot = db.query(DefinitionSnapshot).filter(
        DefinitionSnapshot.version_name == version_name
    ).first()

    if not snapshot:
        return None

    return DefinitionSnapshotResponse(
        id=snapshot.id,
        version_name=snapshot.version_name,
        content_json=snapshot.content_json,
        created_at=snapshot.created_at,
    )


# ============================================================
# Step 5: Project-Definition Link Services
# ============================================================

def link_project_definition(
    db: Session, request: ProjectDefinitionLinkRequest, current_user: User
) -> ProjectDefinitionLinkResponse:
    """
    Link a project to a definition snapshot.
    ADMIN only.
    """
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only ADMIN can link project definitions")

    with db.begin():
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise NotFoundError(f"Project {request.project_id} not found")

        snapshot = db.query(DefinitionSnapshot).filter(
            DefinitionSnapshot.id == request.definition_snapshot_id
        ).first()
        if not snapshot:
            raise NotFoundError(f"Definition snapshot {request.definition_snapshot_id} not found")

        # Check if link already exists
        existing = db.query(ProjectDefinitionLink).filter(
            ProjectDefinitionLink.project_id == request.project_id,
            ProjectDefinitionLink.definition_snapshot_id == request.definition_snapshot_id,
        ).first()

        if existing:
            return ProjectDefinitionLinkResponse(
                id=existing.id,
                project_id=existing.project_id,
                project_name=project.name,
                definition_snapshot_id=existing.definition_snapshot_id,
                definition_version_name=snapshot.version_name,
                created_at=existing.created_at,
            )

        link = ProjectDefinitionLink(
            project_id=request.project_id,
            definition_snapshot_id=request.definition_snapshot_id,
        )
        db.add(link)
        db.flush()

        return ProjectDefinitionLinkResponse(
            id=link.id,
            project_id=link.project_id,
            project_name=project.name,
            definition_snapshot_id=link.definition_snapshot_id,
            definition_version_name=snapshot.version_name,
            created_at=link.created_at,
        )


def get_project_definition_links(db: Session) -> ProjectDefinitionListResponse:
    """Get all project-definition links."""
    links = (
        db.query(ProjectDefinitionLink)
        .order_by(ProjectDefinitionLink.created_at.desc())
        .all()
    )

    return ProjectDefinitionListResponse(
        links=[
            ProjectDefinitionLinkResponse(
                id=l.id,
                project_id=l.project_id,
                project_name=l.project.name,
                definition_snapshot_id=l.definition_snapshot_id,
                definition_version_name=l.definition_snapshot.version_name,
                created_at=l.created_at,
            )
            for l in links
        ]
    )


def get_project_definitions(db: Session, project_id: int) -> ProjectDefinitionListResponse:
    """Get definition links for a specific project."""
    links = (
        db.query(ProjectDefinitionLink)
        .filter(ProjectDefinitionLink.project_id == project_id)
        .order_by(ProjectDefinitionLink.created_at.desc())
        .all()
    )

    return ProjectDefinitionListResponse(
        links=[
            ProjectDefinitionLinkResponse(
                id=l.id,
                project_id=l.project_id,
                project_name=l.project.name,
                definition_snapshot_id=l.definition_snapshot_id,
                definition_version_name=l.definition_snapshot.version_name,
                created_at=l.created_at,
            )
            for l in links
        ]
    )


# ============================================================
# Step 5: Cohort Summary (Metrics with Filters)
# ============================================================

def get_cohort_summary(
    db: Session, cohort_filter: CohortFilter
) -> CohortSummary:
    """
    Compute summary metrics for a cohort defined by filters.
    Metrics are computed on-the-fly, never stored.
    """
    from datetime import date as date_type

    query = db.query(Case)

    # Apply filters
    if cohort_filter.tag:
        tagged_case_ids = db.query(CaseTag.case_id).filter(
            CaseTag.tag_text == cohort_filter.tag
        ).subquery()
        query = query.filter(Case.id.in_(tagged_case_ids))

    if cohort_filter.project_id:
        query = query.filter(Case.project_id == cohort_filter.project_id)

    if cohort_filter.definition_version:
        # Find projects linked to this definition version
        snapshot = db.query(DefinitionSnapshot).filter(
            DefinitionSnapshot.version_name == cohort_filter.definition_version
        ).first()
        if snapshot:
            linked_project_ids = db.query(ProjectDefinitionLink.project_id).filter(
                ProjectDefinitionLink.definition_snapshot_id == snapshot.id
            ).subquery()
            query = query.filter(Case.project_id.in_(linked_project_ids))
        else:
            # No matching definition, return empty
            return CohortSummary(
                filter_applied=cohort_filter,
                total_cases=0,
                by_status={},
                by_difficulty={},
                by_part={},
                by_hospital={},
                total_work_seconds=0,
                total_man_days=0.0,
                avg_work_seconds_per_case=0.0,
            )

    if cohort_filter.status:
        query = query.filter(Case.status == cohort_filter.status)

    if cohort_filter.start_date:
        query = query.filter(
            Case.created_at >= datetime.combine(
                cohort_filter.start_date, datetime.min.time()
            ).replace(tzinfo=TIMEZONE)
        )

    if cohort_filter.end_date:
        query = query.filter(
            Case.created_at <= datetime.combine(
                cohort_filter.end_date, datetime.max.time()
            ).replace(tzinfo=TIMEZONE)
        )

    cases = query.all()

    # Compute aggregations
    total_cases = len(cases)
    by_status: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    by_part: dict[str, int] = {}
    by_hospital: dict[str, int] = {}

    auto_timeout = get_config(db, "auto_timeout_minutes")
    workday_hours = get_config(db, "workday_hours")
    total_work_seconds = 0

    for case in cases:
        # Status
        status_key = case.status.value
        by_status[status_key] = by_status.get(status_key, 0) + 1

        # Difficulty
        diff_key = case.difficulty.value
        by_difficulty[diff_key] = by_difficulty.get(diff_key, 0) + 1

        # Part
        part_key = case.part.name
        by_part[part_key] = by_part.get(part_key, 0) + 1

        # Hospital
        hosp_key = case.hospital or "Unknown"
        by_hospital[hosp_key] = by_hospital.get(hosp_key, 0) + 1

        # Work time
        work_seconds = compute_work_seconds(case.worklogs, auto_timeout)
        total_work_seconds += work_seconds

    total_man_days = compute_man_days(total_work_seconds, workday_hours)
    avg_work_seconds = total_work_seconds / total_cases if total_cases > 0 else 0.0

    return CohortSummary(
        filter_applied=cohort_filter,
        total_cases=total_cases,
        by_status=by_status,
        by_difficulty=by_difficulty,
        by_part=by_part,
        by_hospital=by_hospital,
        total_work_seconds=total_work_seconds,
        total_man_days=round(total_man_days, 2),
        avg_work_seconds_per_case=round(avg_work_seconds, 2),
    )
