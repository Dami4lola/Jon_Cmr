"""
SMS service using Twilio
"""
import logging
import re
from twilio.rest import Client
from ..config import settings

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> str | None:
    """Normalize phone number to E.164 format (+1XXXXXXXXXX for North America)"""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if phone.startswith("+") and len(digits) >= 10:
        return f"+{digits}"
    return None


def send_sms(to_phone: str, body: str) -> str | None:
    """Send an SMS via Twilio. Returns message SID on success, None on failure."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("Twilio credentials not configured — skipping SMS")
        return None

    normalized = _normalize_phone(to_phone)
    if not normalized:
        logger.warning(f"Could not normalize phone number: {to_phone}")
        return None

    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=normalized,
        )
        logger.info(f"SMS sent to {normalized}: SID={message.sid}")
        return message.sid
    except Exception as e:
        logger.error(f"Failed to send SMS to {normalized}: {e}")
        return None


def send_job_reminder(
    client_name: str,
    client_phone: str,
    job_title: str,
    job_address: str,
    scheduled_date: str,
    scheduled_time: str | None = None,
) -> tuple[str | None, str]:
    """Send a job reminder SMS. Returns (twilio_sid, message_body)."""
    time_str = f" at {scheduled_time}" if scheduled_time else ""
    body = (
        f"Hi {client_name}, this is a reminder from OBATEK. "
        f"Your job \"{job_title}\" is scheduled for {scheduled_date}{time_str} "
        f"at {job_address}. "
        f"Please ensure site access is available. "
        f"Reply STOP to opt out."
    )
    sid = send_sms(client_phone, body)
    return sid, body
