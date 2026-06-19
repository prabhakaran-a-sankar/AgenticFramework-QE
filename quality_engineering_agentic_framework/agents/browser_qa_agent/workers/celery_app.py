from celery import Celery
from ..config import get_settings


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "qa_agent",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    return app


celery_app = make_celery()
