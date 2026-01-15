"""
Demo data seed script.
Creates 50 realistic test cases with full workflow coverage.

Usage:
    del data\\app.db  (optional - for fresh start)
    python seed_demo.py

Deterministic output: uses fixed random seed for reproducibility.
"""
import argparse
import json
import random
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config import TIMEZONE
from database import SessionLocal, init_db
from models import (
    ActionType,
    AppConfig,
    AutoQcSummary,
    Case,
    CaseStatus,
    Difficulty,
    Event,
    EventType,
    Part,
    PreQcSummary,
    Project,
    ReviewerQcFeedback,
    ReviewNote,
    User,
    UserRole,
    WorkCalendar,
    WorkerQcFeedback,
    WorkLog,
)


# =============================================================================
# 상태 매핑표 (스펙 vs 실제 enum)
# =============================================================================
"""
| 스펙 상태     | 실제 enum              | 구현 방식                        |
|--------------|------------------------|----------------------------------|
| TODO         | CaseStatus.TODO        | 동일                             |
| ASSIGNED     | CaseStatus.TODO        | TODO + assigned_user_id != None  |
| IN_PROGRESS  | CaseStatus.IN_PROGRESS | 동일                             |
| SUBMITTED    | CaseStatus.SUBMITTED   | 동일                             |
| IN_REVIEW    | CaseStatus.SUBMITTED   | SUBMITTED (검수 중 = 동일)       |
| REWORK       | CaseStatus.REWORK      | 동일                             |
| COMPLETED    | CaseStatus.ACCEPTED    | COMPLETED → ACCEPTED             |
"""


# =============================================================================
# Constants & Configuration
# =============================================================================
RANDOM_SEED = 42
MONTHS_BACK = 3

# 난이도 분포: EASY 30%, NORMAL 50%, HARD 20%
DIFFICULTY_WEIGHTS = {
    Difficulty.EASY: 15,
    Difficulty.NORMAL: 25,
    Difficulty.HARD: 10,
}

# 작업자 분포
WORKER_DISTRIBUTION = {
    "worker1": 15,
    "worker2": 15,
    "worker3": 12,
    "worker4": 8,
}

# Auto-QC 상태 분포 (PASS 60%, WARN 30%, INCOMPLETE 10%)
AUTOQC_STATUS_WEIGHTS = {
    "PASS": 60,
    "WARN": 30,
    "INCOMPLETE": 10,
}

# Pre-QC flags
PREQC_FLAGS = [
    "low_contrast",
    "vessel_discontinuity",
    "motion_artifact",
    "calcification",
    "breathing_artifact",
    "metal_artifact",
]

# 병원 목록
HOSPITALS = [
    "서울대병원",
    "세브란스병원",
    "아산병원",
    "삼성병원",
    "고대병원",
    "분당서울대병원",
]

# 부위 목록
PARTS = [
    "Liver",
    "Kidney",
    "Abdomen",
    "Spine",
    "Chest",
    "Pelvis",
]

# 프로젝트 목록
PROJECTS = [
    "CT Segmentation 2026",
    "MRI Analysis Project",
    "Vessel Annotation",
]

# QC 이슈 템플릿
QC_ISSUES_TEMPLATES = {
    "WARN": [
        {"code": "SEGMENT_NAME_MISMATCH", "level": "WARN", "segment": "IVC", "message": "세그먼트 이름 불일치"},
        {"code": "CONTACT", "level": "WARN", "segment": "Aorta, Portal_vein", "message": "혈관 접촉 감지"},
        {"code": "FRAGMENTED", "level": "WARN", "segment": "Hepatic_vein", "message": "분절된 혈관 감지"},
    ],
    "INCOMPLETE": [
        {"code": "MISSING_REQUIRED", "level": "INCOMPLETE", "segment": "Aorta", "message": "필수 세그먼트 누락"},
        {"code": "GEOMETRY_MISMATCH", "level": "INCOMPLETE", "segment": "Volume", "message": "지오메트리 불일치"},
    ],
}


def generate_idempotency_key(case_id: int, event_type: str) -> str:
    """Generate unique idempotency key."""
    return f"{case_id}_{event_type}_{uuid.uuid4().hex[:8]}"


def random_datetime_in_range(start: datetime, end: datetime) -> datetime:
    """Generate random datetime between start and end."""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def add_hours(dt: datetime, hours: int) -> datetime:
    """Add hours to datetime."""
    return dt + timedelta(hours=hours)


def add_days(dt: datetime, days: int) -> datetime:
    """Add days to datetime."""
    return dt + timedelta(days=days)


