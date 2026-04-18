"""Tests for /quiz/{material_id}/submit."""

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


def _make_prereqs(client: TestClient, educator_token: str, student_token: str) -> dict[str, Any]:
    cls = make_class(client, educator_token)
    enroll_student(client, student_token, cls["id"], cls["enrollment_code"])
    material = make_material(client, educator_token, cls["id"])
    questions = make_quiz(client, educator_token, material["id"])
    publish_material(client, educator_token, material["id"])
    return {"class_id": cls["id"], "material_id": material["id"], "questions": questions, "section_ids": [s["id"] for s in material["sections"]]}


class TestSubmitQuiz:
    def test_perfect_score(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        ctx = _make_prereqs(client, educator["access_token"], student["access_token"])
        answers = {str(q["id"]): DEFAULT_QUIZ[i]["correct_answer"] for i, q in enumerate(ctx["questions"])}
        response = client.post(
            f"/quiz/{ctx['material_id']}/submit",
            json={"answers": answers},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["normalized_score"] == 1.0
        assert body["score"] == body["max_score"]

    def test_zero_score(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        ctx = _make_prereqs(client, educator["access_token"], student["access_token"])
        answers = {str(q["id"]): "WRONG" for q in ctx["questions"]}
        response = client.post(
            f"/quiz/{ctx['material_id']}/submit",
            json={"answers": answers},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["normalized_score"] == 0.0

    def test_partial_score(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        ctx = _make_prereqs(client, educator["access_token"], student["access_token"])
        answers = {str(ctx["questions"][0]["id"]): DEFAULT_QUIZ[0]["correct_answer"]}
        response = client.post(
            f"/quiz/{ctx['material_id']}/submit",
            json={"answers": answers},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["normalized_score"] == 0.5

    def test_non_enrolled_student_denied(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any], second_student: dict[str, Any]
    ) -> None:
        ctx = _make_prereqs(client, educator["access_token"], student["access_token"])
        response = client.post(
            f"/quiz/{ctx['material_id']}/submit",
            json={"answers": {}},
            headers=auth_headers(second_student["access_token"]),
        )
        assert response.status_code == 403

    def test_material_without_questions_rejected(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.post(
            f"/quiz/{material['id']}/submit",
            json={"answers": {}},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 400

    def test_unknown_material_404(self, client: TestClient, student: dict[str, Any]) -> None:
        response = client.post(
            "/quiz/99999/submit",
            json={"answers": {}},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 404

    def test_educator_denied_from_submit(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        ctx = _make_prereqs(client, educator["access_token"], student["access_token"])
        response = client.post(
            f"/quiz/{ctx['material_id']}/submit",
            json={"answers": {}},
            headers=auth_headers(educator["access_token"]),
        )
        assert response.status_code == 403

    def test_invalid_session_id_rejected(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        ctx = _make_prereqs(client, educator["access_token"], student["access_token"])
        response = client.post(
            f"/quiz/{ctx['material_id']}/submit",
            json={"answers": {}, "session_id": 99999},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 400

    def test_session_actual_score_written_back(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        ctx = _make_prereqs(client, educator["access_token"], student["access_token"])
        ended = run_tracked_session(client, student["access_token"], ctx["material_id"], ctx["section_ids"])
        answers = {str(q["id"]): DEFAULT_QUIZ[i]["correct_answer"] for i, q in enumerate(ctx["questions"])}
        response = client.post(
            f"/quiz/{ctx['material_id']}/submit",
            json={"answers": answers, "session_id": ended["session_id"]},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 200
        # prediction route (researcher-only) should now show actual score
        # We don't have researcher here — covered by integration test.
