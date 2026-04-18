from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, run_tracked_session


def _login_token(response: dict[str, Any]) -> str:
    return response["access_token"]


def test_educator_can_create_and_publish_lesson_plan(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    educator: dict[str, Any],
) -> None:
    # Seed learning signal so scoring has context
    run_tracked_session(
        client,
        student["access_token"],
        published_class["material"]["id"],
        published_class["section_ids"],
    )

    create = client.post(
        "/teacher/lesson-plans",
        json={
            "student_id": student["user"]["id"],
            "topic": "pythagorean theorem",
            "description": "intro lesson for this student",
            "class_id": published_class["class"]["id"],
        },
        headers=auth_headers(educator["access_token"]),
    )
    assert create.status_code == 200, create.text
    draft = create.json()
    assert draft["topic"] == "pythagorean theorem"
    assert draft["status"] in {"ready", "draft", "published"}
    assert draft["nodes"], "a sequence should be proposed"
    assert draft["candidates"], "candidates should be available"
    for candidate in draft["candidates"]:
        assert 0 <= candidate["fit_score"] <= 100
        assert candidate["asset"]["kind"] in {"reading", "quiz", "video", "practice"}

    publish = client.post(
        f"/teacher/lesson-plans/{draft['id']}/publish",
        headers=auth_headers(educator["access_token"]),
    )
    assert publish.status_code == 200, publish.text
    material = publish.json()
    assert material["sections"], "published material should have sections"
    assert material["class_id"] == published_class["class"]["id"]


def test_educator_cannot_access_other_educators_draft(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    educator: dict[str, Any],
) -> None:
    create = client.post(
        "/teacher/lesson-plans",
        json={
            "student_id": student["user"]["id"],
            "topic": "arrays",
            "class_id": published_class["class"]["id"],
        },
        headers=auth_headers(educator["access_token"]),
    )
    assert create.status_code == 200
    draft_id = create.json()["id"]

    other = client.post(
        "/auth/register",
        json={
            "email": "other-educator@example.com",
            "password": "password-123",
            "role": "educator",
            "institution": "Other",
        },
    )
    assert other.status_code == 200
    other_token = other.json()["access_token"]

    response = client.get(f"/teacher/lesson-plans/{draft_id}", headers=auth_headers(other_token))
    assert response.status_code == 403


def test_student_role_blocked(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
) -> None:
    response = client.post(
        "/teacher/lesson-plans",
        json={
            "student_id": student["user"]["id"],
            "topic": "anything",
            "class_id": published_class["class"]["id"],
        },
        headers=auth_headers(student["access_token"]),
    )
    assert response.status_code == 403


def test_patch_reorders_nodes(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    educator: dict[str, Any],
) -> None:
    create = client.post(
        "/teacher/lesson-plans",
        json={
            "student_id": student["user"]["id"],
            "topic": "recursion",
            "class_id": published_class["class"]["id"],
        },
        headers=auth_headers(educator["access_token"]),
    )
    assert create.status_code == 200
    draft = create.json()
    original_nodes = draft["nodes"]
    if len(original_nodes) < 2:
        return

    new_order = [
        {"asset_id": original_nodes[1]["asset_id"], "order_index": 0, "teacher_adjusted": True},
        {"asset_id": original_nodes[0]["asset_id"], "order_index": 1, "teacher_adjusted": True},
    ]
    patched = client.patch(
        f"/teacher/lesson-plans/{draft['id']}",
        json={"nodes": new_order},
        headers=auth_headers(educator["access_token"]),
    )
    assert patched.status_code == 200, patched.text
    patched_nodes = patched.json()["nodes"]
    assert patched_nodes[0]["asset_id"] == original_nodes[1]["asset_id"]
    assert all(node["teacher_adjusted"] is True for node in patched_nodes)


def test_create_from_material_seeds_draft_with_real_sections(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    educator: dict[str, Any],
) -> None:
    material = published_class["material"]
    create = client.post(
        "/teacher/lesson-plans",
        json={
            "student_id": student["user"]["id"],
            "topic": material["title"],
            "class_id": published_class["class"]["id"],
            "material_id": material["id"],
        },
        headers=auth_headers(educator["access_token"]),
    )
    assert create.status_code == 200, create.text
    draft = create.json()
    # The nodes should come from the material's real sections (plus a quiz asset).
    assert draft["nodes"], "nodes should be seeded from the material"
    source_nodes = [n for n in draft["nodes"] if n["asset"]["generated_by"] == "source"]
    assert len(source_nodes) >= len(material["sections"]), "every section becomes a source node"
    kinds = {n["asset"]["kind"] for n in draft["nodes"]}
    assert "reading" in kinds, "at least one reading card"
    assert "quiz" in kinds, "quiz card is added from material's questions"
    # Candidates pool is empty at seed time — LLM suggestions only come via regenerate.
    assert draft["candidates"] == [] or all(c["asset"]["generated_by"] != "llm" for c in draft["candidates"])


def test_regenerate_adds_candidates_without_replacing_nodes(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    educator: dict[str, Any],
) -> None:
    material = published_class["material"]
    create = client.post(
        "/teacher/lesson-plans",
        json={
            "student_id": student["user"]["id"],
            "topic": material["title"],
            "class_id": published_class["class"]["id"],
            "material_id": material["id"],
        },
        headers=auth_headers(educator["access_token"]),
    )
    assert create.status_code == 200, create.text
    draft = create.json()
    original_node_ids = [n["asset_id"] for n in draft["nodes"]]

    regen = client.post(
        f"/teacher/lesson-plans/{draft['id']}/regenerate",
        headers=auth_headers(educator["access_token"]),
    )
    assert regen.status_code == 200, regen.text
    updated = regen.json()
    # Nodes stay untouched.
    assert [n["asset_id"] for n in updated["nodes"]] == original_node_ids
    # Candidates pool is now populated.
    assert updated["candidates"], "regenerate should populate candidates"


def test_publish_replaces_target_material_sections(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    educator: dict[str, Any],
) -> None:
    material = published_class["material"]
    create = client.post(
        "/teacher/lesson-plans",
        json={
            "student_id": student["user"]["id"],
            "topic": material["title"],
            "class_id": published_class["class"]["id"],
            "material_id": material["id"],
        },
        headers=auth_headers(educator["access_token"]),
    )
    draft = create.json()
    publish = client.post(
        f"/teacher/lesson-plans/{draft['id']}/publish?target_material_id={material['id']}",
        headers=auth_headers(educator["access_token"]),
    )
    assert publish.status_code == 200, publish.text
    published = publish.json()
    # Publishing in place keeps the same material id and class id.
    assert published["id"] == material["id"]
    assert published["class_id"] == material["class_id"]
    assert published["sections"], "published material keeps a section list"


def test_learning_view_endpoint(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    educator: dict[str, Any],
) -> None:
    run_tracked_session(
        client,
        student["access_token"],
        published_class["material"]["id"],
        published_class["section_ids"],
    )
    response = client.get(
        f"/teacher/students/{student['user']['id']}/learning-view",
        headers=auth_headers(educator["access_token"]),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["student_id"] == student["user"]["id"]
    assert data["learning_profile"] is not None
    assert "style_vector" in data["learning_profile"]
