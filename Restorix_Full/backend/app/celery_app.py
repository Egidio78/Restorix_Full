from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "dbshield",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Rome",
    enable_utc=True,
    beat_schedule={
        "check-due-jobs-every-minute": {
            "task": "tasks.check_due_jobs",
            "schedule": 60.0,
        },
        "cleanup-scheduler-every-5-min": {
            "task": "app.tasks.cleanup_scheduler",
            "schedule": 300.0,
        },
    },
)
