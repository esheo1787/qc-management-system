"""
Seed data script.
Creates initial admin and worker users with API keys.
Only runs if users table is empty (first-time setup).
"""
import json
import sys

from sqlalchemy.orm import Session

from database import SessionLocal, init_db
from models import (
    AppConfig,
    AutoQcSummary,
    Case,
    CaseStatus,
    Difficulty,
    Part,
    PreQcSummary,
    Project,
    User,
    UserRole,
    WorkCalendar,
)


def seed_users(db: Session) -> bool:
    """
    Seed initial users if table is empty.
    Returns True if seeding was performed.
    """
    existing = db.query(User).first()
    if existing:
        print("Users already exist. Skipping seed.")
        return False

    # 사용자 정의: username, role, api_key
    # API 키는 내부 운영용이므로 기억하기 쉬운 형태 사용
    users_data = [
        {"username": "admin1", "role": UserRole.ADMIN, "api_key": "data_admin1"},
        {"username": "admin2", "role": UserRole.ADMIN, "api_key": "data_admin2"},
        {"username": "worker1", "role": UserRole.WORKER, "api_key": "data_worker1"},
        {"username": "worker2", "role": UserRole.WORKER, "api_key": "data_worker2"},
        {"username": "worker3", "role": UserRole.WORKER, "api_key": "data_worker3"},
        {"username": "worker4", "role": UserRole.WORKER, "api_key": "data_worker4"},
    ]

    created_users = []
    for data in users_data:
        user = User(
            username=data["username"],
            role=data["role"],
            api_key=data["api_key"],
            is_active=True,
        )
        db.add(user)
        created_users.append((data["username"], data["role"].value, data["api_key"]))

    db.commit()

    print("\n" + "=" * 60)
    print("SEED DATA CREATED - SAVE THESE API KEYS!")
    print("=" * 60)
    for username, role, api_key in created_users:
        print(f"\n{username} ({role}):")
        print(f"  API Key: {api_key}")
    print("\n" + "=" * 60 + "\n")

    return True


def seed_sample_cases(db: Session) -> bool:
    """
    Seed sample cases for testing.
    Only runs if cases table is empty.
    """
    existing = db.query(Case).first()
    if existing:
        print("Cases already exist. Skipping sample cases.")
        return False

    # Get or create project
    project = db.query(Project).filter(Project.name == "Sample Project").first()
    if not project:
        project = Project(name="Sample Project", is_active=True)
        db.add(project)
        db.flush()

    # Get or create parts
    parts_data = ["Liver", "Kidney", "Spine"]
    parts = {}
    for part_name in parts_data:
        part = db.query(Part).filter(Part.name == part_name).first()
        if not part:
            part = Part(name=part_name, is_active=True)
            db.add(part)
            db.flush()
        parts[part_name] = part

    # Get workers for assignment
    worker1 = db.query(User).filter(User.username == "worker1").first()
    worker2 = db.query(User).filter(User.username == "worker2").first()

    # Sample cases data
    cases_data = [
        {
            "case_uid": "CASE-001",
            "display_name": "Patient A - Liver CT",
            "hospital": "Seoul National Hospital",
            "slice_thickness_mm": 1.0,
            "part": "Liver",
            "difficulty": Difficulty.LOW,
            "assigned_user": worker1,
        },
        {
            "case_uid": "CASE-002",
            "display_name": "Patient B - Kidney MRI",
            "hospital": "Severance Hospital",
            "slice_thickness_mm": 2.0,
            "part": "Kidney",
            "difficulty": Difficulty.MID,
            "assigned_user": worker1,
        },
        {
            "case_uid": "CASE-003",
            "display_name": "Patient C - Spine CT",
            "hospital": "Asan Medical Center",
            "slice_thickness_mm": 1.5,
            "part": "Spine",
            "difficulty": Difficulty.HIGH,
            "assigned_user": worker2,
        },
        {
            "case_uid": "CASE-004",
            "display_name": "Patient D - Liver CT",
            "hospital": "Samsung Medical Center",
            "slice_thickness_mm": 1.0,
            "part": "Liver",
            "difficulty": Difficulty.MID,
            "assigned_user": None,  # Unassigned
        },
        {
            "case_uid": "CASE-005",
            "display_name": "Patient E - Kidney CT",
            "hospital": "Korea University Hospital",
            "slice_thickness_mm": 2.5,
            "part": "Kidney",
            "difficulty": Difficulty.LOW,
            "assigned_user": worker2,
        },
    ]

    created_cases = []
    for data in cases_data:
        case = Case(
            case_uid=data["case_uid"],
            display_name=data["display_name"],
            hospital=data["hospital"],
            slice_thickness_mm=data["slice_thickness_mm"],
            project_id=project.id,
            part_id=parts[data["part"]].id,
            difficulty=data["difficulty"],
            status=CaseStatus.TODO,
            revision=1,
            assigned_user_id=data["assigned_user"].id if data["assigned_user"] else None,
        )
        db.add(case)
        db.flush()

        # Add PreQC summary for some cases (User 요청 예시 데이터)
        if data["case_uid"] == "CASE-001":
            preqc = PreQcSummary(
                case_id=case.id,
                slice_count=512,
                flags_json=json.dumps(["vessel_discontinuity", "low_contrast"]),
                expected_segments_json=json.dumps(["aorta", "portal_vein", "hepatic_vein", "IVC"]),
            )
            db.add(preqc)
        elif data["case_uid"] == "CASE-003":
            preqc = PreQcSummary(
                case_id=case.id,
                slice_count=350,
                flags_json=json.dumps(["normal"]),
                expected_segments_json=json.dumps(["vertebra", "spinal_cord", "disc"]),
            )
            db.add(preqc)

        # Add AutoQC summary for some cases (User 요청 예시 데이터)
        if data["case_uid"] == "CASE-001":
            autoqc = AutoQcSummary(
                case_id=case.id,
                qc_pass=False,
                missing_segments_json=json.dumps(["hepatic_vein"]),
                geometry_mismatch=True,
                warnings_json=json.dumps(["fragmented_vessel_detected", "artery_vein_contact"]),
            )
            db.add(autoqc)
        elif data["case_uid"] == "CASE-002":
            autoqc = AutoQcSummary(
                case_id=case.id,
                qc_pass=True,
                missing_segments_json=None,
                geometry_mismatch=False,
                warnings_json=None,
            )
            db.add(autoqc)

        created_cases.append(data["case_uid"])

    db.commit()

    print(f"\nSample cases created: {', '.join(created_cases)}")
    return True


