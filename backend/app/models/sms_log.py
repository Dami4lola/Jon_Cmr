"""
SMS Log model
"""
from datetime import datetime
from sqlmodel import SQLModel, Field


class SmsLog(SQLModel, table=True):
    __tablename__ = "sms_log"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    client_id: int = Field(foreign_key="client.id")
    phone_number: str = Field(max_length=20)
    message_body: str
    status: str = Field(default="pending", max_length=20)
    twilio_sid: str | None = Field(default=None, max_length=50)
    error_message: str | None = Field(default=None)
    sent_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
