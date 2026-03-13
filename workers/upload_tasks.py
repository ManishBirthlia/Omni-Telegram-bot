# Placeholder for upload‑level tasks (YouTube API interaction)

from workers.celery_app import celery_app

@celery_app.task(name="upload.youtube_uploader")
def youtube_uploader(job_id: str, video_path: str, metadata: dict):
    # In a real implementation this would call YouTube Data API
    return f"Uploaded {video_path} to YouTube (job {job_id})"
