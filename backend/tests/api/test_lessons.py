"""Tests for /lessons/{material_id}/personalize/{student_id}."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    enroll_student,
    make_class,
    make_material,
    make_quiz,
    publish_material,
)


class TestPersonalizeNow:
    def test_researcher_only(
        self,
        client: TestClient,
        educator: dict[str, Any],
        researcher: dict[str, Any],
        student: dict[str, Any],
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        make_quiz(client, educator["access_token"], material["id"])
        publish_material(client, educator["access_token"], material["id"])

        path = f"/lessons/{material['id']}/personalize/{student['user']['id']}"
        assert client.post(path, headers=auth_headers(educator["access_token"])).status_code == 403
        assert client.post(path, headers=auth_headers(student["access_token"])).status_code == 403
        response = client.post(path, headers=auth_headers(researcher["access_token"]))
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_unknown_material_404(self, client: TestClient, researcher: dict[str, Any], student: dict[str, Any]) -> None:
        response = client.post(
            f"/lessons/99999/personalize/{student['user']['id']}",
            headers=auth_headers(researcher["access_token"]),
        )
        assert response.status_code == 404

    def test_unenrolled_student_404(
        self,
        client: TestClient,
        educator: dict[str, Any],
        researcher: dict[str, Any],
        student: dict[str, Any],
        second_student: dict[str, Any],
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.post(
            f"/lessons/{material['id']}/personalize/{second_student['user']['id']}",
            headers=auth_headers(researcher["access_token"]),
        )
        assert response.status_code == 404
