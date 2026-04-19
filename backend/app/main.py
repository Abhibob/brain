from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, classes, lesson_studio, lessons, materials, profiles, quizzes, research, tracking
from app.redis import close_redis
from app.settings import get_settings

settings = get_settings()

app = FastAPI(title="EduTrack API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(classes.router)
app.include_router(materials.router)
app.include_router(quizzes.router)
app.include_router(tracking.router)
app.include_router(profiles.router)
app.include_router(lessons.router)
app.include_router(lesson_studio.router)
app.include_router(research.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_redis()
