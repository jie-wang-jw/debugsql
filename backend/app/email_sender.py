from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import get_settings


class EmailDeliveryError(RuntimeError):
    pass


def send_login_code(email: str, code: str) -> dict:
    settings = get_settings()
    if settings.email_dev_log_codes:
        print(f"[auth] DebugSQL login code for {email}: {code}", flush=True)

    if not settings.smtp_host:
        if settings.email_dev_log_codes:
            return {"delivery": "dev_log"}
        raise EmailDeliveryError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = "Your DebugSQL login code"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                f"Your DebugSQL verification code is: {code}",
                "",
                f"This code expires in {settings.email_login_code_ttl_minutes} minutes.",
                "If you did not request this code, you can ignore this email.",
            ]
        )
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except Exception as exc:  # smtplib raises several transport-specific errors.
        if settings.email_dev_log_codes:
            print(f"[auth] SMTP delivery failed; login code was logged instead: {exc}", flush=True)
            return {"delivery": "dev_log", "warning": "smtp_failed"}
        raise EmailDeliveryError("Email delivery failed") from exc

    return {"delivery": "smtp"}