# =============================================================================
# Seed Functions
# =============================================================================

def seed_master_data(db: Session) -> dict:
    """Create master data: users, projects, parts, config, calendar."""
    result = {"users": {}, "projects": {}, "parts": {}}

    # Users
    users_data = [
        {"username": "admin1", "role": UserRole.ADMIN, "api_key": "demo_admin1"},
        {"username": "admin2", "role": UserRole.ADMIN, "api_key": "demo_admin2"},
        {"username": "worker1", "role": UserRole.WORKER, "api_key": "demo_worker1"},
        {"username": "worker2", "role": UserRole.WORKER, "api_key": "demo_worker2"},
        {"username": "worker3", "role": UserRole.WORKER, "api_key": "demo_worker3"},
        {"username": "worker4", "role": UserRole.WORKER, "api_key": "demo_worker4"},
    ]

    for data in users_data:
        user = db.query(User).filter(User.username == data["username"]).first()
        if not user:
            user = User(**data, is_active=True)
            db.add(user)
            db.flush()
        result["users"][data["username"]] = user

    # Projects
    for name in PROJECTS:
        project = db.query(Project).filter(Project.name == name).first()
        if not project:
            project = Project(name=name, is_active=True)
            db.add(project)
            db.flush()
        result["projects"][name] = project

    # Parts
    for name in PARTS:
        part = db.query(Part).filter(Part.name == name).first()
        if not part:
            part = Part(name=name, is_active=True)
            db.add(part)
            db.flush()
        result["parts"][name] = part

    # AppConfig
    default_configs = {
        "workday_hours": 8,
        "wip_limit": 3,
        "auto_timeout_minutes": 120,
        "difficulty_weights": {"EASY": 1.0, "NORMAL": 1.5, "HARD": 2.0, "VERY_HARD": 2.5},
    }
    for key, value in default_configs.items():
        existing = db.query(AppConfig).filter(AppConfig.key == key).first()
        if not existing:
            db.add(AppConfig(key=key, value_json=json.dumps(value)))

    # WorkCalendar
    existing_cal = db.query(WorkCalendar).first()
    if not existing_cal:
        holidays = [
            "2025-11-01", "2025-12-25",
            "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18",
            "2026-03-01",
        ]
        db.add(WorkCalendar(holidays_json=json.dumps(holidays), timezone="Asia/Seoul"))

    db.commit()
    return result


def create_preqc(db: Session, case: Case, difficulty: Difficulty) -> PreQcSummary:
    """Create Pre-QC summary for a case."""
    # flags 결정 (약 20% 케이스에 flags 포함)
    flags = []
    if random.random() < 0.25:
        num_flags = random.randint(1, 3)
        flags = random.sample(PREQC_FLAGS, min(num_flags, len(PREQC_FLAGS)))

    expected_segments = ["Aorta", "IVC", "Portal_vein", "Hepatic_vein"]
    if random.random() < 0.3:
        expected_segments.extend(["Renal_artery", "Renal_vein"])

    preqc = PreQcSummary(
        case_id=case.id,
        slice_count=random.randint(200, 600),
        slice_thickness_mm=random.choice([0.5, 1.0, 1.5, 2.0, 2.5]),
        slice_thickness_flag=random.choice(["OK", "OK", "OK", "WARN", "THICK"]),
        noise_level=random.choice(["LOW", "LOW", "MODERATE", "MODERATE", "HIGH"]),
        contrast_flag=random.choice(["GOOD", "GOOD", "GOOD", "BORDERLINE", "POOR"]),
        vascular_visibility_level=random.choice(["EXCELLENT", "USABLE", "USABLE", "BORDERLINE"]),
        difficulty=difficulty.value,
        flags_json=json.dumps(flags) if flags else None,
        expected_segments_json=json.dumps(expected_segments),
    )
    db.add(preqc)
    return preqc


def create_autoqc(db: Session, case: Case, status: str) -> AutoQcSummary:
    """Create Auto-QC summary for a case."""
    issues = []

    if status == "WARN":
        num_issues = random.randint(1, 3)
        issues = random.sample(QC_ISSUES_TEMPLATES["WARN"], min(num_issues, len(QC_ISSUES_TEMPLATES["WARN"])))
    elif status == "INCOMPLETE":
        issues = QC_ISSUES_TEMPLATES["INCOMPLETE"][:random.randint(1, 2)]
        if random.random() < 0.5:
            issues.extend(random.sample(QC_ISSUES_TEMPLATES["WARN"], 1))

    autoqc = AutoQcSummary(
        case_id=case.id,
        status=status,
        issues_json=json.dumps(issues) if issues else None,
        issue_count_json=json.dumps({
            "warn_level": sum(1 for i in issues if i.get("level") == "WARN"),
            "incomplete_level": sum(1 for i in issues if i.get("level") == "INCOMPLETE"),
        }) if issues else None,
        geometry_mismatch=(status == "INCOMPLETE" and random.random() < 0.5),
    )
    db.add(autoqc)
    return autoqc


