"""
Email service using Resend
"""
import resend
from ..config import settings


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    """Send a password reset email with a link containing the reset token"""
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured")

    resend.api_key = settings.RESEND_API_KEY

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    resend.Emails.send({
        "from": "OBATEK <noreply@obatek.com>",
        "to": [to_email],
        "subject": "Reset Your Password - OBATEK",
        "html": f"""
        <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
            <h2 style="color: #333;">Reset Your Password</h2>
            <p>You requested a password reset for your OBATEK account.</p>
            <p>Click the button below to set a new password. This link expires in {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes.</p>
            <a href="{reset_link}"
               style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 16px 0;">
                Reset Password
            </a>
            <p style="color: #666; font-size: 14px;">If you didn't request this, you can safely ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
            <p style="color: #999; font-size: 12px;">OBATEK Worker Portal</p>
        </div>
        """,
    })
