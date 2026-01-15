"""
Tests for QC Summary and Tag endpoints.
Verifies API Contract: docs/API_CONTRACT.md Section 6
"""
import pytest
from starlette.testclient import TestClient

from models import User, Case, PreQcSummary, AutoQcSummary, CaseTag
from tests.conftest import admin_headers, worker_headers


class TestPreQcSummary:
    """Test PreQC Summary endpoints."""

    def test_save_preqc_summary(
        self, client: TestClient, worker_user: User, assigned_case: Case
    ):
        """
        POST /api/preqc_summary should save PreQC summary from local client.

        NOTE: Server does NOT run Pre-QC. It only stores the summary.
        Actual QC runs on local PC (offline-first, cost=0).

        Expected Response:
        {
            "id": <int>,
            "case_id": <int>,
            "slice_count": <int>,
            ...
        }
        """
        payload = {
            "case_id": assigned_case.id,
            "slice_count": 100,
            "slice_thickness_mm": 1.0,
            "slice_thickness_flag": "OK",
            "noise_level": "LOW",
            "contrast_flag": "GOOD",
            "vascular_visibility_level": "EXCELLENT",
        }

        response = client.post(
            "/api/preqc_summary",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == assigned_case.id

    def test_get_preqc_summary(
        self, client: TestClient, admin_user: User, assigned_case: Case, test_db
    ):
        """
        GET /api/preqc_summary/{case_id} should return PreQC summary.
        """
        # Create PreQC summary first
        preqc = PreQcSummary(
            case_id=assigned_case.id,
            slice_count=50,
            slice_thickness_mm=1.5,
        )
        test_db.add(preqc)
        test_db.commit()

        response = client.get(
            f"/api/preqc_summary/{assigned_case.id}",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == assigned_case.id

    def test_get_preqc_summary_not_found(
        self, client: TestClient, admin_user: User
    ):
        """
        GET /api/preqc_summary/{case_id} with no summary should return 404.
        """
        response = client.get(
            "/api/preqc_summary/99999",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 404


class TestAutoQcSummary:
    """Test AutoQC Summary endpoints."""

    def test_save_autoqc_summary(
        self, client: TestClient, worker_user: User, assigned_case: Case
    ):
        """
        POST /api/autoqc_summary should save AutoQC summary from local client.

        NOTE: Server does NOT run Auto-QC. It only stores the summary.
        Actual QC runs on local PC (offline-first, cost=0).

        Expected Response:
        {
            "id": <int>,
            "case_id": <int>,
            "status": "PASS" | "WARN" | "INCOMPLETE",
            ...
        }
        """
        payload = {
            "case_id": assigned_case.id,
            "status": "PASS",
            "missing_segments": [],
            "issues": [],
            "geometry_mismatch": False,
        }

        response = client.post(
            "/api/autoqc_summary",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == assigned_case.id

    def test_get_autoqc_summary(
        self, client: TestClient, admin_user: User, assigned_case: Case, test_db
    ):
        """
        GET /api/autoqc_summary/{case_id} should return AutoQC summary.
        """
        # Create AutoQC summary first
        autoqc = AutoQcSummary(
            case_id=assigned_case.id,
            status="PASS",
            geometry_mismatch=False,
        )
        test_db.add(autoqc)
        test_db.commit()

        response = client.get(
            f"/api/autoqc_summary/{assigned_case.id}",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == assigned_case.id

    def test_get_autoqc_summary_not_found(
        self, client: TestClient, admin_user: User
    ):
        """
        GET /api/autoqc_summary/{case_id} with no summary should return 404.
        """
        response = client.get(
            "/api/autoqc_summary/99999",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 404


class TestTags:
    """Test Tag (research cohort) endpoints."""

    def test_apply_tags_to_cases(
        self, client: TestClient, admin_user: User, assigned_case: Case
    ):
        """
        POST /api/admin/tags/apply should apply tag to cases.

        Expected Request:
        {
            "case_uids": ["CASE-001", "CASE-002"],
            "tag_text": "research_cohort_a"
        }

        Expected Response:
        {
            "tag_text": "research_cohort_a",
            "applied_count": 2,
            "skipped_count": 0,
            "not_found_count": 0
        }
        """
        payload = {
            "case_uids": [assigned_case.case_uid],
            "tag_text": "test_cohort",
        }

        response = client.post(
            "/api/admin/tags/apply",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tag_text"] == "test_cohort"
        assert data["applied_count"] >= 0

    def test_list_all_tags(
        self, client: TestClient, admin_user: User, assigned_case: Case, test_db
    ):
        """
        GET /api/admin/tags should return all unique tags.

        Expected Response:
        {
            "tags": ["tag_a", "tag_b", ...]
        }
        """
        # Create some tags first
        tag1 = CaseTag(case_id=assigned_case.id, tag_text="unique_tag_1")
        tag2 = CaseTag(case_id=assigned_case.id, tag_text="unique_tag_2")
        test_db.add_all([tag1, tag2])
        test_db.commit()

        response = client.get(
            "/api/admin/tags",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert "tags" in data

    def test_get_cases_by_tag(
        self, client: TestClient, admin_user: User, assigned_case: Case, test_db
    ):
        """
        GET /api/admin/tags/{tag_text}/cases should return cases with tag.

        Expected Response:
        {
            "tag_text": "...",
            "total": <int>,
            "cases": [...]
        }
        """
        # Create a tag first
        tag = CaseTag(case_id=assigned_case.id, tag_text="cohort_alpha")
        test_db.add(tag)
        test_db.commit()

        response = client.get(
            "/api/admin/tags/cohort_alpha/cases",
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tag_text"] == "cohort_alpha"
        assert "cases" in data

    def test_remove_tags_from_cases(
        self, client: TestClient, admin_user: User, assigned_case: Case, test_db
    ):
        """
        POST /api/admin/tags/remove should remove tag from cases.

        Expected Response:
        {
            "tag_text": "...",
            "removed_count": <int>
        }
        """
        # Create a tag first
        tag = CaseTag(case_id=assigned_case.id, tag_text="tag_to_remove")
        test_db.add(tag)
        test_db.commit()

        payload = {
            "case_uids": [assigned_case.case_uid],
            "tag_text": "tag_to_remove",
        }

        response = client.post(
            "/api/admin/tags/remove",
            json=payload,
            headers=admin_headers(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tag_text"] == "tag_to_remove"

    def test_apply_tags_as_worker_forbidden(
        self, client: TestClient, worker_user: User, assigned_case: Case
    ):
        """
        POST /api/admin/tags/apply as worker should return 403.
        """
        payload = {
            "case_uids": [assigned_case.case_uid],
            "tag_text": "forbidden_tag",
        }

        response = client.post(
            "/api/admin/tags/apply",
            json=payload,
            headers=worker_headers(worker_user),
        )

        assert response.status_code == 403
