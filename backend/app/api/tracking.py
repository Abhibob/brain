from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.db import AsyncSessionLocal, get_db
from app.models import Class, Enrollment, Material, ScorePrediction, TrackingSession, User
from app.redis import get_redis
from app.schemas import SessionEndOut, SessionPredictionOut, SessionStart, SessionStartOut
from app.security import decode_token
from app.services.tracking import ingest_event
from app.workers import tasks

router = APIRouter(tags=["tracking"])


@router.post("/sessions/start", response_model=SessionStartOut)
async def start_session(
    payload: SessionStart,
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
) -> SessionStartOut:
    material = await db.scalar(select(Material).where(Material.id == payload.material_id))
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    enrolled = await db.scalar(select(Enrollment.id).where(Enrollment.class_id == material.class_id, Enrollment.student_id == current_user.id))
    if not enrolled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student is not enrolled")
    session = TrackingSession(student_id=current_user.id, material_id=payload.material_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionStartOut(session_id=session.id, started_at=session.started_at)


@router.post("/sessions/{session_id}/end", response_model=SessionEndOut)
async def end_session(
    session_id: int,
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
) -> SessionEndOut:
    session = await db.scalar(select(TrackingSession).where(TrackingSession.id == session_id, TrackingSession.student_id == current_user.id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.ended_at = datetime.now(UTC)
    await db.commit()
    tasks.extract_features_and_predict.delay(session_id)
    await db.refresh(session)
    prediction = await db.scalar(select(ScorePrediction).where(ScorePrediction.session_id == session_id))
    return SessionEndOut(
        session_id=session.id,
        features=session.features,
        prediction={
            "predicted_score": prediction.predicted_score,
            "confidence": prediction.confidence,
            "model_version": prediction.model_version,
            "actual_score": prediction.actual_score,
        }
        if prediction
        else None,
    )


@router.get("/sessions/{session_id}/prediction", response_model=SessionPredictionOut)
async def get_prediction(
    session_id: int,
    current_user: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> SessionPredictionOut:
    session = await db.scalar(select(TrackingSession).where(TrackingSession.id == session_id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    prediction = await db.scalar(select(ScorePrediction).where(ScorePrediction.session_id == session_id))
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")
    return SessionPredictionOut(
        session_id=session_id,
        predicted_score=prediction.predicted_score,
        confidence=prediction.confidence,
        model_version=prediction.model_version,
        actual_score=prediction.actual_score,
    )


@router.websocket("/track/{session_id}")
async def track(websocket: WebSocket, session_id: int) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        decoded = decode_token(token, "access")
        user_id = int(decoded["sub"])
    except ValueError:
        await websocket.close(code=1008)
        return

    async with AsyncSessionLocal() as db:
        session = await db.scalar(select(TrackingSession).where(TrackingSession.id == session_id, TrackingSession.student_id == user_id))
        if session is None:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    redis = get_redis()
    try:
        while True:
            payload = await websocket.receive_json()
            message_type = payload.get("type")
            if message_type == "heartbeat":
                await websocket.send_json({"type": "ack"})
            elif message_type == "event":
                data = payload.get("data") or {}
                event_type = data.get("event_type") or data.get("type")
                if not event_type:
                    await websocket.send_json({"type": "error", "message": "event_type is required"})
                    continue
                await ingest_event(redis, session_id, event_type, data, int(payload.get("ts") or data.get("client_ts") or 0))
                await websocket.send_json({"type": "ack"})
            else:
                await websocket.send_json({"type": "error", "message": "Unsupported message type"})
    except WebSocketDisconnect:
        return
    finally:
        await redis.aclose()
