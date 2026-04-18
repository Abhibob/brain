"""Tests for /students/{id}/profile."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import (
    DEFAULT_QUIZ,
    auth_headers,
    enroll_student,
    make_class,
    make_material,
    make_quiz,
    publish_material,
    run_tracked_session,
)


class TestGetProfile:
    def test_educator_denied_researcher_and_self_allowed(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any], researcher: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        sid = student["user"]["id"]
        # Educators are not allowed to read student profile entries.
        assert client.get(f"/students/{sid}/profile", headers=auth_headers(educator["access_token"])).status_code == 403
        # Researchers see all profiles.
        assert client.get(f"/students/{sid}/profile", headers=auth_headers(researcher["access_token"])).status_code == 200
        # Students can read their own profile.
        assert client.get(f"/students/{sid}/profile", headers=auth_headers(student["access_token"])).status_code == 200

    def test_student_cannot_read_other_students_profile(
        self, client: TestClient, student: dict[str, Any], second_student: dict[str, Any]
    ) -> None:
        response = client.get(
            f"/students/{student['user']['id']}/profile",
            headers=auth_headers(second_student["access_token"]),
        )
        assert response.status_code == 403

    def test_unknown_student_404(self, client: TestClient, researcher: dict[str, Any]) -> None:
        response = client.get("/students/99999/profile", headers=auth_headers(researcher["access_token"]))
        assert response.status_code == 404

    def test_profile_populated_after_quiz_submit(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any], researcher: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        questions = make_quiz(client, educator["access_token"], material["id"])
        publish_material(client, educator["access_token"], material["id"])
        section_ids = [s["id"] for s in material["sections"]]
        ended = run_tracked_session(client, student["access_token"], material["id"], section_ids)
        answers = {str(q["id"]): DEFAULT_QUIZ[i]["correct_answer"] for i, q in enumerate(questions)}
        submit = client.post(
            f"/quiz/{material['id']}/submit",
            json={"answers": answers, "session_id": ended["session_id"]},
            headers=auth_headers(student["access_token"]),
        )
        assert submit.status_code == 200

        # add_student_profile_entry ran eagerly — profile endpoint should show an entry
        response = client.get(
            f"/students/{student['user']['id']}/profile",
            headers=auth_headers(researcher["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["entry_count"] >= 1
        first = response.json()["entries"][0]["profile_json"]
        assert {"topic", "observed_score", "recommendation"}.issubset(first.keys())
