"""
Tests for Case Management endpoints.
Verifies API Contract: docs/API_CONTRACT.md Section 3
"""
import pytest
from starlette.testclient import TestClient

from models import User, Case, CaseStatus
from tests.conftest import admin_headers, worker_headers


class TestBulkRegister:
    """Test POST /api/admin/cases/bulk_register endpoint."""

    def test_bulk_register_single_case(self, client: TestClient, admin_user: User):
        """
        POST /api/admin/cases/bulk_register with one case.

        Expected Response:
        {
            "created_count": 1,
            "skipped_count": 0,
            "created_case_uids": ["NEW-CASE-001"],
            "skipped_case_uids": []
        }
        """
        payload = {
            "cases": [
                {
                    "case_uid": "NEW-CASE-001",
                    "project_name": "New Project",
                    "part_name": "New Part",
                    "hospital": "New Hospital",
                    "difficulty": "NORMAL",
                }
            ]
        }

        response = client.post(
            "/api/admin/cases/bulk_register",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 1
        assert data["skipped_count"] == 0
        assert "NEW-CASE-001" in data["created_case_uids"]
        assert data["skipped_case_uids"] == []

    def test_bulk_register_multiple_cases(self, client: TestClient, admin_user: User):
        """
        POST /api/admin/cases/bulk_register with multiple cases.
        """
        payload = {
            "cases": [
                {
                    "case_uid": "MULTI-001",
                    "project_name": "Project A",
                    "part_name": "Part A",
                    "difficulty": "EASY",
                },
                {
                    "case_uid": "MULTI-002",
                    "project_name": "Project A",
                    "part_name": "Part B",
                    "difficulty": "HARD",
                },
            ]
        }

        response = client.post(
            "/api/admin/cases/bulk_register",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 2
        assert data["skipped_count"] == 0

    def test_bulk_register_duplicate_skipped(self, client: TestClient, admin_user: User, test_case: Case):
        """
        POST /api/admin/cases/bulk_register should skip existing case_uid.
        """
        payload = {
            "cases": [
                {
                    "case_uid": test_case.case_uid,  # Already exists
                    "project_name": "Any Project",
                    "part_name": "Any Part",
                }
            ]
        }

        response = client.post(
            "/api/admin/cases/bulk_register",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 0
        assert data["skipped_count"] == 1
        assert test_case.case_uid in data["skipped_case_uids"]

    def test_bulk_register_as_worker_forbidden(self, client: TestClient, worker_user: User):
        """
        POST /api/admin/cases/bulk_register as worker should return 403.
        """
        payload = {
            "cases": [
                {
                    "case_uid": "WORKER-CASE",
                    "project_name": "P",
                    "part_name": "P",
                }
            ]
        }

        response = client.post(
            "/api/admin/cases/bulk_register",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 403


class TestAssign:
    """Test POST /api/admin/assign endpoint."""

    def test_assign_case_to_worker(
        self, client: TestClient, admin_user: User, worker_user: User, test_case: Case
    ):
        """
        POST /api/admin/assign should assign case to worker.

        Expected Response:
        {
            "case_id": <int>,
            "case_uid": "TEST-CASE-001",
            "assigned_user_id": <int>,
            "assigned_username": "test_worker"
        }
        """
        payload = {
            "case_id": test_case.id,
            "user_id": worker_user.id,
        }

        response = client.post(
            "/api/admin/assign",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == test_case.id
        assert data["case_uid"] == test_case.case_uid
        assert data["assigned_user_id"] == worker_user.id
        assert data["assigned_username"] == worker_user.username

    def test_assign_nonexistent_case(self, client: TestClient, admin_user: User, worker_user: User):
        """
        POST /api/admin/assign with nonexistent case_id should return 404.
        """
        payload = {
            "case_id": 99999,
            "user_id": worker_user.id,
        }

        response = client.post(
            "/api/admin/assign",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 404


class TestListCases:
    """Test GET /api/admin/cases endpoint."""

    def test_list_cases_empty(self, client: TestClient, admin_user: User):
        """
        GET /api/admin/cases with no cases should return empty list.
        """
        response = client.get("/api/admin/cases", headers=admin_headers(admin_user))

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["cases"] == []

    def test_list_cases_with_data(self, client: TestClient, admin_user: User, test_case: Case):
        """
        GET /api/admin/cases should return case list.

        Expected Response:
        {
            "total": 1,
            "cases": [
                {
                    "id": <int>,
                    "case_uid": "TEST-CASE-001",
                    "display_name": "Test Case 1",
                    "status": "TODO",
                    ...
                }
            ]
        }
        """
        response = client.get("/api/admin/cases", headers=admin_headers(admin_user))

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["cases"]) == 1
        assert data["cases"][0]["case_uid"] == test_case.case_uid

    def test_list_cases_with_status_filter(
        self, client: TestClient, admin_user: User, test_case: Case
    ):
        """
        GET /api/admin/cases?status=TODO should filter by status.
        """
        # Should find the TODO case
        response = client.get(
            "/api/admin/cases?status=TODO",
            headers=admin_headers(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        # Should not find with different status
        response = client.get(
            "/api/admin/cases?status=IN_PROGRESS",
            headers=admin_headers(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_list_cases_pagination(self, client: TestClient, admin_user: User, test_case: Case):
        """
        GET /api/admin/cases should support limit and offset.
        """
        response = client.get(
            "/api/admin/cases?limit=10&offset=0",
            headers=admin_headers(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "cases" in data


class TestGetCase:
    """Test GET /api/admin/cases/{case_id} endpoint."""

    def test_get_case_detail(self, client: TestClient, admin_user: User, test_case: Case):
        """
        GET /api/admin/cases/{case_id} should return case detail.

        Expected Response contains:
        - id, case_uid, display_name, status, revision
        - preqc_summary (nullable)
        - events (list)
        - review_notes (list)
        """
        response = client.get(
            f"/api/admin/cases/{test_case.id}",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_case.id
        assert data["case_uid"] == test_case.case_uid
        assert data["display_name"] == test_case.display_name
        assert data["status"] == "TODO"
        assert "events" in data
        assert "review_notes" in data

    def test_get_case_not_found(self, client: TestClient, admin_user: User):
        """
        GET /api/admin/cases/{case_id} with invalid id should return 404.
        """
        response = client.get(
            "/api/admin/cases/99999",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 404


class TestGetCaseMetrics:
    """Test GET /api/admin/cases/{case_id}/metrics endpoint."""

    def test_get_case_metrics(self, client: TestClient, admin_user: User, test_case: Case):
        """
        GET /api/admin/cases/{case_id}/metrics should return case with metrics.

        Expected Response contains:
        - All fields from case detail
        - worklogs (list)
        - metrics: { work_seconds, work_duration, man_days, timeline, is_working }
        """
        response = client.get(
            f"/api/admin/cases/{test_case.id}/metrics",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_case.id
        assert "worklogs" in data
        assert "metrics" in data
        assert "work_seconds" in data["metrics"]
        assert "work_duration" in data["metrics"]
        assert "man_days" in data["metrics"]
        assert "timeline" in data["metrics"]
        assert "is_working" in data["metrics"]


class TestListUsers:
    """Test GET /api/admin/users endpoint."""

    def test_list_users(self, client: TestClient, admin_user: User, worker_user: User):
        """
        GET /api/admin/users should return user list.

        Expected Response:
        {
            "users": [
                {
                    "id": <int>,
                    "username": "...",
                    "role": "ADMIN" | "WORKER",
                    "is_active": true | false,
                    "created_at": "..."
                },
                ...
            ]
        }
        """
        response = client.get("/api/admin/users", headers=admin_headers(admin_user))

        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert len(data["users"]) >= 2  # At least admin and worker


class TestWorkerTasks:
    """Test GET /api/me/tasks endpoint."""

    def test_get_my_tasks_as_worker(
        self, client: TestClient, worker_user: User, assigned_case: Case
    ):
        """
        GET /api/me/tasks should return worker's assigned cases.
        """
        response = client.get("/api/me/tasks", headers=worker_headers(worker_user))

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "cases" in data
        # The assigned_case should be in the list
        case_uids = [c["case_uid"] for c in data["cases"]]
        assert assigned_case.case_uid in case_uids

    def test_get_my_tasks_as_admin_forbidden(self, client: TestClient, admin_user: User):
        """
        GET /api/me/tasks as admin should return 403.
        Only workers can access this endpoint.
        """
        response = client.get("/api/me/tasks", headers=admin_headers(admin_user))

        assert response.status_code == 403
        data = response.json()
        assert data["detail"] == "Only workers can access this endpoint"
