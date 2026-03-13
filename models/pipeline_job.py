# Simple SQLAlchemy model for a pipeline job

from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"
    id = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Additional fields (topic, video_path, etc.) can be added as needed
