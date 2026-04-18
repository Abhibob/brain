"""Tests for /classes/{id}/materials and /materials/{id}* routes."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import (
    DEFAULT_QUIZ,
    DEFAULT_SECTIONS,
    auth_headers,
    enroll_student,
    make_class,
    make_material,
    make_quiz,
    publish_material,
    register_user,
)


class TestCreateMaterial:
    def test_educator_can_create(self, client: TestClient, educator: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        response = client.post(
            f"/classes/{cls['id']}/materials",
            json={"title": "M1", "type": "lesson", "sections": DEFAULT_SECTIONS},
            headers=auth_headers(educator["access_token"]),
        )
        assert response.status_code == 200
        assert len(response.json()["sections"]) == 2

    def test_word_count_populated(self, client: TestClient, educator: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        assert material["sections"][0]["word_count"] > 0

    def test_other_educator_denied(self, client: TestClient, educator: dict[str, Any]) -> None:
        other = register_user(client, "other-ed@example.com", "educator")
        cls = make_class(client, educator["access_token"])
        response = client.post(
            f"/classes/{cls['id']}/materials",
            json={"title": "M", "type": "lesson", "sections": DEFAULT_SECTIONS},
            headers=auth_headers(other["access_token"]),
        )
        assert response.status_code == 404

    def test_student_denied(self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        response = client.post(
            f"/classes/{cls['id']}/materials",
            json={"title": "M", "type": "lesson", "sections": DEFAULT_SECTIONS},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 403


class TestGetMaterial:
    def test_student_unpublished_denied(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.get(f"/materials/{material['id']}", headers=auth_headers(student["access_token"]))
        assert response.status_code == 200
        # unpublished means no generated personalization yet
        assert response.json()["personalized"] is False

    def test_student_not_enrolled_denied(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.get(f"/materials/{material['id']}", headers=auth_headers(student["access_token"]))
        assert response.status_code == 403

    def test_404_for_unknown(self, client: TestClient, educator: dict[str, Any]) -> None:
        response = client.get("/materials/99999", headers=auth_headers(educator["access_token"]))
        assert response.status_code == 404

    def test_researcher_can_read_any(self, client: TestClient, educator: dict[str, Any], researcher: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.get(f"/materials/{material['id']}", headers=auth_headers(researcher["access_token"]))
        assert response.status_code == 200


class TestUpdateMaterial:
    def test_update_title(self, client: TestClient, educator: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.put(
            f"/materials/{material['id']}",
            json={"title": "New title"},
            headers=auth_headers(educator["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New title"

    def test_update_sections_replaces_all(self, client: TestClient, educator: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.put(
            f"/materials/{material['id']}",
            json={"sections": [{"title": "Only", "content": "one section now", "order_index": 0}]},
            headers=auth_headers(educator["access_token"]),
        )
        assert response.status_code == 200
        assert len(response.json()["sections"]) == 1

    def test_other_educator_denied(self, client: TestClient, educator: dict[str, Any]) -> None:
        other = register_user(client, "x@example.com", "educator")
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.put(
            f"/materials/{material['id']}",
            json={"title": "Nope"},
            headers=auth_headers(other["access_token"]),
        )
        assert response.status_code == 403


class TestDeleteMaterial:
    def test_delete(self, client: TestClient, educator: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.delete(f"/materials/{material['id']}", headers=auth_headers(educator["access_token"]))
        assert response.status_code == 200
        missing = client.get(f"/materials/{material['id']}", headers=auth_headers(educator["access_token"]))
        assert missing.status_code == 404

    def test_non_owner_denied(self, client: TestClient, educator: dict[str, Any]) -> None:
        other = register_user(client, "o@example.com", "educator")
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.delete(f"/materials/{material['id']}", headers=auth_headers(other["access_token"]))
        assert response.status_code == 403


class TestPublishMaterial:
    def test_publish_sets_timestamp_and_queues_tasks(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        make_quiz(client, educator["access_token"], material["id"])
        body = publish_material(client, educator["access_token"], material["id"])
        assert body["published_at"]
        assert body["personalization_tasks"] == 1

    def test_publish_with_no_students_zero_tasks(self, client: TestClient, educator: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        body = publish_material(client, educator["access_token"], material["id"])
        assert body["personalization_tasks"] == 0


class TestQuizCRUD:
    def test_create_and_fetch_quiz(self, client: TestClient, educator: dict[str, Any]) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        created = make_quiz(client, educator["access_token"], material["id"])
        assert len(created) == len(DEFAULT_QUIZ)
        assert "correct_answer" not in created[0]

        get = client.get(f"/materials/{material['id']}/quiz", headers=auth_headers(educator["access_token"]))
        assert get.status_code == 200
        assert len(get.json()) == len(DEFAULT_QUIZ)

    def test_quiz_visible_to_enrolled_student(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        make_quiz(client, educator["access_token"], material["id"])
        response = client.get(f"/materials/{material['id']}/quiz", headers=auth_headers(student["access_token"]))
        assert response.status_code == 200
        # options visible, answers hidden
        assert "correct_answer" not in response.json()[0]

    def test_quiz_denied_for_non_enrolled(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        make_quiz(client, educator["access_token"], material["id"])
        response = client.get(f"/materials/{material['id']}/quiz", headers=auth_headers(student["access_token"]))
        assert response.status_code == 403

    def test_create_quiz_owner_only(self, client: TestClient, educator: dict[str, Any]) -> None:
        other = register_user(client, "o@example.com", "educator")
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.post(
            f"/materials/{material['id']}/quiz",
            json=DEFAULT_QUIZ,
            headers=auth_headers(other["access_token"]),
        )
        assert response.status_code == 403