def seed_app_config(db: Session) -> bool:
    """
    Seed default AppConfig values.
    Only creates if key doesn't exist.
    """
    default_configs = {
        "workday_hours": 8,
        "wip_limit": 1,
        "auto_timeout_minutes": 120,
        "difficulty_weights": {"LOW": 1.0, "MID": 1.5, "HIGH": 2.0},
    }

    created = []
    for key, value in default_configs.items():
        existing = db.query(AppConfig).filter(AppConfig.key == key).first()
        if not existing:
            config = AppConfig(key=key, value_json=json.dumps(value))
            db.add(config)
            created.append(key)

    if created:
        db.commit()
        print(f"\nAppConfig created: {', '.join(created)}")
        return True
    else:
        print("AppConfig already exists. Skipping.")
        return False


def seed_work_calendar(db: Session) -> bool:
    """
    Seed default WorkCalendar with 2026 Korean holidays.
    Only creates if not exists. Does NOT update existing (preserves user changes).
    """
    # 이미 존재하면 스킵 (사용자가 수정한 공휴일 보존)
    existing = db.query(WorkCalendar).first()
    if existing:
        print("WorkCalendar already exists. Skipping seed (preserving user changes).")
        return False

    # 2026년 대한민국 공휴일
    default_holidays = [
        "2026-01-01",  # 신정
        "2026-02-16",  # 설날 연휴
        "2026-02-17",  # 설날
        "2026-02-18",  # 설날 연휴
        "2026-03-01",  # 삼일절
        "2026-03-02",  # 삼일절 대체공휴일
        "2026-05-05",  # 어린이날
        "2026-05-24",  # 부처님오신날
        "2026-05-25",  # 부처님오신날 대체공휴일
        "2026-06-03",  # 선거일
        "2026-06-06",  # 현충일
        "2026-08-15",  # 광복절
        "2026-08-17",  # 광복절 대체공휴일
        "2026-09-24",  # 추석 연휴
        "2026-09-25",  # 추석
        "2026-09-26",  # 추석 연휴
        "2026-10-03",  # 개천절
        "2026-10-05",  # 개천절 대체공휴일
        "2026-10-09",  # 한글날
        "2026-12-25",  # 성탄절
    ]

    calendar = WorkCalendar(
        holidays_json=json.dumps(default_holidays),
        timezone="Asia/Seoul",
    )
    db.add(calendar)
    db.commit()

    print(f"\nWorkCalendar created with {len(default_holidays)} holidays (2026)")
    return True


def main():
    """Main entry point."""
    print("Initializing database...")
    init_db()

    print("Seeding data...")
    db = SessionLocal()
    try:
        seed_users(db)
        seed_sample_cases(db)
        seed_app_config(db)
        seed_work_calendar(db)
    finally:
        db.close()

    print("Done!")


if __name__ == "__main__":
    main()
