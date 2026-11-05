"""Deliver newly issued invitation tokens through the existing SMTP transport."""

from urllib.parse import quote, urlsplit

from atlas_api.core.settings import AtlasAPISettings
from atlas_api.services.email_sender import EmailDeliveryError, SMTPEmailSender


def deliver_invitation_email(
    *, recipient: str | None, token: str, expires_at: str,
) -> str:
    """Report SMTP acceptance while preserving the successful invitation issue."""
    if not recipient:
        return "skipped"
    try:
        settings = AtlasAPISettings.from_environment()
        origin = urlsplit(settings.base_url)
        if (
            not settings.smtp_host or not settings.smtp_sender
            or origin.scheme not in {"https", "http"} or not origin.hostname
            or origin.hostname in {"localhost", "127.0.0.1", "::1"}
            or origin.username or origin.password or origin.query or origin.fragment
        ):
            return "unavailable"
        sender = SMTPEmailSender(
            host=settings.smtp_host, port=settings.smtp_port,
            sender=settings.smtp_sender, username=settings.smtp_username,
            password=settings.smtp_password, security=settings.smtp_security,
        )
        sender.send_invitation(
            recipient=recipient,
            registration_url=f"{settings.base_url.rstrip('/')}/register#token={quote(token, safe='')}",
            expires_at=expires_at,
        )
    except (EmailDeliveryError, ValueError):
        return "failed"
    return "accepted"
