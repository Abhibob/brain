"""Tests for /classes routes."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    enroll_student,
    make_class,
    make_material,
    register_user,
)


class TestCreateClass:
    def test_educator_creates_class(self, client: TestClient, educator: dict[str, Any]) -> None:
        response = client.post(
            "/classes",
            json={"title": "Algorithms", "description": "Recursion + DP"},
            headers=auth_headers(educator["access_token"]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Algorithms"
        assert body["enrollment_code"]
        assert len(body["enrollment_code"]) <= 8

    def test_student_denied(self, client: TestClient, student: dict[str, Any]) -> None:
        response = client.post(
            "/classes",
            json={"title": "X"},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 403

    def test_researcher_denied_from_create(self, client: TestClient, researcher: dict[str, Any]) -> None:
        response = client.post(
            "/classes",
            json={"title": "X"},
            headers=auth_headers(researcher["access_token"]),
        )
        assert response.status_code == 403


class TestListClasses:
    def test_educator_sees_only_own(self, client: TestClient, educator: dict[str, Any]) -> None:
        other = register_user(client, "other-ed@example.com", "educator")
        make_class(client, educator["access_token"], title="Mine")
        make_class(client, other["access_token"], title="Theirs")
        response = client.get("/classes", headers=auth_headers(educator["access_token"]))
        assert response.status_code == 200
        titles = {item["title"] for item in response.json()}
        assert titles == {"Mine"}

    def test_student_sees_only_enrolled(self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"], title="Joined")
        make_class(client, educator["access_token"], title="NotJoined")
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        response = client.get("/classes", headers=auth_headers(student["access_token"]))
        titles = {item["title"] for item in response.json()}
        assert titles == {"Joined"}

    def test_researcher_sees_all(self, client: TestClient, educator: dict[str, Any], researcher: dict[str, Any]) -> None:
        make_class(client, educator["access_token"], title="A")
        make_class(client, educator["access_token"], title="B")
        response = client.get("/classes", headers=auth_headers(researcher["access_token"]))
        titles = {item["title"] for item in response.json()}
        assert titles == {"A", "B"}


class TestGetClass:
    def test_educator_gets_own_class_with_materials(self, client: TestClient, educator: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        make_material(client, educator["access_token"], cls["id"], title="Lesson 1")
        response = client.get(f"/classes/{cls['id']}", headers=auth_headers(educator["access_token"]))
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == cls["id"]
        assert body["materials"][0]["title"] == "Lesson 1"

    def test_unknown_class_404(self, client: TestClient, educator: dict[str, Any]) -> None:
        response = client.get("/classes/99999", headers=auth_headers(educator["access_token"]))
        assert response.status_code == 404

    def test_student_not_enrolled_denied(self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        response = client.get(f"/classes/{cls['id']}", headers=auth_headers(student["access_token"]))
        assert response.status_code == 403

    def test_enrolled_student_allowed(self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        response = client.get(f"/classes/{cls['id']}", headers=auth_headers(student["access_token"]))
        assert response.status_code == 200

    def test_other_educator_denied(self, client: TestClient, educator: dict[str, Any]) -> None:
        other = register_user(client, "other@example.com", "educator")
        cls = make_class(client, educator["access_token"])
        response = client.get(f"/classes/{cls['id']}", headers=auth_headers(other["access_token"]))
        assert response.status_code == 403


class TestEnroll:
    def test_enroll_success(self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        response = client.post(
            f"/classes/{cls['id']}/enroll",
            json={"enrollment_code": cls["enrollment_code"]},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "enrolled"

    def test_enroll_wrong_code(self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        response = client.post(
            f"/classes/{cls['id']}/enroll",
            json={"enrollment_code": "WRONGCODE"},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 404

    def test_enroll_twice_is_idempotent(self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        code = cls["enrollment_code"]
        enroll_student(client, student["access_token"], cls["id"], code)
        response = client.post(
            f"/classes/{cls['id']}/enroll",
            json={"enrollment_code": code},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "already_enrolled"

    def test_enroll_requires_student_role(self, client: TestClient, educator: dict[str, Any], researcher: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        response = client.post(
            f"/classes/{cls['id']}/enroll",
            json={"enrollment_code": cls["enrollment_code"]},
            headers=auth_headers(researcher["access_token"]),
        )
        assert response.status_code == 403


class TestRoster:
    def test_educator_roster_no_profile_counts(self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        response = client.get(f"/classes/{cls['id']}/students", headers=auth_headers(educator["access_token"]))
        assert response.status_code == 200
        assert "profile_entry_count" not in response.json()[0]

    def test_researcher_roster_has_profile_counts(self, client: TestClient, educator: dict[str, Any], researcher: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        response = client.get(f"/classes/{cls['id']}/students", headers=auth_headers(researcher["access_token"]))
        assert response.status_code == 200
        assert "profile_entry_count" in response.json()[0]

    def test_student_denied(self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        response = client.get(f"/classes/{cls['id']}/students", headers=auth_headers(student["access_token"]))
        # Roster is educator/researcher only. The current endpoint returns 404 because
        # the can-read-class guard treats students without an explicit enrollment check as
        # missing the class; either way the request is rejected.
        assert response.status_code in {403, 404}


class TestClassAnalytics:
    def test_researcher_only(self, client: TestClient, educator: dict[str, Any], researcher: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        deny = client.get(f"/classes/{cls['id']}/analytics", headers=auth_headers(educator["access_token"]))
        assert deny.status_code == 403
        allow = client.get(f"/classes/{cls['id']}/analytics", headers=auth_headers(researcher["access_token"]))
        assert allow.status_code == 200
        payload = allow.json()
        assert payload["class_id"] == cls["id"]
        assert "drift" in payload

    def test_unknown_class_404(self, client: TestClient, researcher: dict[str, Any]) -> None:
        response = client.get("/classes/99999/analytics", headers=auth_headers(researcher["access_token"]))
        assert response.status_code == 404
