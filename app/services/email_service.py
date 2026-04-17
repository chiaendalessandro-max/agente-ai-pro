import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings


logger = logging.getLogger(__name__)


def make_email(company: str, sector: str, description: str, score: int) -> tuple[str, str]:
    subject = f"Growth opportunity for {company}"
    body = (
        f"Hello {company} team,\n\n"
        f"We reviewed your position in {sector or 'your market'} and found strong fit signals.\n"
        f"Lead score: {score}/100.\n\n"
        f"Public insight: {description[:220]}\n\n"
        "Would you like a short 15-minute intro call?\n\n"
        "Best regards"
    )
    return subject, body


def send_or_draft(to_email: str, subject: str, body: str) -> tuple[str, str]:
    if not settings.smtp_enabled or not settings.smtp_host or not settings.smtp_user or not settings.smtp_from:
        return "draft", "SMTP not configured"
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to_email
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, [to_email], msg.as_string())
        return "sent", ""
    except Exception as exc:
        logger.warning("Email send failed: %s", str(exc)[:250])
        return "draft", str(exc)[:500]
