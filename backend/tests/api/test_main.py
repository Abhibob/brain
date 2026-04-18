"""Tests for /health and basic app wiring."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealth:
    def test_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestRoutesRegistered:
    def test_auth_register_exists(self, client: TestClient) -> None:
        # missing body → 422, proving route is mounted
        response = client.post("/auth/register", json={})
        assert response.status_code == 422

    def test_openapi_lists_core_paths(self, client: TestClient) -> None:
        spec = client.get("/openapi.json").json()
        paths = set(spec["paths"].keys())
        for path in [
            "/auth/register",
            "/auth/login",
            "/auth/refresh",
            "/classes",
            "/classes/{class_id}",
            "/classes/{class_id}/enroll",
            "/classes/{class_id}/students",
            "/classes/{class_id}/analytics",
            "/classes/{class_id}/materials",
            "/materials/{material_id}",
            "/materials/{material_id}/publish",
            "/materials/{material_id}/quiz",
            "/quiz/{material_id}/submit",
            "/sessions/start",
            "/sessions/{session_id}/end",
            "/sessions/{session_id}/prediction",
            "/students/{student_id}/profile",
            "/lessons/{material_id}/personalize/{student_id}",
        ]:
            assert path in paths, f"{path} not in OpenAPI spec"
