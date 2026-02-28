"""
Job photo model
"""
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .job import Job


class JobPhoto(SQLModel, table=True):
    """Photo attached to a job for reference"""
    __tablename__ = "job_photo"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    public_url: str  # S3 URL
    content_type: str
    caption: str | None = Field(default=None)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    job: Optional["Job"] = Relationship(back_populates="photos")
