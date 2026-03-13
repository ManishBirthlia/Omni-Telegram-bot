# Placeholder for intelligence‑level tasks (script generation, metadata, etc.)

from workers.celery_app import celery_app

@celery_app.task(name="intelligence.script_generator")
def script_generator(job_id: str, topic: str):
    # In a real implementation this would call Claude API
    return f"Generated script for {topic} (job {job_id})"
