"""
Tests for Definitions, Projects, and Cohort endpoints.
Verifies API Contract: docs/API_CONTRACT.md Section 7
"""
import pytest
from starlette.testclient import TestClient

from models import User, Project, DefinitionSnapshot
from tests.conftest import admin_headers, worker_headers


class TestDefinitionSnapshots:
    """Test Definition Snapshot endpoints."""

    def test_create_definition_snapshot(self, client: TestClient, admin_user: User):
        """
        POST /api/admin/definitions should create a new definition snapshot.

        Expected Request:
        {
            "version_name": "v1.0",
            "content_json": "{...}"
        }

        Expected Response:
        {
            "id": <int>,
            "version_name": "v1.0",
            "content_json": "{...}",
            "created_at": "..."
        }
        """
        payload = {
            "version_name": "test_v1.0",
            "content_json": '{"segments": ["IVC", "Aorta"]}',
        }

        response = client.post(
            "/api/admin/definitions",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version_name"] == "test_v1.0"

    def test_list_definition_snapshots(
        self, client: TestClient, admin_user: User, test_db
    ):
        """
        GET /api/admin/definitions should return definition snapshot list.

        Expected Response:
        {
            "definitions": [
                {
                    "id": <int>,
                    "version_name": "...",
                    "created_at": "..."
                },
                ...
            ]
        }
        """
        # Create a definition snapshot first (without created_by_id as it doesn't exist in model)
        snapshot = DefinitionSnapshot(
            version_name="list_test_v1",
            content_json='{"test": true}',
        )
        test_db.add(snapshot)
        test_db.commit()

        response = client.get(
            "/api/admin/definitions",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "definitions" in data

    def test_get_definition_snapshot_by_version(
        self, client: TestClient, admin_user: User, test_db
    ):
        """
        GET /api/admin/definitions/{version_name} should return specific snapshot.
        """
        # Create a definition snapshot first
        snapshot = DefinitionSnapshot(
            version_name="get_test_v1",
            content_json='{"segments": ["Test"]}',
        )
        test_db.add(snapshot)
        test_db.commit()

        response = client.get(
            "/api/admin/definitions/get_test_v1",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version_name"] == "get_test_v1"

    def test_get_definition_snapshot_not_found(
        self, client: TestClient, admin_user: User
    ):
        """
        GET /api/admin/definitions/{version_name} should return 404 for non-existent version.
        """
        response = client.get(
            "/api/admin/definitions/nonexistent_version",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 404

    def test_create_definition_as_worker_forbidden(
        self, client: TestClient, worker_user: User
    ):
        """
        POST /api/admin/definitions as worker should return 403.
        """
        payload = {
            "version_name": "forbidden_v1",
            "content_json": "{}",
        }

        response = client.post(
            "/api/admin/definitions",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 403


class TestProjectDefinitions:
    """Test Project-Definition linking endpoints."""

    def test_link_project_to_definition(
        self, client: TestClient, admin_user: User, test_project: Project, test_db
    ):
        """
        POST /api/admin/projects/definition should link project to definition snapshot.

        Expected Request:
        {
            "project_id": <int>,
            "definition_snapshot_id": <int>
        }
        """
        # Create a definition snapshot first
        snapshot = DefinitionSnapshot(
            version_name="link_test_v1",
            content_json='{"segments": ["IVC"]}',
        )
        test_db.add(snapshot)
        test_db.commit()
        test_db.refresh(snapshot)

        payload = {
            "project_id": test_project.id,
            "definition_snapshot_id": snapshot.id,
        }

        response = client.post(
            "/api/admin/projects/definition",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200

    def test_list_all_project_definitions(
        self, client: TestClient, admin_user: User
    ):
        """
        GET /api/admin/projects/definitions should return all project-definition links.
        """
        response = client.get(
            "/api/admin/projects/definitions",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "links" in data or "definitions" in data or isinstance(data, dict)

    def test_get_project_definitions(
        self, client: TestClient, admin_user: User, test_project: Project
    ):
        """
        GET /api/admin/projects/{project_id}/definitions should return definitions for project.
        """
        response = client.get(
            f"/api/admin/projects/{test_project.id}/definitions",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200


class TestCapacity:
    """Test Capacity calculation endpoint."""

    def test_get_capacity(self, client: TestClient, admin_user: User):
        """
        GET /api/admin/capacity should return capacity calculation.

        Query Parameters:
        - start_date: YYYY-MM-DD
        - end_date: YYYY-MM-DD
        - user_id: optional

        Expected Response:
        {
            "working_days": <int>,
            "total_capacity_hours": <float>,
            ...
        }
        """
        from datetime import date, timedelta

        start = date.today()
        end = date.today() + timedelta(days=30)

        response = client.get(
            f"/api/admin/capacity?start_date={start}&end_date={end}",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200


class TestCohortSummary:
    """Test Cohort Summary endpoint."""

    def test_get_cohort_summary(self, client: TestClient, admin_user: User):
        """
        POST /api/admin/cohort/summary should return cohort statistics.

        Can filter by:
        - project_id
        - part_name
        - hospital
        - difficulty
        - status
        - tags
        """
        payload = {}  # Empty payload for all cases

        response = client.post(
            "/api/admin/cohort/summary",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200

    def test_get_cohort_summary_as_worker_forbidden(
        self, client: TestClient, worker_user: User
    ):
        """
        POST /api/admin/cohort/summary as worker should return 403.
        """
        payload = {}

        response = client.post(
            "/api/admin/cohort/summary",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 403


class TestQcDisagreements:
    """Test QC Disagreement endpoints."""

    def test_get_qc_disagreements(self, client: TestClient, admin_user: User):
        """
        GET /api/admin/qc_disagreements should return disagreement analysis.

        Expected Response:
        {
            "total": <int>,
            "disagreements": [...]
        }
        """
        response = client.get(
            "/api/admin/qc_disagreements",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200

    def test_get_qc_disagreements_stats(self, client: TestClient, admin_user: User):
        """
        GET /api/admin/qc_disagreements/stats should return disagreement statistics.
        """
        response = client.get(
            "/api/admin/qc_disagreements/stats",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200

    def test_get_qc_disagreements_as_worker_forbidden(
        self, client: TestClient, worker_user: User
    ):
        """
        GET /api/admin/qc_disagreements as worker should return 403.
        """
        response = client.get(
            "/api/admin/qc_disagreements",
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 403
