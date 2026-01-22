"""
Portfolio screenshot seed script.
Creates specific data for 4 portfolio screenshots.

Usage:
    del data\\app.db
    python seed_portfolio.py

Target Screenshots:
1. 전체 케이스 목록 (20개, 다양한 상태)
2. 케이스 상세 + QC 워크플로우
3. QC 불일치 분석 (미검출 4건 / 과검출 3건)
4. 작업 통계 대시보드 (완료율, 재작업률, 1차 통과율)
"""
import json
import random
import uuid
from datetime import datetime, timedelta
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
# Constants
# =============================================================================
RANDOM_SEED = 2026

HOSPITALS = ["서울대병원", "세브란스병원", "아산병원", "삼성병원"]
PARTS = ["Liver", "Kidney", "Abdomen", "Spine", "Chest"]
PROJECTS = ["CT Segmentation 2026", "MRI Analysis"]

PREQC_FLAGS = ["low_contrast", "vessel_discontinuity", "motion_artifact", "calcification"]

QC_ISSUES = {
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

PAUSE_REASONS = ["BREAK", "MEETING", "PHONE", "OTHER"]


def generate_key(case_id: int, event_type: str) -> str:
    return f"{case_id}_{event_type}_{uuid.uuid4().hex[:8]}"


def add_hours(dt: datetime, hours: int) -> datetime:
    return dt + timedelta(hours=hours)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    return dt + timedelta(minutes=minutes)


# =============================================================================
# Helper Functions
# =============================================================================

def create_master_data(db: Session) -> dict:
    """Create users, projects, parts, config."""
    result = {"users": {}, "projects": {}, "parts": {}}

    # Users: 2 admins + 4 workers
    users = [
        {"username": "admin1", "role": UserRole.ADMIN, "api_key": "admin1_key"},
        {"username": "admin2", "role": UserRole.ADMIN, "api_key": "admin2_key"},
        {"username": "worker1", "role": UserRole.WORKER, "api_key": "worker1_key"},
        {"username": "worker2", "role": UserRole.WORKER, "api_key": "worker2_key"},
        {"username": "worker3", "role": UserRole.WORKER, "api_key": "worker3_key"},
        {"username": "worker4", "role": UserRole.WORKER, "api_key": "worker4_key"},
    ]
    for data in users:
        user = User(**data, is_active=True)
        db.add(user)
        db.flush()
        result["users"][data["username"]] = user

    # Projects
    for name in PROJECTS:
        project = Project(name=name, is_active=True)
        db.add(project)
        db.flush()
        result["projects"][name] = project

    # Parts
    for name in PARTS:
        part = Part(name=name, is_active=True)
        db.add(part)
        db.flush()
        result["parts"][name] = part

    # AppConfig
    configs = {
        "workday_hours": 8,
        "wip_limit": 3,
        "difficulty_weights": {"EASY": 1.0, "NORMAL": 1.5, "HARD": 2.0},
    }
    for key, value in configs.items():
        db.add(AppConfig(key=key, value_json=json.dumps(value)))

    # WorkCalendar
    holidays = ["2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18"]
    db.add(WorkCalendar(holidays_json=json.dumps(holidays), timezone="Asia/Seoul"))

    db.commit()
    return result


def create_preqc(db: Session, case: Case, difficulty: Difficulty) -> PreQcSummary:
    """Create Pre-QC for a case."""
    flags = random.sample(PREQC_FLAGS, random.randint(0, 2)) if random.random() < 0.3 else []
    segments = ["Aorta", "IVC", "Portal_vein", "Hepatic_vein"]

    preqc = PreQcSummary(
        case_id=case.id,
        slice_count=random.randint(250, 500),
        slice_thickness_mm=random.choice([0.5, 1.0, 1.5]),
        slice_thickness_flag=random.choice(["OK", "OK", "WARN"]),
        noise_level=random.choice(["LOW", "MODERATE", "MODERATE"]),
        contrast_flag=random.choice(["GOOD", "GOOD", "BORDERLINE"]),
        vascular_visibility_level=random.choice(["EXCELLENT", "USABLE", "USABLE"]),
        difficulty=difficulty.value,
        flags_json=json.dumps(flags) if flags else None,
        expected_segments_json=json.dumps(segments),
    )
    db.add(preqc)
    return preqc


def create_autoqc(db: Session, case: Case, status: str) -> AutoQcSummary:
    """Create Auto-QC for a case."""
    issues = []
    if status == "WARN":
        issues = random.sample(QC_ISSUES["WARN"], random.randint(1, 2))
    elif status == "INCOMPLETE":
        issues = QC_ISSUES["INCOMPLETE"][:1]

    autoqc = AutoQcSummary(
        case_id=case.id,
        status=status,
        issues_json=json.dumps(issues) if issues else None,
        issue_count_json=json.dumps({
            "warn_level": sum(1 for i in issues if i.get("level") == "WARN"),
            "incomplete_level": sum(1 for i in issues if i.get("level") == "INCOMPLETE"),
        }) if issues else None,
        geometry_mismatch=(status == "INCOMPLETE"),
    )
    db.add(autoqc)
    return autoqc


def create_event(db: Session, case: Case, user: User, event_type: EventType,
                 created_at: datetime, payload: Optional[dict] = None) -> Event:
    event = Event(
        case_id=case.id,
        user_id=user.id,
        event_type=event_type,
        idempotency_key=generate_key(case.id, event_type.value),
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        created_at=created_at,
    )
    db.add(event)
    return event


def create_worklog(db: Session, case: Case, user: User, action_type: ActionType,
                   timestamp: datetime, reason_code: Optional[str] = None) -> WorkLog:
    worklog = WorkLog(
        case_id=case.id,
        user_id=user.id,
        action_type=action_type,
        timestamp=timestamp,
        reason_code=reason_code,
    )
    db.add(worklog)
    return worklog


def create_worker_feedback(db: Session, case: Case, user: User,
                           qc_fixes: Optional[list] = None,
                           additional_fixes: Optional[list] = None) -> WorkerQcFeedback:
    feedback = WorkerQcFeedback(
        case_id=case.id,
        user_id=user.id,
        qc_fixes_json=json.dumps(qc_fixes, ensure_ascii=False) if qc_fixes else None,
        additional_fixes_json=json.dumps(additional_fixes, ensure_ascii=False) if additional_fixes else None,
    )
    db.add(feedback)
    return feedback


def create_reviewer_feedback(db: Session, case: Case, reviewer: User,
                             disagreement_type: str, detail: str,
                             segments: list) -> ReviewerQcFeedback:
    feedback = ReviewerQcFeedback(
        case_id=case.id,
        reviewer_id=reviewer.id,
        has_disagreement=True,
        disagreement_type=disagreement_type,
        disagreement_detail=detail,
        disagreement_segments_json=json.dumps(segments, ensure_ascii=False),
    )
    db.add(feedback)
    return feedback


def create_review_note(db: Session, case: Case, reviewer: User,
                       note_text: str, created_at: datetime) -> ReviewNote:
    note = ReviewNote(
        case_id=case.id,
        reviewer_user_id=reviewer.id,
        note_text=note_text,
        qc_summary_confirmed=True,
        created_at=created_at,
    )
    db.add(note)
    return note


# =============================================================================
# Case Creation Functions
# =============================================================================

def create_todo_case(db: Session, case: Case):
    """TODO: Pre-QC only, no assignment."""
    case.status = CaseStatus.TODO
    case.assigned_user_id = None


def create_assigned_case(db: Session, case: Case, worker: User, admin: User, base_time: datetime):
    """ASSIGNED: TODO + assigned."""
    case.status = CaseStatus.TODO
    case.assigned_user_id = worker.id
    create_event(db, case, admin, EventType.ASSIGN, base_time, {"assigned_to": worker.username})


def create_in_progress_case(db: Session, case: Case, worker: User, admin: User,
                            base_time: datetime, with_pause: bool = False):
    """IN_PROGRESS: Started working."""
    case.status = CaseStatus.IN_PROGRESS
    case.assigned_user_id = worker.id

    assign_time = base_time
    start_time = add_hours(assign_time, random.randint(1, 4))
    case.started_at = start_time

    create_event(db, case, admin, EventType.ASSIGN, assign_time, {"assigned_to": worker.username})
    create_event(db, case, worker, EventType.STARTED, start_time)
    create_worklog(db, case, worker, ActionType.START, start_time)

    if with_pause:
        pause_time = add_minutes(start_time, random.randint(30, 90))
        resume_time = add_minutes(pause_time, random.randint(10, 30))
        create_worklog(db, case, worker, ActionType.PAUSE, pause_time,
                      reason_code=random.choice(PAUSE_REASONS))
        create_worklog(db, case, worker, ActionType.RESUME, resume_time)


def create_submitted_case(db: Session, case: Case, worker: User, admin: User,
                          base_time: datetime, autoqc_status: str):
    """SUBMITTED: Waiting for review."""
    case.status = CaseStatus.SUBMITTED
    case.assigned_user_id = worker.id

    assign_time = base_time
    start_time = add_hours(assign_time, 2)
    submit_time = add_hours(start_time, random.randint(2, 6))

    case.started_at = start_time
    case.worker_completed_at = submit_time

    create_event(db, case, admin, EventType.ASSIGN, assign_time, {"assigned_to": worker.username})
    create_event(db, case, worker, EventType.STARTED, start_time)
    create_worklog(db, case, worker, ActionType.START, start_time)

    # Pause/Resume
    pause_time = add_minutes(start_time, random.randint(30, 60))
    resume_time = add_minutes(pause_time, random.randint(15, 30))
    create_worklog(db, case, worker, ActionType.PAUSE, pause_time, reason_code="BREAK")
    create_worklog(db, case, worker, ActionType.RESUME, resume_time)

    create_worklog(db, case, worker, ActionType.SUBMIT, submit_time)
    create_event(db, case, worker, EventType.SUBMITTED, submit_time)

    create_autoqc(db, case, autoqc_status)


def create_rework_case(db: Session, case: Case, worker: User, admin: User,
                       reviewer: User, base_time: datetime, autoqc_status: str):
    """REWORK: Rejected, needs rework."""
    case.status = CaseStatus.REWORK
    case.assigned_user_id = worker.id
    case.revision = 2

    assign_time = base_time
    start_time = add_hours(assign_time, 2)
    submit_time = add_hours(start_time, 4)
    reject_time = add_hours(submit_time, 6)

    case.started_at = start_time
    case.worker_completed_at = submit_time

    create_event(db, case, admin, EventType.ASSIGN, assign_time, {"assigned_to": worker.username})
    create_event(db, case, worker, EventType.STARTED, start_time)
    create_worklog(db, case, worker, ActionType.START, start_time)

    # Pause/Resume
    pause_time = add_minutes(start_time, 45)
    resume_time = add_minutes(pause_time, 20)
    create_worklog(db, case, worker, ActionType.PAUSE, pause_time, reason_code="MEETING")
    create_worklog(db, case, worker, ActionType.RESUME, resume_time)

    create_worklog(db, case, worker, ActionType.SUBMIT, submit_time)
    create_event(db, case, worker, EventType.SUBMITTED, submit_time)
    create_event(db, case, reviewer, EventType.REJECT, reject_time, {"reason": "세그먼트 수정 필요"})

    create_autoqc(db, case, autoqc_status)
    create_review_note(db, case, reviewer, "IVC 세그먼트 경계 수정 필요", reject_time)


def create_completed_case(db: Session, case: Case, worker: User, admin: User,
                          reviewer: User, base_time: datetime, autoqc_status: str,
                          rework_count: int = 0,
                          disagreement_type: Optional[str] = None,
                          disagreement_segment: Optional[str] = None):
    """COMPLETED (ACCEPTED): Approved."""
    case.status = CaseStatus.ACCEPTED
    case.assigned_user_id = worker.id
    case.revision = rework_count + 1

    current_time = base_time
    create_event(db, case, admin, EventType.ASSIGN, current_time, {"assigned_to": worker.username})

    for i in range(rework_count + 1):
        start_time = add_hours(current_time, 2)
        submit_time = add_hours(start_time, random.randint(3, 6))

        if i == 0:
            case.started_at = start_time
            create_event(db, case, worker, EventType.STARTED, start_time)
            create_worklog(db, case, worker, ActionType.START, start_time)
        else:
            create_worklog(db, case, worker, ActionType.REWORK_START, start_time)

        # Pause/Resume
        pause_time = add_minutes(start_time, random.randint(30, 60))
        resume_time = add_minutes(pause_time, random.randint(10, 25))
        create_worklog(db, case, worker, ActionType.PAUSE, pause_time,
                      reason_code=random.choice(PAUSE_REASONS))
        create_worklog(db, case, worker, ActionType.RESUME, resume_time)

        create_worklog(db, case, worker, ActionType.SUBMIT, submit_time)
        create_event(db, case, worker, EventType.SUBMITTED, submit_time)

        if i < rework_count:
            reject_time = add_hours(submit_time, 4)
            create_event(db, case, reviewer, EventType.REJECT, reject_time,
                        {"reason": f"수정 필요 ({i+1}차)"})
            create_review_note(db, case, reviewer, f"재작업 요청 ({i+1}차)", reject_time)
            current_time = reject_time
        else:
            accept_time = add_hours(submit_time, 3)
            create_event(db, case, reviewer, EventType.ACCEPTED, accept_time)
            create_review_note(db, case, reviewer, "검수 완료", accept_time)
            case.worker_completed_at = submit_time
            case.accepted_at = accept_time

    create_autoqc(db, case, autoqc_status)

    # QC disagreement
    if disagreement_type and disagreement_segment:
        if disagreement_type == "MISSED":
            detail = f"Auto-QC가 {disagreement_segment} 세그먼트의 경계 오류를 놓침"
        else:
            detail = f"Auto-QC의 {disagreement_segment} 경고는 실제 문제 아님"

        create_reviewer_feedback(db, case, reviewer, disagreement_type, detail, [disagreement_segment])


# =============================================================================
# Main Seed Function
# =============================================================================

def seed_portfolio_data(db: Session):
    """Generate portfolio screenshot data."""
    random.seed(RANDOM_SEED)

    print("\n" + "=" * 60)
    print("PORTFOLIO DATA SEED")
    print("=" * 60)

    # 1. Master data
    print("\n[1/3] Creating master data...")
    master = create_master_data(db)

    workers = [master["users"][f"worker{i}"] for i in range(1, 5)]
    admin = master["users"]["admin1"]
    reviewer = master["users"]["admin2"]
    projects = list(master["projects"].values())
    parts = list(master["parts"].values())

    # 2. Create 20 cases with specific distribution
    print("\n[2/3] Creating 20 cases...")

    now = datetime.now(TIMEZONE)
    base_date = now - timedelta(days=25)  # Within last month

    # Case configurations
    # 상태 분포: TODO(2), ASSIGNED(2), IN_PROGRESS(3), SUBMITTED(3), IN_REVIEW(2), REWORK(3), COMPLETED(5)
    # Auto-QC: PASS(6), WARN(5), INCOMPLETE(2) - 총 13개 (SUBMITTED 이후 케이스)

    case_configs = [
        # TODO (2)
        {"type": "TODO", "worker_idx": None},
        {"type": "TODO", "worker_idx": None},

        # ASSIGNED (2)
        {"type": "ASSIGNED", "worker_idx": 0},
        {"type": "ASSIGNED", "worker_idx": 1},

        # IN_PROGRESS (3) - with pause records
        {"type": "IN_PROGRESS", "worker_idx": 0, "with_pause": True},
        {"type": "IN_PROGRESS", "worker_idx": 1, "with_pause": True},
        {"type": "IN_PROGRESS", "worker_idx": 2, "with_pause": False},

        # SUBMITTED (3) - Auto-QC: PASS(1), WARN(2)
        {"type": "SUBMITTED", "worker_idx": 2, "autoqc": "PASS"},
        {"type": "SUBMITTED", "worker_idx": 3, "autoqc": "WARN"},
        {"type": "SUBMITTED", "worker_idx": 0, "autoqc": "WARN"},

        # IN_REVIEW (2) - same as SUBMITTED, Auto-QC: PASS(1), INCOMPLETE(1)
        {"type": "SUBMITTED", "worker_idx": 1, "autoqc": "PASS"},
        {"type": "SUBMITTED", "worker_idx": 2, "autoqc": "INCOMPLETE"},

        # REWORK (3) - Auto-QC: WARN(2), INCOMPLETE(1)
        {"type": "REWORK", "worker_idx": 3, "autoqc": "WARN"},
        {"type": "REWORK", "worker_idx": 0, "autoqc": "WARN"},
        {"type": "REWORK", "worker_idx": 1, "autoqc": "INCOMPLETE"},

        # COMPLETED (5) - with disagreements and rework scenarios
        # 1차 통과: 3건, 1회 재작업 후 통과: 1건, 2회 재작업 후 통과: 1건
        # 미검출(MISSED): 4건, 과검출(FALSE_ALARM): 3건
        {"type": "COMPLETED", "worker_idx": 0, "autoqc": "PASS", "rework": 0,
         "disagreement": "MISSED", "segment": "IVC"},
        {"type": "COMPLETED", "worker_idx": 1, "autoqc": "PASS", "rework": 0,
         "disagreement": "MISSED", "segment": "Aorta"},
        {"type": "COMPLETED", "worker_idx": 2, "autoqc": "PASS", "rework": 1,
         "disagreement": "MISSED", "segment": "Portal_vein"},
        {"type": "COMPLETED", "worker_idx": 3, "autoqc": "WARN", "rework": 0,
         "disagreement": "FALSE_ALARM", "segment": "Hepatic_vein"},
        {"type": "COMPLETED", "worker_idx": 0, "autoqc": "WARN", "rework": 2,
         "disagreement": "FALSE_ALARM", "segment": "IVC"},
    ]

    # Additional COMPLETED cases for statistics (without disagreement)
    additional_completed = [
        {"type": "COMPLETED", "worker_idx": 1, "autoqc": "PASS", "rework": 0},
        {"type": "COMPLETED", "worker_idx": 2, "autoqc": "PASS", "rework": 0},
        {"type": "COMPLETED", "worker_idx": 3, "autoqc": "WARN", "rework": 1,
         "disagreement": "MISSED", "segment": "Renal_artery"},
        {"type": "COMPLETED", "worker_idx": 0, "autoqc": "PASS", "rework": 0,
         "disagreement": "FALSE_ALARM", "segment": "Portal_vein"},
    ]
    case_configs.extend(additional_completed)

    # Worker distribution tracking
    worker_counts = {f"worker{i}": 0 for i in range(1, 5)}

    # Create cases
    difficulties = [Difficulty.EASY, Difficulty.NORMAL, Difficulty.NORMAL, Difficulty.HARD]

    for idx, config in enumerate(case_configs):
        # Time spread across the month
        day_offset = idx % 20
        case_time = base_date + timedelta(days=day_offset, hours=random.randint(9, 17))

        # Select data
        project = projects[idx % len(projects)]
        part = parts[idx % len(parts)]
        difficulty = difficulties[idx % len(difficulties)]
        hospital = HOSPITALS[idx % len(HOSPITALS)]

        # Create case
        case = Case(
            case_uid=f"PF-{idx+1:03d}",
            display_name=f"Patient {idx+1} - {part.name}",
            original_name=f"patient_{idx+1}_{part.name.lower()}",
            hospital=hospital,
            slice_thickness_mm=random.choice([0.5, 1.0, 1.5]),
            project_id=project.id,
            part_id=part.id,
            difficulty=difficulty,
            status=CaseStatus.TODO,
            revision=1,
            created_at=case_time,
        )
        db.add(case)
        db.flush()

        # Pre-QC (always)
        create_preqc(db, case, difficulty)

        # Get worker
        worker_idx = config.get("worker_idx")
        worker = workers[worker_idx] if worker_idx is not None else None

        # Create based on type
        if config["type"] == "TODO":
            create_todo_case(db, case)

        elif config["type"] == "ASSIGNED":
            create_assigned_case(db, case, worker, admin, case_time)
            worker_counts[worker.username] += 1

        elif config["type"] == "IN_PROGRESS":
            create_in_progress_case(db, case, worker, admin, case_time,
                                   with_pause=config.get("with_pause", False))
            worker_counts[worker.username] += 1

        elif config["type"] == "SUBMITTED":
            create_submitted_case(db, case, worker, admin, case_time, config["autoqc"])
            worker_counts[worker.username] += 1

        elif config["type"] == "REWORK":
            create_rework_case(db, case, worker, admin, reviewer, case_time, config["autoqc"])
            worker_counts[worker.username] += 1

        elif config["type"] == "COMPLETED":
            create_completed_case(
                db, case, worker, admin, reviewer, case_time,
                config["autoqc"],
                rework_count=config.get("rework", 0),
                disagreement_type=config.get("disagreement"),
                disagreement_segment=config.get("segment"),
            )
            worker_counts[worker.username] += 1

    db.commit()

    # 3. Summary
    print("\n[3/3] Summary:")
    print("-" * 40)

    # Count by status
    status_counts = {}
    for status in CaseStatus:
        count = db.query(Case).filter(Case.status == status).count()
        if count > 0:
            status_counts[status.value] = count

    print("\n[Status Distribution]")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")

    # Auto-QC counts
    print("\n[Auto-QC Distribution]")
    for status in ["PASS", "WARN", "INCOMPLETE"]:
        count = db.query(AutoQcSummary).filter(AutoQcSummary.status == status).count()
        print(f"  {status}: {count}")

    # Disagreement counts
    print("\n[QC Disagreements]")
    missed = db.query(ReviewerQcFeedback).filter(
        ReviewerQcFeedback.disagreement_type == "MISSED"
    ).count()
    false_alarm = db.query(ReviewerQcFeedback).filter(
        ReviewerQcFeedback.disagreement_type == "FALSE_ALARM"
    ).count()
    print(f"  미검출 (False Negative): {missed}")
    print(f"  과검출 (False Positive): {false_alarm}")

    # Worker distribution
    print("\n[Worker Distribution]")
    for worker, count in worker_counts.items():
        print(f"  {worker}: {count}")

    # Pause records
    pause_count = db.query(WorkLog).filter(WorkLog.action_type == ActionType.PAUSE).count()
    print(f"\n[Pause Records]: {pause_count}")

    print("\n" + "=" * 60)
    print("DONE! Run: streamlit run dashboard.py")
    print("=" * 60)


def main():
    print("Initializing database...")
    init_db()

    db = SessionLocal()
    try:
        existing = db.query(Case).first()
        if existing:
            print("\nData already exists. Delete data/app.db first.")
            print("  > del data\\app.db")
            print("  > python seed_portfolio.py")
            return

        seed_portfolio_data(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
