"""
Tests for Health Check endpoints.
Verifies API Contract: docs/API_CONTRACT.md Section 1.1, 1.2
"""
import pytest
from starlette.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """
        GET / should return service status.

        Expected Response:
        {
            "status": "ok",
            "service": "qc-management-system"
        }
        """
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "qc-management-system"

    def test_health_endpoint(self, client: TestClient):
        """
        GET /health should return healthy status.

        Expected Response:
        {
            "status": "healthy"
        }
        """
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_root_no_auth_required(self, client: TestClient):
        """Root endpoint should not require authentication."""
        # No X-API-Key header
        response = client.get("/")
        assert response.status_code == 200

    def test_health_no_auth_required(self, client: TestClient):
        """Health endpoint should not require authentication."""
        # No X-API-Key header
        response = client.get("/health")
        assert response.status_code == 200