def create_event(
    db: Session,
    case: Case,
    user: User,
    event_type: EventType,
    created_at: datetime,
    payload: Optional[dict] = None,
    event_code: Optional[str] = None,
) -> Event:
    """Create an event record."""
    event = Event(
        case_id=case.id,
        user_id=user.id,
        event_type=event_type,
        idempotency_key=generate_idempotency_key(case.id, event_type.value),
        event_code=event_code,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        created_at=created_at,
    )
    db.add(event)
    return event


def create_worklog(
    db: Session,
    case: Case,
    user: User,
    action_type: ActionType,
    timestamp: datetime,
    reason_code: Optional[str] = None,
) -> WorkLog:
    """Create a worklog record."""
    worklog = WorkLog(
        case_id=case.id,
        user_id=user.id,
        action_type=action_type,
        timestamp=timestamp,
        reason_code=reason_code,
    )
    db.add(worklog)
    return worklog


def create_worker_feedback(
    db: Session,
    case: Case,
    user: User,
    qc_fixes: Optional[list] = None,
    additional_fixes: Optional[list] = None,
    memo: Optional[str] = None,
) -> WorkerQcFeedback:
    """Create worker QC feedback."""
    feedback = WorkerQcFeedback(
        case_id=case.id,
        user_id=user.id,
        qc_fixes_json=json.dumps(qc_fixes, ensure_ascii=False) if qc_fixes else None,
        additional_fixes_json=json.dumps(additional_fixes, ensure_ascii=False) if additional_fixes else None,
        memo=memo,
    )
    db.add(feedback)
    return feedback


def create_reviewer_feedback(
    db: Session,
    case: Case,
    reviewer: User,
    has_disagreement: bool = False,
    disagreement_type: Optional[str] = None,
    disagreement_detail: Optional[str] = None,
    segments: Optional[list] = None,
    review_memo: Optional[str] = None,
) -> ReviewerQcFeedback:
    """Create reviewer QC feedback."""
    feedback = ReviewerQcFeedback(
        case_id=case.id,
        reviewer_id=reviewer.id,
        has_disagreement=has_disagreement,
        disagreement_type=disagreement_type,
        disagreement_detail=disagreement_detail,
        disagreement_segments_json=json.dumps(segments, ensure_ascii=False) if segments else None,
        review_memo=review_memo,
    )
    db.add(feedback)
    return feedback


def create_review_note(
    db: Session,
    case: Case,
    reviewer: User,
    note_text: str,
    created_at: datetime,
    qc_confirmed: bool = False,
) -> ReviewNote:
    """Create review note."""
    note = ReviewNote(
        case_id=case.id,
        reviewer_user_id=reviewer.id,
        note_text=note_text,
        qc_summary_confirmed=qc_confirmed,
        created_at=created_at,
    )
    db.add(note)
    return note


# =============================================================================
# Case Creation with Full Workflow
# =============================================================================

def create_todo_case(db: Session, case: Case, created_at: datetime):
    """TODO case - Pre-QC only, no assignment, no Auto-QC."""
    case.status = CaseStatus.TODO
    case.assigned_user_id = None


def create_assigned_case(db: Session, case: Case, worker: User, admin: User, created_at: datetime):
    """ASSIGNED case - TODO + assigned, no work started."""
    case.status = CaseStatus.TODO
    case.assigned_user_id = worker.id

    assign_time = add_hours(created_at, random.randint(1, 24))
    create_event(db, case, admin, EventType.ASSIGN, assign_time,
                 payload={"assigned_to": worker.username})


def create_in_progress_case(
    db: Session, case: Case, worker: User, admin: User, created_at: datetime,
    with_pause: bool = False
):
    """IN_PROGRESS case - work started, not submitted."""
    case.status = CaseStatus.IN_PROGRESS
    case.assigned_user_id = worker.id

    assign_time = add_hours(created_at, random.randint(1, 12))
    start_time = add_hours(assign_time, random.randint(1, 24))

    case.started_at = start_time

    create_event(db, case, admin, EventType.ASSIGN, assign_time,
                 payload={"assigned_to": worker.username})
    create_event(db, case, worker, EventType.STARTED, start_time)
    create_worklog(db, case, worker, ActionType.START, start_time)

    if with_pause:
        pause_time = add_hours(start_time, random.randint(1, 4))
        create_worklog(db, case, worker, ActionType.PAUSE, pause_time,
                      reason_code=random.choice(["BREAK", "MEETING", "OTHER"]))
        resume_time = add_hours(pause_time, random.randint(1, 3))
        create_worklog(db, case, worker, ActionType.RESUME, resume_time)


