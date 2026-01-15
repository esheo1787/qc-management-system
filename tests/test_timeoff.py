"""
Tests for TimeOff and Holiday endpoints.
Verifies API Contract: docs/API_CONTRACT.md Section 5
"""
import pytest
from datetime import date, timedelta
from starlette.testclient import TestClient

from models import User, UserTimeOff, TimeOffType, WorkCalendar
from tests.conftest import admin_headers, worker_headers


class TestTimeOff:
    """Test TimeOff endpoints."""

    def test_create_timeoff_as_worker(
        self, client: TestClient, worker_user: User
    ):
        """
        POST /api/timeoff should create a time-off entry.
        Workers can create for themselves.

        Expected Response:
        {
            "id": <int>,
            "user_id": <int>,
            "date": "2024-01-15",
            "type": "VACATION",
            "created_at": "..."
        }
        """
        payload = {
            "user_id": worker_user.id,
            "date": str(date.today() + timedelta(days=7)),
            "type": "VACATION",
        }

        response = client.post(
            "/api/timeoff",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == worker_user.id
        assert data["type"] == "VACATION"

    def test_create_timeoff_half_day(
        self, client: TestClient, worker_user: User
    ):
        """
        POST /api/timeoff with HALF_DAY type.
        """
        payload = {
            "user_id": worker_user.id,
            "date": str(date.today() + timedelta(days=14)),
            "type": "HALF_DAY",
        }

        response = client.post(
            "/api/timeoff",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "HALF_DAY"

    def test_get_my_timeoffs(
        self, client: TestClient, worker_user: User, test_db
    ):
        """
        GET /api/timeoff/me should return current user's time-offs.

        Expected Response:
        {
            "timeoffs": [
                {
                    "id": <int>,
                    "user_id": <int>,
                    "date": "2024-01-15",
                    "type": "VACATION"
                },
                ...
            ]
        }
        """
        # Create a timeoff entry first
        timeoff = UserTimeOff(
            user_id=worker_user.id,
            date=date.today() + timedelta(days=1),
            type=TimeOffType.VACATION,
        )
        test_db.add(timeoff)
        test_db.commit()

        response = client.get(
            "/api/timeoff/me",
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "timeoffs" in data

    def test_list_all_timeoffs_as_admin(
        self, client: TestClient, admin_user: User, worker_user: User, test_db
    ):
        """
        GET /api/admin/timeoff should return all time-offs.
        """
        # Create timeoff entries
        timeoff = UserTimeOff(
            user_id=worker_user.id,
            date=date.today() + timedelta(days=2),
            type=TimeOffType.VACATION,
        )
        test_db.add(timeoff)
        test_db.commit()

        response = client.get(
            "/api/admin/timeoff",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "timeoffs" in data

    def test_get_user_timeoffs_as_admin(
        self, client: TestClient, admin_user: User, worker_user: User, test_db
    ):
        """
        GET /api/admin/timeoff/{user_id} should return specific user's time-offs.
        """
        # Create a timeoff entry first
        timeoff = UserTimeOff(
            user_id=worker_user.id,
            date=date.today() + timedelta(days=3),
            type=TimeOffType.VACATION,
        )
        test_db.add(timeoff)
        test_db.commit()

        response = client.get(
            f"/api/admin/timeoff/{worker_user.id}",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "timeoffs" in data

    def test_delete_timeoff(
        self, client: TestClient, worker_user: User, test_db
    ):
        """
        DELETE /api/timeoff/{id} should delete the entry.
        Workers can only delete their own.
        """
        # Create a timeoff entry first
        timeoff = UserTimeOff(
            user_id=worker_user.id,
            date=date.today() + timedelta(days=5),
            type=TimeOffType.VACATION,
        )
        test_db.add(timeoff)
        test_db.commit()
        test_db.refresh(timeoff)

        response = client.delete(
            f"/api/timeoff/{timeoff.id}",
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200

    def test_list_all_timeoffs_as_worker_forbidden(
        self, client: TestClient, worker_user: User
    ):
        """
        GET /api/admin/timeoff as worker should return 403.
        """
        response = client.get(
            "/api/admin/timeoff",
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 403


class TestHolidays:
    """Test Holiday endpoints."""

    def test_list_holidays(self, client: TestClient, admin_user: User, test_db):
        """
        GET /api/holidays should return holiday list.

        Expected Response:
        {
            "holidays": ["2024-01-01", "2024-05-05", ...]
        }
        """
        # Create a WorkCalendar if not exists
        calendar = test_db.query(WorkCalendar).first()
        if not calendar:
            calendar = WorkCalendar(
                holidays_json='["2024-01-01", "2024-05-05"]',
                timezone="Asia/Seoul",
            )
            test_db.add(calendar)
            test_db.commit()

        response = client.get(
            "/api/holidays",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "holidays" in data

    def test_add_holiday(self, client: TestClient, admin_user: User, test_db):
        """
        POST /api/admin/holidays/{date} should add a holiday.
        """
        # Ensure WorkCalendar exists
        calendar = test_db.query(WorkCalendar).first()
        if not calendar:
            calendar = WorkCalendar(
                holidays_json="[]",
                timezone="Asia/Seoul",
            )
            test_db.add(calendar)
            test_db.commit()

        holiday_date = date.today() + timedelta(days=30)

        response = client.post(
            f"/api/admin/holidays/{holiday_date}",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "holidays" in data

    def test_remove_holiday(self, client: TestClient, admin_user: User, test_db):
        """
        DELETE /api/admin/holidays/{date} should remove the holiday.
        """
        # Create a WorkCalendar with a holiday
        holiday_date = date.today() + timedelta(days=60)
        calendar = test_db.query(WorkCalendar).first()
        if not calendar:
            calendar = WorkCalendar(
                holidays_json=f'["{holiday_date}"]',
                timezone="Asia/Seoul",
            )
            test_db.add(calendar)
            test_db.commit()
        else:
            import json
            holidays = json.loads(calendar.holidays_json or "[]")
            holidays.append(str(holiday_date))
            calendar.holidays_json = json.dumps(holidays)
            test_db.commit()

        response = client.delete(
            f"/api/admin/holidays/{holiday_date}",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200

    def test_update_holidays(self, client: TestClient, admin_user: User, test_db):
        """
        PUT /api/admin/holidays should update the full holiday list.
        """
        # Ensure WorkCalendar exists
        calendar = test_db.query(WorkCalendar).first()
        if not calendar:
            calendar = WorkCalendar(
                holidays_json="[]",
                timezone="Asia/Seoul",
            )
            test_db.add(calendar)
            test_db.commit()

        payload = {
            "holidays": [
                str(date.today() + timedelta(days=100)),
                str(date.today() + timedelta(days=200)),
            ]
        }

        response = client.put(
            "/api/admin/holidays",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "holidays" in data

    def test_add_holiday_as_worker_forbidden(
        self, client: TestClient, worker_user: User
    ):
        """
        POST /api/admin/holidays/{date} as worker should return 403.
        """
        holiday_date = date.today() + timedelta(days=150)

        response = client.post(
            f"/api/admin/holidays/{holiday_date}",
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 403
