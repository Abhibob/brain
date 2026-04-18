from __future__ import annotations

from celery import Celery

from app.settings import get_settings

settings = get_settings()

celery_app = Celery("edutrack", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    timezone="UTC",
)

