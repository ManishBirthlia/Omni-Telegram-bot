from celery import Celery
import os

celery_app = Celery(
    "omni_telegram_bot",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

# Register task modules (they will be created as placeholders later)
celery_app.autodiscover_tasks(["workers.intelligence_tasks", "workers.generation_tasks", "workers.assembly_tasks", "workers.upload_tasks"])