def create_submitted_case(
    db: Session, case: Case, worker: User, admin: User, created_at: datetime,
    autoqc_status: str, with_worker_fixes: bool = False
):
    """SUBMITTED case - submitted, waiting for review."""
    case.status = CaseStatus.SUBMITTED
    case.assigned_user_id = worker.id

    assign_time = add_hours(created_at, random.randint(1, 12))
    start_time = add_hours(assign_time, random.randint(1, 24))
    submit_time = add_hours(start_time, random.randint(2, 48))

    case.started_at = start_time
    case.worker_completed_at = submit_time

    create_event(db, case, admin, EventType.ASSIGN, assign_time,
                 payload={"assigned_to": worker.username})
    create_event(db, case, worker, EventType.STARTED, start_time)
    create_worklog(db, case, worker, ActionType.START, start_time)
    create_worklog(db, case, worker, ActionType.SUBMIT, submit_time)
    create_event(db, case, worker, EventType.SUBMITTED, submit_time)

    # Auto-QC
    create_autoqc(db, case, autoqc_status)

    # Worker fixes
    if with_worker_fixes:
        qc_fixes = [
            {"issue_id": 0, "segment": "IVC", "code": "SEGMENT_NAME_MISMATCH", "fixed": True},
        ]
        create_worker_feedback(db, case, worker, qc_fixes=qc_fixes, memo="수정 완료")


def create_rework_case(
    db: Session, case: Case, worker: User, admin: User, reviewer: User,
    created_at: datetime, autoqc_status: str
):
    """REWORK case - rejected by reviewer, needs rework."""
    case.status = CaseStatus.REWORK
    case.assigned_user_id = worker.id
    case.revision = 2

    assign_time = add_hours(created_at, random.randint(1, 12))
    start_time = add_hours(assign_time, random.randint(1, 24))
    submit_time = add_hours(start_time, random.randint(2, 48))
    reject_time = add_hours(submit_time, random.randint(4, 24))

    case.started_at = start_time
    case.worker_completed_at = submit_time

    create_event(db, case, admin, EventType.ASSIGN, assign_time,
                 payload={"assigned_to": worker.username})
    create_event(db, case, worker, EventType.STARTED, start_time)
    create_worklog(db, case, worker, ActionType.START, start_time)
    create_worklog(db, case, worker, ActionType.SUBMIT, submit_time)
    create_event(db, case, worker, EventType.SUBMITTED, submit_time)
    create_event(db, case, reviewer, EventType.REJECT, reject_time,
                 payload={"reason": "세그먼트 누락"})

    create_autoqc(db, case, autoqc_status)
    create_review_note(db, case, reviewer, "세그먼트 일부 누락됨. 재작업 필요.", reject_time)


