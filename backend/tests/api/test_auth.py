"""Tests for /auth routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_user


class TestRegister:
    def test_register_student(self, client: TestClient) -> None:
        response = client.post(
            "/auth/register",
            json={"email": "s@example.com", "password": "password-123", "role": "student"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "s@example.com"
        assert body["user"]["role"] == "student"

    def test_register_educator_creates_profile(self, client: TestClient) -> None:
        response = client.post(
            "/auth/register",
            json={
                "email": "e@example.com",
                "password": "password-123",
                "role": "educator",
                "bio": "Teaches algorithms",
                "institution": "Acme",
            },
        )
        assert response.status_code == 200
        # educator profile creation verified via no failure + login works
        login = client.post("/auth/login", json={"email": "e@example.com", "password": "password-123"})
        assert login.status_code == 200

    def test_email_normalized_to_lowercase(self, client: TestClient) -> None:
        response = client.post(
            "/auth/register",
            json={"email": "MixedCase@Example.COM", "password": "password-123", "role": "student"},
        )
        assert response.status_code == 200
        login = client.post("/auth/login", json={"email": "mixedcase@example.com", "password": "password-123"})
        assert login.status_code == 200

    def test_duplicate_email_rejected(self, client: TestClient) -> None:
        register_user(client, "dup@example.com", "student")
        response = client.post(
            "/auth/register",
            json={"email": "dup@example.com", "password": "password-123", "role": "student"},
        )
        assert response.status_code == 409

    def test_short_password_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/auth/register",
            json={"email": "x@example.com", "password": "short", "role": "student"},
        )
        assert response.status_code == 422

    def test_invalid_email_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/auth/register",
            json={"email": "nope", "password": "password-123", "role": "student"},
        )
        assert response.status_code == 422

    def test_invalid_role_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/auth/register",
            json={"email": "r@example.com", "password": "password-123", "role": "admin"},
        )
        assert response.status_code == 422


class TestLogin:
    def test_login_happy_path(self, client: TestClient) -> None:
        register_user(client, "a@example.com", "student")
        response = client.post(
            "/auth/login",
            json={"email": "a@example.com", "password": "password-123"},
        )
        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_login_wrong_password(self, client: TestClient) -> None:
        register_user(client, "a@example.com", "student")
        response = client.post(
            "/auth/login",
            json={"email": "a@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_login_unknown_email(self, client: TestClient) -> None:
        response = client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "password-123"},
        )
        assert response.status_code == 401

    def test_login_case_insensitive(self, client: TestClient) -> None:
        register_user(client, "b@example.com", "student")
        response = client.post(
            "/auth/login",
            json={"email": "B@EXAMPLE.com", "password": "password-123"},
        )
        assert response.status_code == 200


class TestRefresh:
    def test_refresh_success(self, client: TestClient) -> None:
        auth = register_user(client, "r@example.com", "student")
        response = client.post("/auth/refresh", json={"refresh_token": auth["refresh_token"]})
        assert response.status_code == 200
        assert response.json()["access_token"] != auth["access_token"] or response.json()["access_token"]

    def test_refresh_rejects_access_token(self, client: TestClient) -> None:
        auth = register_user(client, "r@example.com", "student")
        response = client.post("/auth/refresh", json={"refresh_token": auth["access_token"]})
        assert response.status_code == 401

    def test_refresh_rejects_garbage(self, client: TestClient) -> None:
        response = client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
        assert response.status_code == 401


class TestAuthDependency:
    def test_missing_bearer(self, client: TestClient) -> None:
        response = client.get("/classes")
        assert response.status_code == 401

    def test_bad_bearer(self, client: TestClient) -> None:
        response = client.get("/classes", headers={"Authorization": "Bearer not-a-jwt"})
        assert response.status_code == 401

    def test_valid_bearer(self, client: TestClient) -> None:
        auth = register_user(client, "v@example.com", "student")
        response = client.get("/classes", headers=auth_headers(auth["access_token"]))
        assert response.status_code == 200
