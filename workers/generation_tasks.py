# Placeholder for generation‑level tasks (image, video, voice, music)

from workers.celery_app import celery_app

@celery_app.task(name="generation.image_generator")
def image_generator(job_id: str, prompt: str):
    # In a real implementation this would call DALL‑E 3
    return f"Image generated for prompt '{prompt}' (job {job_id})"
