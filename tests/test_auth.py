"""
Tests for Auth endpoints.
Verifies API Contract: docs/API_CONTRACT.md Section 2
"""
import pytest
from starlette.testclient import TestClient

from models import User
from tests.conftest import admin_headers, worker_headers


class TestAuthMe:
    """Test /api/auth/me endpoint."""

    def test_get_me_as_admin(self, client: TestClient, admin_user: User):
        """
        GET /api/auth/me should return current admin user info.

        Expected Response:
        {
            "id": <int>,
            "username": "test_admin",
            "role": "ADMIN",
            "is_active": true
        }
        """
        response = client.get("/api/auth/me", headers=admin_headers(admin_user))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == admin_user.id
        assert data["username"] == "test_admin"
        assert data["role"] == "ADMIN"
        assert data["is_active"] is True

    def test_get_me_as_worker(self, client: TestClient, worker_user: User):
        """
        GET /api/auth/me should return current worker user info.

        Expected Response:
        {
            "id": <int>,
            "username": "test_worker",
            "role": "WORKER",
            "is_active": true
        }
        """
        response = client.get("/api/auth/me", headers=worker_headers(worker_user))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == worker_user.id
        assert data["username"] == "test_worker"
        assert data["role"] == "WORKER"
        assert data["is_active"] is True

    def test_get_me_without_api_key(self, client: TestClient):
        """
        GET /api/auth/me without X-API-Key should return 422 (validation error).
        """
        response = client.get("/api/auth/me")
        assert response.status_code == 422

    def test_get_me_with_invalid_api_key(self, client: TestClient):
        """
        GET /api/auth/me with invalid API key should return 401.

        Expected Response:
        {
            "detail": "Invalid or inactive API key"
        }
        """
        response = client.get("/api/auth/me", headers={"X-API-Key": "invalid_key"})

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid or inactive API key"

    def test_get_me_with_inactive_user(self, client: TestClient, inactive_user: User):
        """
        GET /api/auth/me with inactive user's API key should return 401.

        Expected Response:
        {
            "detail": "Invalid or inactive API key"
        }
        """
        response = client.get("/api/auth/me", headers={"X-API-Key": inactive_user.api_key})

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid or inactive API key"


class TestAdminAccess:
    """Test admin-only endpoint access control."""

    def test_admin_endpoint_as_admin(self, client: TestClient, admin_user: User):
        """Admin should be able to access admin endpoints."""
        response = client.get("/api/admin/users", headers=admin_headers(admin_user))
        assert response.status_code == 200

    def test_admin_endpoint_as_worker(self, client: TestClient, worker_user: User):
        """
        Worker should NOT be able to access admin endpoints.

        Expected Response:
        {
            "detail": "Admin access required"
        }
        """
        response = client.get("/api/admin/users", headers=worker_headers(worker_user))

        assert response.status_code == 403
        data = response.json()
        assert data["detail"] == "Admin access required"

    def test_admin_endpoint_without_auth(self, client: TestClient):
        """Admin endpoint without auth should return 422."""
        response = client.get("/api/admin/users")
        assert response.status_code == 422
