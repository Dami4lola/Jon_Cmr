"""
Background scheduler for automatic SMS reminders
"""
import logging
from datetime import datetime, timedelta, date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from ..config import settings
from ..database import engine
from ..models import Job, SmsLog
from .sms import send_job_reminder

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def check_and_send_reminders():
    """Check for upcoming jobs and send SMS reminders to clients."""
    with Session(engine) as session:
        now = datetime.utcnow()
        cutoff_date = (now + timedelta(hours=settings.SMS_REMINDER_HOURS_BEFORE)).date()
        today = date.today()

        jobs = session.exec(
            select(Job)
            .options(selectinload(Job.client))
            .where(Job.start_date >= today)
            .where(Job.start_date <= cutoff_date)
            .where(Job.is_completed == False)
        ).all()

        sent_count = 0
        for job in jobs:
            if not job.client or not job.client.phone_number:
                continue

            existing = session.exec(
                select(SmsLog).where(
                    SmsLog.job_id == job.id,
                    SmsLog.status == "sent",
                )
            ).first()
            if existing:
                continue

            scheduled_date_str = job.start_date.strftime("%B %d, %Y")
            time_str = job.scheduled_time.strftime("%I:%M %p") if job.scheduled_time else None
            job_address = job.get_job_address()

            sid, body = send_job_reminder(
                client_name=job.client.name,
                client_phone=job.client.phone_number,
                job_title=job.title,
                job_address=job_address,
                scheduled_date=scheduled_date_str,
                scheduled_time=time_str,
            )

            log = SmsLog(
                job_id=job.id,
                client_id=job.client_id,
                phone_number=job.client.phone_number,
                message_body=body,
                status="sent" if sid else "failed",
                twilio_sid=sid,
                error_message=None if sid else "Send failed",
                sent_at=datetime.utcnow() if sid else None,
            )
            session.add(log)
            if sid:
                sent_count += 1

        session.commit()
        if sent_count:
            logger.info(f"SMS reminders sent: {sent_count}")


def start_scheduler():
    scheduler.add_job(
        check_and_send_reminders,
        IntervalTrigger(minutes=15),
        id="sms_reminder_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("SMS reminder scheduler started (checking every 15 minutes)")
