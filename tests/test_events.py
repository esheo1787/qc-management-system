"""
Tests for Event and WorkLog endpoints.
Verifies API Contract: docs/API_CONTRACT.md Section 4
"""
import pytest
import uuid
from datetime import datetime
from starlette.testclient import TestClient

from models import User, Case, CaseStatus, Event, EventType, WorkLog, ActionType
from tests.conftest import admin_headers, worker_headers


class TestCreateEvent:
    """Test POST /api/events endpoint."""

    def test_create_started_event(
        self, client: TestClient, worker_user: User, assigned_case: Case, test_db
    ):
        """
        POST /api/events with STARTED should create event and change case status.
        Worker must be assigned to the case.

        Expected Response:
        {
            "id": <int>,
            "case_id": <int>,
            "event_type": "STARTED",
            ...
        }
        """
        # assigned_case is already assigned to worker_user and is IN_PROGRESS
        # Need to set it to TODO first for STARTED transition
        assigned_case.status = CaseStatus.TODO
        test_db.commit()
        test_db.refresh(assigned_case)

        idempotency_key = str(uuid.uuid4())
        payload = {
            "case_id": assigned_case.id,
            "event_type": "STARTED",
            "idempotency_key": idempotency_key,
            "expected_revision": assigned_case.revision,
        }

        response = client.post(
            "/api/events",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == assigned_case.id
        assert data["event_type"] == "STARTED"
        assert "id" in data
        assert "created_at" in data

    def test_create_event_idempotency(
        self, client: TestClient, worker_user: User, assigned_case: Case, test_db
    ):
        """
        POST /api/events with same idempotency_key should return existing event.
        """
        # Set case to TODO for STARTED transition
        assigned_case.status = CaseStatus.TODO
        test_db.commit()
        test_db.refresh(assigned_case)

        idempotency_key = str(uuid.uuid4())
        payload = {
            "case_id": assigned_case.id,
            "event_type": "STARTED",
            "idempotency_key": idempotency_key,
            "expected_revision": assigned_case.revision,
        }

        # First request
        response1 = client.post(
            "/api/events",
            json=payload,
            headers=worker_headers(worker_user),
        )
        assert response1.status_code == 200
        event_id_1 = response1.json()["id"]

        # Second request with same idempotency_key
        response2 = client.post(
            "/api/events",
            json=payload,
            headers=worker_headers(worker_user),
        )
        assert response2.status_code == 200
        event_id_2 = response2.json()["id"]

        # Should return same event
        assert event_id_1 == event_id_2

    def test_create_event_revision_conflict(
        self, client: TestClient, worker_user: User, assigned_case: Case, test_db
    ):
        """
        POST /api/events with wrong revision should return 409.

        Expected Response:
        {
            "detail": "Conflict: revision mismatch"
        }
        """
        # Set case to TODO for STARTED transition
        assigned_case.status = CaseStatus.TODO
        test_db.commit()
        test_db.refresh(assigned_case)

        payload = {
            "case_id": assigned_case.id,
            "event_type": "STARTED",
            "idempotency_key": str(uuid.uuid4()),
            "expected_revision": assigned_case.revision + 100,  # Wrong revision
        }

        response = client.post(
            "/api/events",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 409
        data = response.json()
        assert "detail" in data

    def test_create_event_case_not_found(
        self, client: TestClient, worker_user: User
    ):
        """
        POST /api/events with nonexistent case_id should return 404.
        """
        payload = {
            "case_id": 99999,
            "event_type": "STARTED",
            "idempotency_key": str(uuid.uuid4()),
            "expected_revision": 1,
        }

        response = client.post(
            "/api/events",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 404

    def test_create_event_not_assigned_forbidden(
        self, client: TestClient, worker_user: User, test_case: Case
    ):
        """
        Worker cannot create STARTED event on unassigned case.
        """
        # test_case is not assigned to worker_user
        payload = {
            "case_id": test_case.id,
            "event_type": "STARTED",
            "idempotency_key": str(uuid.uuid4()),
            "expected_revision": test_case.revision,
        }

        response = client.post(
            "/api/events",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 403


class TestGetEvents:
    """Test GET /api/admin/events endpoint."""

    def test_get_recent_events(
        self, client: TestClient, admin_user: User, test_case: Case, test_db
    ):
        """
        GET /api/admin/events should return recent events.

        Expected Response:
        [
            {
                "id": <int>,
                "case_id": <int>,
                "event_type": "...",
                "created_at": "...",
                ...
            },
            ...
        ]
        """
        # Create an event first using correct field names
        event = Event(
            case_id=test_case.id,
            event_type=EventType.STARTED,
            user_id=admin_user.id,
            idempotency_key=str(uuid.uuid4()),
        )
        test_db.add(event)
        test_db.commit()

        response = client.get(
            "/api/admin/events",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestSubmitWork:
    """Test POST /api/submit endpoint."""

    def test_submit_work_success(
        self, client: TestClient, worker_user: User, test_db, assigned_case: Case
    ):
        """
        POST /api/submit should submit work and change status to SUBMITTED.

        Expected Response:
        {
            "case_id": <int>,
            "case_status": "SUBMITTED",
            ...
        }
        """
        # Case must already be IN_PROGRESS (assigned_case fixture provides this)
        # First, add a START worklog to allow SUBMIT
        worklog = WorkLog(
            case_id=assigned_case.id,
            user_id=worker_user.id,
            action_type=ActionType.START,
        )
        test_db.add(worklog)
        test_db.commit()
        test_db.refresh(assigned_case)

        payload = {
            "case_id": assigned_case.id,
            "idempotency_key": str(uuid.uuid4()),
            "expected_revision": assigned_case.revision,
        }

        response = client.post(
            "/api/submit",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == assigned_case.id
        assert data["case_status"] == "SUBMITTED"


class TestWorkLogs:
    """Test WorkLog endpoints."""

    def test_create_worklog(
        self, client: TestClient, worker_user: User, assigned_case: Case, test_db
    ):
        """
        POST /api/worklogs should create a worklog entry.

        Expected Request:
        {
            "case_id": <int>,
            "action_type": "START" | "PAUSE" | "RESUME",
            "reason_code": optional
        }
        """
        # assigned_case is IN_PROGRESS, but we need it in TODO/REWORK for START
        assigned_case.status = CaseStatus.TODO
        test_db.commit()

        payload = {
            "case_id": assigned_case.id,
            "action_type": "START",
        }

        response = client.post(
            "/api/worklogs",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == assigned_case.id
        assert data["action_type"] == "START"

    def test_create_worklog_pause(
        self, client: TestClient, worker_user: User, assigned_case: Case, test_db
    ):
        """
        POST /api/worklogs with PAUSE action.
        """
        # Set case to TODO and add a START worklog first
        assigned_case.status = CaseStatus.TODO
        test_db.commit()

        # First start
        start_payload = {
            "case_id": assigned_case.id,
            "action_type": "START",
        }
        response = client.post(
            "/api/worklogs",
            json=start_payload,
            headers=worker_headers(worker_user),
        )
        assert response.status_code == 200

        # Then pause
        pause_payload = {
            "case_id": assigned_case.id,
            "action_type": "PAUSE",
            "reason_code": "BREAK",
        }

        response = client.post(
            "/api/worklogs",
            json=pause_payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action_type"] == "PAUSE"
        assert data["reason_code"] == "BREAK"


class TestReviewActions:
    """Test review actions via Event endpoint (Accept/Rework)."""

    def test_accept_case(
        self, client: TestClient, admin_user: User, test_db, test_case: Case, worker_user: User
    ):
        """
        POST /api/events with ACCEPTED event should accept the case.
        Admin-only action.
        """
        # Set case to SUBMITTED status (required for ACCEPTED transition)
        test_case.status = CaseStatus.SUBMITTED
        test_case.assigned_user_id = worker_user.id
        test_db.commit()
        test_db.refresh(test_case)

        payload = {
            "case_id": test_case.id,
            "event_type": "ACCEPTED",
            "idempotency_key": str(uuid.uuid4()),
            "expected_revision": test_case.revision,
        }

        response = client.post(
            "/api/events",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == test_case.id
        assert data["case_status"] == "ACCEPTED"

    def test_request_rework(
        self, client: TestClient, admin_user: User, test_db, test_case: Case, worker_user: User
    ):
        """
        POST /api/events with REWORK_REQUESTED event should request rework.
        Admin-only action.
        """
        # Set case to SUBMITTED status (required for REWORK_REQUESTED transition)
        test_case.status = CaseStatus.SUBMITTED
        test_case.assigned_user_id = worker_user.id
        test_db.commit()
        test_db.refresh(test_case)

        payload = {
            "case_id": test_case.id,
            "event_type": "REWORK_REQUESTED",
            "idempotency_key": str(uuid.uuid4()),
            "expected_revision": test_case.revision,
        }

        response = client.post(
            "/api/events",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == test_case.id
        assert data["case_status"] == "REWORK"

    def test_accept_as_worker_forbidden(
        self, client: TestClient, worker_user: User, test_case: Case, test_db
    ):
        """
        POST /api/events with ACCEPTED as worker should return 403.
        """
        test_case.status = CaseStatus.SUBMITTED
        test_case.assigned_user_id = worker_user.id
        test_db.commit()

        payload = {
            "case_id": test_case.id,
            "event_type": "ACCEPTED",
            "idempotency_key": str(uuid.uuid4()),
            "expected_revision": test_case.revision,
        }

        response = client.post(
            "/api/events",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 403
