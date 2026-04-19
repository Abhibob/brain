"""Tests for /sessions/* routes and the /track/{id} WebSocket."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient
from redis.asyncio import Redis

from app.settings import get_settings
from tests.conftest import (
    auth_headers,
    enroll_student,
    make_class,
    make_material,
    run_tracked_session,
)


async def _redis_llen(key: str) -> int:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        return await redis.llen(key)
    finally:
        await redis.aclose()


class TestStartSession:
    def test_requires_student(self, client: TestClient, educator: dict[str, Any]) -> None:
        # educator has no enrollment + wrong role; role check fires first
        response = client.post(
            "/sessions/start",
            json={"material_id": 1},
            headers=auth_headers(educator["access_token"]),
        )
        assert response.status_code == 403

    def test_unknown_material_404(self, client: TestClient, student: dict[str, Any]) -> None:
        response = client.post(
            "/sessions/start",
            json={"material_id": 99999},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 404

    def test_non_enrolled_student_denied(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.post(
            "/sessions/start",
            json={"material_id": material["id"]},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 403

    def test_happy_path(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        response = client.post(
            "/sessions/start",
            json={"material_id": material["id"]},
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 200
        assert response.json()["session_id"]


class TestWebSocketTrack:
    def test_rejects_missing_token(self, client: TestClient) -> None:
        # starlette raises WebSocketDisconnect on close
        from starlette.websockets import WebSocketDisconnect

        try:
            with client.websocket_connect("/track/1"):
                pass
        except WebSocketDisconnect:
            return
        raise AssertionError("expected WebSocketDisconnect")

    def test_rejects_invalid_token(self, client: TestClient) -> None:
        from starlette.websockets import WebSocketDisconnect

        try:
            with client.websocket_connect("/track/1?token=not-a-jwt"):
                pass
        except WebSocketDisconnect:
            return
        raise AssertionError("expected WebSocketDisconnect")

    def test_rejects_when_session_not_owned_by_user(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any], second_student: dict[str, Any]
    ) -> None:
        from starlette.websockets import WebSocketDisconnect

        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        started = client.post(
            "/sessions/start",
            json={"material_id": material["id"]},
            headers=auth_headers(student["access_token"]),
        )
        session_id = started.json()["session_id"]

        # second_student authenticates but session belongs to `student`
        try:
            with client.websocket_connect(f"/track/{session_id}?token={second_student['access_token']}"):
                pass
        except WebSocketDisconnect:
            return
        raise AssertionError("expected WebSocketDisconnect")

    def test_heartbeat_and_event_ack(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        started = client.post(
            "/sessions/start",
            json={"material_id": material["id"]},
            headers=auth_headers(student["access_token"]),
        )
        session_id = started.json()["session_id"]

        with client.websocket_connect(f"/track/{session_id}?token={student['access_token']}") as ws:
            ws.send_json({"type": "heartbeat"})
            assert ws.receive_json() == {"type": "ack"}
            ws.send_json({"type": "event", "data": {"event_type": "section_view", "section_id": "1"}, "ts": 1})
            assert ws.receive_json()["type"] == "ack"

    def test_event_without_type_rejected(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        started = client.post(
            "/sessions/start",
            json={"material_id": material["id"]},
            headers=auth_headers(student["access_token"]),
        )
        session_id = started.json()["session_id"]

        with client.websocket_connect(f"/track/{session_id}?token={student['access_token']}") as ws:
            ws.send_json({"type": "event", "data": {}})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_unknown_message_type(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        started = client.post(
            "/sessions/start",
            json={"material_id": material["id"]},
            headers=auth_headers(student["access_token"]),
        )
        session_id = started.json()["session_id"]
        with client.websocket_connect(f"/track/{session_id}?token={student['access_token']}") as ws:
            ws.send_json({"type": "meow"})
            assert ws.receive_json()["type"] == "error"

    def test_events_buffered_in_redis(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        started = client.post(
            "/sessions/start",
            json={"material_id": material["id"]},
            headers=auth_headers(student["access_token"]),
        )
        session_id = started.json()["session_id"]
        with client.websocket_connect(f"/track/{session_id}?token={student['access_token']}") as ws:
            for i in range(3):
                ws.send_json({"type": "event", "data": {"event_type": "mouse_move", "velocity": 0.1}, "ts": i})
                assert ws.receive_json()["type"] == "ack"
        count = asyncio.run(_redis_llen(f"tracking:{session_id}"))
        assert count == 3


class TestEndSession:
    def test_unknown_session_404(self, client: TestClient, student: dict[str, Any]) -> None:
        response = client.post("/sessions/99999/end", headers=auth_headers(student["access_token"]))
        assert response.status_code == 404

    def test_end_drains_redis_and_returns_features(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        ended = run_tracked_session(
            client,
            student["access_token"],
            material["id"],
            [material["sections"][0]["id"], material["sections"][1]["id"]],
        )
        assert ended["features"]["section_completion_rate"] == 1.0
        assert ended["prediction"]["model_version"]
        assert asyncio.run(_redis_llen(f"tracking:{ended['session_id']}")) == 0


class TestPrediction:
    def test_researcher_only(
        self, client: TestClient, educator: dict[str, Any], student: dict[str, Any], researcher: dict[str, Any]
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        ended = run_tracked_session(
            client,
            student["access_token"],
            material["id"],
            [material["sections"][0]["id"], material["sections"][1]["id"]],
        )
        session_id = ended["session_id"]

        student_resp = client.get(f"/sessions/{session_id}/prediction", headers=auth_headers(student["access_token"]))
        assert student_resp.status_code == 403
        educator_resp = client.get(f"/sessions/{session_id}/prediction", headers=auth_headers(educator["access_token"]))
        assert educator_resp.status_code == 403
        researcher_resp = client.get(f"/sessions/{session_id}/prediction", headers=auth_headers(researcher["access_token"]))
        assert researcher_resp.status_code == 200
        body = researcher_resp.json()
        assert body["session_id"] == session_id
        assert body["model_version"]

    def test_unknown_session_404(self, client: TestClient, researcher: dict[str, Any]) -> None:
        response = client.get("/sessions/99999/prediction", headers=auth_headers(researcher["access_token"]))
        assert response.status_code == 404


class TestGazeHeatmap:
    def _run_session_with_gaze(
        self,
        client: TestClient,
        student_token: str,
        material: dict[str, Any],
    ) -> int:
        section_ids = [s["id"] for s in material["sections"]]
        started = client.post(
            "/sessions/start",
            json={"material_id": material["id"]},
            headers=auth_headers(student_token),
        )
        assert started.status_code == 200, started.text
        session_id = started.json()["session_id"]

        with client.websocket_connect(f"/track/{session_id}?token={student_token}") as ws:
            ws.send_json({
                "type": "event",
                "data": {"event_type": "gaze_calibrated", "points": 9, "has_calibration": True},
                "ts": 1,
            })
            ws.receive_json()
            ws.send_json({
                "type": "event",
                "data": {"event_type": "section_view", "section_id": str(section_ids[0])},
                "ts": 10,
            })
            ws.receive_json()
            for offset in range(5):
                ws.send_json({
                    "type": "event",
                    "data": {
                        "event_type": "gaze_fixation",
                        "section_id": str(section_ids[0]),
                        "rel_x": 0.3 + offset * 0.05,
                        "rel_y": 0.4,
                        "x": 200,
                        "y": 300,
                        "duration_ms": 450,
                        "confidence": 0.9,
                        "sample_count": 8,
                    },
                    "ts": 100 + offset * 10,
                })
                ws.receive_json()
            ws.send_json({
                "type": "event",
                "data": {
                    "event_type": "gaze_fixation",
                    "section_id": str(section_ids[1]),
                    "rel_x": 0.5,
                    "rel_y": 0.5,
                    "duration_ms": 600,
                    "confidence": 0.88,
                },
                "ts": 500,
            })
            ws.receive_json()
            ws.send_json({
                "type": "event",
                "data": {"event_type": "gaze_lost", "duration_ms": 1200, "reason": "no_face"},
                "ts": 1000,
            })
            ws.receive_json()

        ended = client.post(
            f"/sessions/{session_id}/end",
            headers=auth_headers(student_token),
        )
        assert ended.status_code == 200, ended.text
        return session_id

    def test_researcher_reads_heatmap(
        self,
        client: TestClient,
        educator: dict[str, Any],
        student: dict[str, Any],
        researcher: dict[str, Any],
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        session_id = self._run_session_with_gaze(client, student["access_token"], material)

        response = client.get(
            f"/sessions/{session_id}/gaze-heatmap",
            headers=auth_headers(researcher["access_token"]),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["session_id"] == session_id
        assert body["material_id"] == material["id"]
        assert body["gaze_present"] is True
        assert body["has_calibration"] is True
        assert body["fixation_count"] == 6
        assert body["attention_source"] == "gaze"
        assert len(body["sections"]) >= 2
        first = next(s for s in body["sections"] if s["fixation_count"] == 5)
        assert len(first["fixations"]) == 5
        assert all(0 <= f["rel_x"] <= 1 for f in first["fixations"])
        assert body["lost_pct"] > 0

    def test_owning_student_can_read(
        self,
        client: TestClient,
        educator: dict[str, Any],
        student: dict[str, Any],
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        session_id = self._run_session_with_gaze(client, student["access_token"], material)

        response = client.get(
            f"/sessions/{session_id}/gaze-heatmap",
            headers=auth_headers(student["access_token"]),
        )
        assert response.status_code == 200

    def test_other_student_forbidden(
        self,
        client: TestClient,
        educator: dict[str, Any],
        student: dict[str, Any],
        second_student: dict[str, Any],
    ) -> None:
        cls = make_class(client, educator["access_token"])
        enroll_student(client, student["access_token"], cls["id"], cls["enrollment_code"])
        material = make_material(client, educator["access_token"], cls["id"])
        session_id = self._run_session_with_gaze(client, student["access_token"], material)

        response = client.get(
            f"/sessions/{session_id}/gaze-heatmap",
            headers=auth_headers(second_student["access_token"]),
        )
        assert response.status_code == 403

    def test_unknown_session_404(
        self, client: TestClient, researcher: dict[str, Any]
    ) -> None:
        response = client.get(
            "/sessions/99999/gaze-heatmap",
            headers=auth_headers(researcher["access_token"]),
        )
        assert response.status_code == 404
