"""Tests for POST /auth/demo - idempotent seeding + token issue."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.auth import DEMO_CLASS_CODE


class TestDemoLogin:
    def test_returns_token_for_each_role(self, client: TestClient) -> None:
        for role in ("student", "educator", "researcher"):
            response = client.post("/auth/demo", json={"role": role})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["user"]["role"] == role
            assert body["access_token"]
            assert body["refresh_token"]

    def test_idempotent_same_user_same_email(self, client: TestClient) -> None:
        first = client.post("/auth/demo", json={"role": "student"}).json()
        second = client.post("/auth/demo", json={"role": "student"}).json()
        assert first["user"]["id"] == second["user"]["id"]
        assert first["user"]["email"] == second["user"]["email"]

    def test_seeds_shared_class_with_lesson(self, client: TestClient) -> None:
        # Educator login triggers the same seed that the student relies on.
        educator = client.post("/auth/demo", json={"role": "educator"}).json()
        classes = client.get("/classes", headers={"Authorization": f"Bearer {educator['access_token']}"})
        assert classes.status_code == 200
        demo = [c for c in classes.json() if c["enrollment_code"] == DEMO_CLASS_CODE]
        assert demo, "demo class should exist after demo login"

    def test_student_is_preenrolled(self, client: TestClient) -> None:
        student = client.post("/auth/demo", json={"role": "student"}).json()
        classes = client.get("/classes", headers={"Authorization": f"Bearer {student['access_token']}"})
        assert classes.status_code == 200
        assert any(c["enrollment_code"] == DEMO_CLASS_CODE for c in classes.json())

    def test_invalid_role_rejected(self, client: TestClient) -> None:
        response = client.post("/auth/demo", json={"role": "hacker"})
        assert response.status_code == 422
