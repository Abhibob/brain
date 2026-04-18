from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, run_tracked_session


def test_student_can_read_own_learning_profile(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
) -> None:
    material = published_class["material"]
    section_ids = published_class["section_ids"]
    student_token = student["access_token"]
    run_tracked_session(client, student_token, material["id"], section_ids)

    response = client.get(
        f"/students/{student['user']['id']}/learning-profile",
        headers=auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "style_vector" in data
    assert set(data["style_vector"].keys()) == {
        "pace",
        "depth",
        "attention_stability",
        "engagement_mode",
        "revisit_tendency",
        "visual_orientation",
        "motor_style",
    }
    assert data["session_count"] >= 1


def test_researcher_can_read_any_learning_profile(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    researcher: dict[str, Any],
) -> None:
    material = published_class["material"]
    section_ids = published_class["section_ids"]
    run_tracked_session(client, student["access_token"], material["id"], section_ids)

    response = client.get(
        f"/students/{student['user']['id']}/learning-profile",
        headers=auth_headers(researcher["access_token"]),
    )
    assert response.status_code == 200, response.text


def test_educator_blocked_from_learning_profile(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    educator: dict[str, Any],
) -> None:
    response = client.get(
        f"/students/{student['user']['id']}/learning-profile",
        headers=auth_headers(educator["access_token"]),
    )
    assert response.status_code == 403


def test_mastery_endpoint_returns_nodes_and_edges(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
) -> None:
    material = published_class["material"]
    section_ids = published_class["section_ids"]
    student_token = student["access_token"]
    run_tracked_session(client, student_token, material["id"], section_ids)

    response = client.get(
        f"/students/{student['user']['id']}/mastery",
        headers=auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data["nodes"], list)
    assert data["nodes"], "expected at least one mastery node"
    node = data["nodes"][0]
    assert {"topic", "mastery_score", "exposure_score", "encounter_count"}.issubset(node.keys())


def test_lesson_plan_endpoint_returns_structured_plan(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
) -> None:
    material = published_class["material"]
    section_ids = published_class["section_ids"]
    student_token = student["access_token"]
    run_tracked_session(client, student_token, material["id"], section_ids)

    response = client.post(
        f"/students/{student['user']['id']}/lesson-plan",
        headers=auth_headers(student_token),
        json={"topic": "pythagorean theorem"},
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["topic"] == "pythagorean theorem"
    assert plan["sections"], "plan should contain sections"
    for section in plan["sections"]:
        assert {"title", "angle", "why_this_works_for_them", "estimated_word_count"}.issubset(section.keys())


def test_learning_context_endpoint(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
) -> None:
    material = published_class["material"]
    section_ids = published_class["section_ids"]
    student_token = student["access_token"]
    run_tracked_session(client, student_token, material["id"], section_ids)

    response = client.get(
        f"/students/{student['user']['id']}/learning-context",
        headers=auth_headers(student_token),
        params={"topic": "recursion"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["seed_text"] == "recursion"
    assert isinstance(data["style_summary_lines"], list)
    assert isinstance(data["mastery_nodes"], list)