def create_completed_case(
    db: Session, case: Case, worker: User, admin: User, reviewer: User,
    created_at: datetime, autoqc_status: str, rework_count: int = 0,
    disagreement_type: Optional[str] = None,
    with_worker_additional_fixes: bool = False,
    additional_fix_type: Optional[str] = None,
    with_worker_qc_check: bool = False,
    reviewer_checked: bool = True,
):
    """COMPLETED (ACCEPTED) case with optional rework history."""
    case.status = CaseStatus.ACCEPTED
    case.assigned_user_id = worker.id
    case.revision = rework_count + 1

    assign_time = add_hours(created_at, random.randint(1, 12))
    current_time = assign_time

    create_event(db, case, admin, EventType.ASSIGN, assign_time,
                 payload={"assigned_to": worker.username})

    # Rework loops
    for i in range(rework_count + 1):
        start_time = add_hours(current_time, random.randint(1, 12))
        work_duration = random.randint(2, 24)
        submit_time = add_hours(start_time, work_duration)

        if i == 0:
            case.started_at = start_time
            create_event(db, case, worker, EventType.STARTED, start_time)
            create_worklog(db, case, worker, ActionType.START, start_time)
        else:
            create_worklog(db, case, worker, ActionType.REWORK_START, start_time)

        create_worklog(db, case, worker, ActionType.SUBMIT, submit_time)
        create_event(db, case, worker, EventType.SUBMITTED, submit_time)

        if i < rework_count:
            # Reject
            reject_time = add_hours(submit_time, random.randint(4, 24))
            create_event(db, case, reviewer, EventType.REJECT, reject_time,
                        payload={"reason": f"재작업 필요 ({i+1}차)"})
            create_review_note(db, case, reviewer, f"수정 필요 사항 발견 ({i+1}차 검수)", reject_time)
            current_time = reject_time
        else:
            # Accept
            accept_time = add_hours(submit_time, random.randint(2, 12))
            create_event(db, case, reviewer, EventType.ACCEPTED, accept_time)
            create_review_note(db, case, reviewer, "검수 완료. 승인합니다.", accept_time, qc_confirmed=True)
            case.worker_completed_at = submit_time
            case.accepted_at = accept_time

    # Auto-QC
    create_autoqc(db, case, autoqc_status)

    # Worker feedback - combine qc_fixes and additional_fixes in one call
    qc_fixes = None
    additional_fixes = None
    memo = None

    if with_worker_qc_check:
        qc_fixes = [
            {"issue_id": 0, "segment": "IVC", "code": "SEGMENT_NAME_MISMATCH", "fixed": True},
            {"issue_id": 1, "segment": "Aorta", "code": "CONTACT", "fixed": True},
        ]
        memo = "이슈 수정 완료"

    if with_worker_additional_fixes and additional_fix_type:
        additional_fixes = [
            {"segment": "Hepatic_vein", "description": "구멍 메움", "fix_type": additional_fix_type},
        ]

    # Create single worker feedback with combined data
    if qc_fixes or additional_fixes:
        create_worker_feedback(
            db, case, worker,
            qc_fixes=qc_fixes,
            additional_fixes=additional_fixes,
            memo=memo
        )

    # Reviewer disagreement
    if disagreement_type:
        detail = "Auto-QC가 놓친 문제 발견" if disagreement_type == "MISSED" else "경고가 잘못됨, 실제 문제 없음"
        create_reviewer_feedback(
            db, case, reviewer,
            has_disagreement=True,
            disagreement_type=disagreement_type,
            disagreement_detail=detail,
            segments=["IVC", "Aorta"] if disagreement_type == "MISSED" else ["Portal_vein"],
            review_memo=detail,
        )
    elif not reviewer_checked and with_worker_qc_check:
        # Worker checked but reviewer didn't confirm -> rework
        pass  # Already handled in rework scenario


# =============================================================================
# Main Seed Function
# =============================================================================

