"""
Update holidays to 2026.
Removes 2024/2025 holidays and adds 2026 Korean holidays.
Run this script once to update existing database.
"""
import json

from database import SessionLocal, init_db
from models import WorkCalendar


def update_holidays():
    """Update WorkCalendar with 2026 Korean holidays only."""
    # 2026년 대한민국 공휴일
    holidays_2026 = [
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

    db = SessionLocal()
    try:
        calendar = db.query(WorkCalendar).first()

        if calendar:
            # Show current holidays
            current_holidays = json.loads(calendar.holidays_json) if calendar.holidays_json else []
            print(f"Current holidays count: {len(current_holidays)}")

            # Filter out 2024/2025, keep only 2026+
            old_count = len([h for h in current_holidays if h.startswith("2024") or h.startswith("2025")])
            print(f"Removing {old_count} holidays from 2024/2025")

            # Update with 2026 holidays only
            calendar.holidays_json = json.dumps(holidays_2026)
            db.commit()
            print(f"Updated with {len(holidays_2026)} holidays for 2026")
        else:
            # Create new calendar
            calendar = WorkCalendar(
                holidays_json=json.dumps(holidays_2026),
                timezone="Asia/Seoul",
            )
            db.add(calendar)
            db.commit()
            print(f"Created WorkCalendar with {len(holidays_2026)} holidays for 2026")

        # Verify
        calendar = db.query(WorkCalendar).first()
        final_holidays = json.loads(calendar.holidays_json)
        print(f"\nFinal holidays ({len(final_holidays)}):")
        for h in final_holidays:
            print(f"  - {h}")

    finally:
        db.close()


if __name__ == "__main__":
    print("Updating holidays to 2026...")
    init_db()
    update_holidays()
    print("\nDone!")