def seed_demo_data(db: Session, num_cases: int = 50) -> dict:
    """
    Generate demo data with realistic distribution.
    """
    random.seed(RANDOM_SEED)

    print("\n" + "=" * 70)
    print("DEMO DATA SEED - Generating realistic test data")
    print("=" * 70)

    # 1. Master data
    print("\n[1/4] Creating master data...")
    master = seed_master_data(db)

    workers = [master["users"]["worker1"], master["users"]["worker2"],
               master["users"]["worker3"], master["users"]["worker4"]]
    admins = [master["users"]["admin1"], master["users"]["admin2"]]
    reviewers = admins  # Admins act as reviewers

    projects = list(master["projects"].values())
    parts = list(master["parts"].values())

    # 2. Calculate date range (last 3 months)
    now = datetime.now(TIMEZONE)
    start_range = now - timedelta(days=MONTHS_BACK * 30)

    # 3. Prepare case distribution
    # 실제 매핑: TODO=5, ASSIGNED=5(TODO+assigned), IN_PROGRESS=5, SUBMITTED=5(+IN_REVIEW=5), REWORK=5, ACCEPTED=20
    case_configs = []

    # Difficulty distribution
    difficulties = []
    for diff, count in DIFFICULTY_WEIGHTS.items():
        difficulties.extend([diff] * count)
    random.shuffle(difficulties)

    # Worker assignment distribution
    worker_assignments = []
    for worker_name, count in WORKER_DISTRIBUTION.items():
        worker_assignments.extend([master["users"][worker_name]] * count)
    random.shuffle(worker_assignments)

    # Auto-QC status distribution (for cases that have Auto-QC)
    # Total cases with Auto-QC: SUBMITTED(5) + IN_REVIEW(5) + REWORK(5) + COMPLETED(20) = 35
    autoqc_cases_count = 35
    autoqc_statuses = []
    for status, weight in AUTOQC_STATUS_WEIGHTS.items():
        count = int(autoqc_cases_count * weight / 100)
        autoqc_statuses.extend([status] * count)
    while len(autoqc_statuses) < autoqc_cases_count:
        autoqc_statuses.append("PASS")
    random.shuffle(autoqc_statuses)
    autoqc_idx = 0

    # Build case configurations
    case_idx = 0

    # TODO (5) - no assignment, no Auto-QC
    for _ in range(5):
        case_configs.append({
            "type": "TODO",
            "difficulty": difficulties[case_idx],
            "worker": None,
        })
        case_idx += 1

    # ASSIGNED (5) - assigned but not started, no Auto-QC
    for i in range(5):
        case_configs.append({
            "type": "ASSIGNED",
            "difficulty": difficulties[case_idx],
            "worker": worker_assignments[case_idx - 5],  # Use assignments after TODO
        })
        case_idx += 1

    # IN_PROGRESS (5) - started, not submitted, no Auto-QC
    # Include 2 with pause records
    for i in range(5):
        case_configs.append({
            "type": "IN_PROGRESS",
            "difficulty": difficulties[case_idx],
            "worker": worker_assignments[case_idx - 5],
            "with_pause": i < 2,
        })
        case_idx += 1

    # SUBMITTED (5) - submitted, waiting review, has Auto-QC
    for i in range(5):
        case_configs.append({
            "type": "SUBMITTED",
            "difficulty": difficulties[case_idx],
            "worker": worker_assignments[case_idx - 5],
            "autoqc_status": autoqc_statuses[autoqc_idx],
            "with_worker_fixes": i < 2,
        })
        autoqc_idx += 1
        case_idx += 1

    # IN_REVIEW (5) - same as SUBMITTED in our model, has Auto-QC
    for i in range(5):
        case_configs.append({
            "type": "SUBMITTED",  # Same status
            "difficulty": difficulties[case_idx],
            "worker": worker_assignments[case_idx - 5],
            "autoqc_status": autoqc_statuses[autoqc_idx],
            "with_worker_fixes": i < 1,
        })
        autoqc_idx += 1
        case_idx += 1

    # REWORK (5) - rejected, needs rework, has Auto-QC
    for i in range(5):
        case_configs.append({
            "type": "REWORK",
            "difficulty": difficulties[case_idx],
            "worker": worker_assignments[case_idx - 5],
            "autoqc_status": autoqc_statuses[autoqc_idx],
        })
        autoqc_idx += 1
        case_idx += 1

    # COMPLETED/ACCEPTED (20)
    # - 12 first pass
    # - 5 with 1 rework
    # - 2 with 2 reworks
    # - 1 with 3+ reworks
    completed_configs = []

    # 12 first pass
    for i in range(12):
        completed_configs.append({"rework_count": 0})
    # 5 with 1 rework
    for i in range(5):
        completed_configs.append({"rework_count": 1})
    # 2 with 2 reworks
    for i in range(2):
        completed_configs.append({"rework_count": 2})
    # 1 with 3 reworks
    completed_configs.append({"rework_count": 3})

    random.shuffle(completed_configs)

    # QC disagreement scenarios (within COMPLETED)
    # - 3 MISSED (Auto-QC PASS but reviewer found issue)
    # - 2 FALSE_ALARM (Auto-QC WARN but reviewer says OK)
    disagreement_configs = ["MISSED"] * 3 + ["FALSE_ALARM"] * 2 + [None] * 15
    random.shuffle(disagreement_configs)

    # Worker additional fixes (5 cases)
    # - 3 missed type, 2 false_alarm type
    additional_fix_configs = ["missed"] * 3 + ["false_alarm"] * 2 + [None] * 15
    random.shuffle(additional_fix_configs)

    # Worker QC check scenarios (8 cases)
    # - 6 reviewer checked and approved
    # - 2 reviewer didn't check, requested rework (these go to REWORK cases, not COMPLETED)
    worker_check_configs = [True] * 8 + [False] * 12
    random.shuffle(worker_check_configs)

    for i in range(20):
        # Force some Auto-QC statuses for disagreement scenarios
        aq_status = autoqc_statuses[autoqc_idx]
        disagreement = disagreement_configs[i]

        if disagreement == "MISSED":
            aq_status = "PASS"  # Must be PASS for MISSED disagreement
        elif disagreement == "FALSE_ALARM":
            aq_status = "WARN"  # Must be WARN for FALSE_ALARM disagreement

        case_configs.append({
            "type": "COMPLETED",
            "difficulty": difficulties[case_idx],
            "worker": worker_assignments[case_idx - 5] if case_idx - 5 < len(worker_assignments) else random.choice(workers),
            "autoqc_status": aq_status,
            "rework_count": completed_configs[i]["rework_count"],
            "disagreement_type": disagreement,
            "with_worker_additional_fixes": additional_fix_configs[i] is not None,
            "additional_fix_type": additional_fix_configs[i],
            "with_worker_qc_check": worker_check_configs[i],
        })
        autoqc_idx += 1
        case_idx += 1

    # 4. Create cases
    print(f"\n[2/4] Creating {num_cases} cases...")

    stats = {
        "status": {"TODO": 0, "ASSIGNED": 0, "IN_PROGRESS": 0, "SUBMITTED": 0, "REWORK": 0, "ACCEPTED": 0},
        "difficulty": {"EASY": 0, "NORMAL": 0, "HARD": 0},
        "autoqc": {"PASS": 0, "WARN": 0, "INCOMPLETE": 0, "NONE": 0},
        "workers": {"worker1": 0, "worker2": 0, "worker3": 0, "worker4": 0, "unassigned": 0},
        "rework_distribution": {0: 0, 1: 0, 2: 0, "3+": 0},
        "disagreements": {"MISSED": 0, "FALSE_ALARM": 0},
        "additional_fixes": {"missed": 0, "false_alarm": 0},
        "worker_qc_check": 0,
        "pause_records": 0,
        "memos": 0,
    }

    # Distribute cases across months
    cases_per_month = num_cases // MONTHS_BACK

    for idx, config in enumerate(case_configs[:num_cases]):
        # Determine creation time (spread across months)
        month_offset = idx % MONTHS_BACK
        month_start = now - timedelta(days=(MONTHS_BACK - month_offset) * 30)
        month_end = month_start + timedelta(days=29)
        created_at = random_datetime_in_range(month_start, month_end)

        # Create case
        project = random.choice(projects)
        part = random.choice(parts)
        hospital = random.choice(HOSPITALS)
        difficulty = config["difficulty"]

        case = Case(
            case_uid=f"DEMO-{idx+1:03d}",
            display_name=f"Patient {idx+1} - {part.name}",
            original_name=f"patient_{idx+1}_{part.name.lower()}_{created_at.strftime('%Y%m%d')}",
            hospital=hospital,
            slice_thickness_mm=random.choice([0.5, 1.0, 1.5, 2.0]),
            project_id=project.id,
            part_id=part.id,
            difficulty=difficulty,
            status=CaseStatus.TODO,  # Will be updated
            revision=1,
            created_at=created_at,
        )
        db.add(case)
        db.flush()

        # Pre-QC (always)
        create_preqc(db, case, difficulty)

        # Process by type
        admin = random.choice(admins)
        reviewer = random.choice(reviewers)
        worker = config.get("worker")

        if config["type"] == "TODO":
            create_todo_case(db, case, created_at)
            stats["status"]["TODO"] += 1
            stats["autoqc"]["NONE"] += 1
            stats["workers"]["unassigned"] += 1

        elif config["type"] == "ASSIGNED":
            create_assigned_case(db, case, worker, admin, created_at)
            stats["status"]["TODO"] += 1  # ASSIGNED is TODO + assigned
            stats["autoqc"]["NONE"] += 1
            stats["workers"][worker.username] += 1

        elif config["type"] == "IN_PROGRESS":
            with_pause = config.get("with_pause", False)
            create_in_progress_case(db, case, worker, admin, created_at, with_pause=with_pause)
            stats["status"]["IN_PROGRESS"] += 1
            stats["autoqc"]["NONE"] += 1
            stats["workers"][worker.username] += 1
            if with_pause:
                stats["pause_records"] += 1

        elif config["type"] == "SUBMITTED":
            autoqc_status = config["autoqc_status"]
            with_fixes = config.get("with_worker_fixes", False)
            create_submitted_case(db, case, worker, admin, created_at, autoqc_status, with_fixes)
            stats["status"]["SUBMITTED"] += 1
            stats["autoqc"][autoqc_status] += 1
            stats["workers"][worker.username] += 1

        elif config["type"] == "REWORK":
            autoqc_status = config["autoqc_status"]
            create_rework_case(db, case, worker, admin, reviewer, created_at, autoqc_status)
            stats["status"]["REWORK"] += 1
            stats["autoqc"][autoqc_status] += 1
            stats["workers"][worker.username] += 1

        elif config["type"] == "COMPLETED":
            autoqc_status = config["autoqc_status"]
            rework_count = config.get("rework_count", 0)
            disagreement = config.get("disagreement_type")
            with_additional = config.get("with_worker_additional_fixes", False)
            additional_type = config.get("additional_fix_type")
            with_qc_check = config.get("with_worker_qc_check", False)

            create_completed_case(
                db, case, worker, admin, reviewer, created_at, autoqc_status,
                rework_count=rework_count,
                disagreement_type=disagreement,
                with_worker_additional_fixes=with_additional,
                additional_fix_type=additional_type,
                with_worker_qc_check=with_qc_check,
            )
            stats["status"]["ACCEPTED"] += 1
            stats["autoqc"][autoqc_status] += 1
            stats["workers"][worker.username] += 1

            if rework_count == 0:
                stats["rework_distribution"][0] += 1
            elif rework_count == 1:
                stats["rework_distribution"][1] += 1
            elif rework_count == 2:
                stats["rework_distribution"][2] += 1
            else:
                stats["rework_distribution"]["3+"] += 1

            if disagreement:
                stats["disagreements"][disagreement] += 1

            if with_additional and additional_type:
                stats["additional_fixes"][additional_type] += 1

            if with_qc_check:
                stats["worker_qc_check"] += 1

        stats["difficulty"][difficulty.value] += 1

        # Add memo to some cases (10 total)
        if idx < 10 and config["type"] in ["SUBMITTED", "COMPLETED", "REWORK"]:
            case.memo = f"작업 메모 #{idx+1}: 특이사항 기록"
            stats["memos"] += 1

    db.commit()

    # 5. Print summary
    print("\n[3/4] Generation complete!")
    print("\n" + "=" * 70)
    print("DISTRIBUTION SUMMARY")
    print("=" * 70)

    print("\n[Case Status Distribution]")
    print(f"  TODO (incl. ASSIGNED): {stats['status']['TODO']}")
    print(f"  IN_PROGRESS:           {stats['status']['IN_PROGRESS']}")
    print(f"  SUBMITTED:             {stats['status']['SUBMITTED']}")
    print(f"  REWORK:                {stats['status']['REWORK']}")
    print(f"  ACCEPTED (COMPLETED):  {stats['status']['ACCEPTED']}")

    print("\n[Difficulty Distribution]")
    for diff, count in stats["difficulty"].items():
        pct = count / num_cases * 100
        print(f"  {diff}: {count} ({pct:.0f}%)")

    print("\n[Auto-QC Status Distribution] (cases with Auto-QC)")
    autoqc_total = sum(v for k, v in stats["autoqc"].items() if k != "NONE")
    for status in ["PASS", "WARN", "INCOMPLETE"]:
        count = stats["autoqc"][status]
        pct = count / autoqc_total * 100 if autoqc_total > 0 else 0
        print(f"  {status}: {count} ({pct:.0f}%)")
    print(f"  (No Auto-QC: {stats['autoqc']['NONE']})")

    print("\n[Worker Distribution]")
    for worker, count in stats["workers"].items():
        print(f"  {worker}: {count}")

    print("\n[Rework Distribution] (COMPLETED cases)")
    print(f"  1차 통과: {stats['rework_distribution'][0]}")
    print(f"  1회 재작업: {stats['rework_distribution'][1]}")
    print(f"  2회 재작업: {stats['rework_distribution'][2]}")
    print(f"  3회+ 재작업: {stats['rework_distribution']['3+']}")

    print("\n[QC Disagreement Scenarios]")
    print(f"  MISSED (놓친 문제): {stats['disagreements']['MISSED']}")
    print(f"  FALSE_ALARM (잘못된 경고): {stats['disagreements']['FALSE_ALARM']}")

    print("\n[Additional Scenarios]")
    print(f"  작업자 추가 수정 (missed): {stats['additional_fixes']['missed']}")
    print(f"  작업자 추가 수정 (false_alarm): {stats['additional_fixes']['false_alarm']}")
    print(f"  작업자 QC 체크: {stats['worker_qc_check']}")
    print(f"  일시중지 기록: {stats['pause_records']}")
    print(f"  메모 포함: {stats['memos']}")

    print("\n" + "=" * 70)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Generate demo data for QC Management System")
    parser.add_argument("--n", type=int, default=50, help="Number of cases to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    global RANDOM_SEED
    RANDOM_SEED = args.seed

    print("Initializing database...")
    init_db()

    db = SessionLocal()
    try:
        # Check if demo data already exists
        existing = db.query(Case).filter(Case.case_uid.like("DEMO-%")).first()
        if existing:
            print("\nDemo data already exists. Delete data/app.db first for fresh seed.")
            print("  > del data\\app.db")
            print("  > python seed_demo.py")
            return

        seed_demo_data(db, num_cases=args.n)

        print("\n[4/4] Verification...")
        print("  Run: python -m pytest tests/ -q")
        print("  Then: streamlit run dashboard.py")

    finally:
        db.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
