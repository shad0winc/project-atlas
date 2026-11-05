"""Minimal first-party SMTP transport for security/account email."""

from __future__ import annotations

from email.message import EmailMessage
from html import escape
import smtplib
import ssl


class EmailDeliveryError(RuntimeError):
    """Email delivery failed without exposing credentials."""


class SMTPEmailSender:
    """Send Atlas account-security mail through configured SMTP."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        security: str = "starttls",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.host = host.strip()
        self.port = port
        self.sender = sender.strip()
        self.username = (
            username.strip()
            if username
            else None
        )
        self.password = password if password else None
        self.security = security.strip().lower()
        self.timeout_seconds = timeout_seconds

        if not self.host:
            raise ValueError("SMTP host is required.")
        if self.port <= 0:
            raise ValueError("SMTP port must be positive.")
        if not self.sender:
            raise ValueError("SMTP sender is required.")
        if self.security not in {
            "starttls",
            "ssl",
            "plain",
        }:
            raise ValueError(
                "SMTP security must be starttls, ssl, or plain."
            )

    def send_password_reset(
        self,
        *,
        recipient: str,
        reset_url: str,
        expires_minutes: int,
    ) -> None:
        message = EmailMessage()
        message["Subject"] = (
            "Reset your Project Atlas password"
        )
        message["From"] = self.sender
        message["To"] = recipient
        message.set_content(
            "\n".join(
                [
                    (
                        "A password reset was requested for "
                        "your Project Atlas account."
                    ),
                    "",
                    f"Reset your password: {reset_url}",
                    "",
                    (
                        "This link expires in "
                        f"{expires_minutes} minutes."
                    ),
                    "",
                    (
                        "If you did not request this reset, "
                        "you can ignore this message."
                    ),
                ]
            )
        )

        self._send(message, failure_message="Password recovery email delivery failed.")

    def send_invitation(
        self, *, recipient: str, registration_url: str, expires_at: str,
    ) -> None:
        """Send a multipart invitation using the configured account transport."""
        message = EmailMessage()
        message["Subject"] = "You're invited to Project Atlas"
        message["From"] = self.sender
        message["To"] = recipient
        message.set_content(
            "You're invited to Project Atlas.\n\n"
            f"Create your account: {registration_url}\n\n"
            f"This invitation expires at {expires_at}.\n"
            "If you were not expecting this invitation, you can ignore it.\n"
        )
        url = escape(registration_url, quote=True)
        expiry = escape(expires_at)
        message.add_alternative(
            f"""<!doctype html>
<html lang="en"><body style="margin:0;background:#090e1c;color:#eaf0ff;
font-family:Arial,sans-serif;padding:32px 16px">
<table role="presentation" style="width:100%;max-width:560px;margin:auto;
background:#121b2e;border:1px solid #2a3853;border-radius:16px">
<tr><td style="padding:36px">
<p style="color:#72c8ff;font-size:12px;letter-spacing:3px">PROJECT ATLAS</p>
<h1 style="font-size:28px;line-height:1.2">Your invitation awaits.</h1>
<p style="color:#c5d1e8;line-height:1.6">You have been invited to join
Project Atlas. Create your account to get started.</p>
<p style="margin:32px 0"><a href="{url}" style="display:inline-block;
background:#75c9ff;color:#091021;padding:14px 24px;border-radius:8px;
font-weight:bold;text-decoration:none">Accept invitation</a></p>
<p style="color:#c5d1e8;font-size:14px">Expires at {expiry}.</p>
<p style="color:#c5d1e8;font-size:13px">Button not working?
<a href="{url}" style="color:#75c9ff">Open your registration link</a>.</p>
<p style="color:#96a5bf;font-size:12px;line-height:1.6">If you were not
expecting this invitation, you can ignore this email.</p>
</td></tr></table></body></html>""",
            subtype="html",
        )
        self._send(message, failure_message="Invitation email delivery failed.")

    def _send(self, message: EmailMessage, *, failure_message: str) -> None:
        try:
            if self.security == "ssl":
                with smtplib.SMTP_SSL(
                    self.host,
                    self.port,
                    timeout=self.timeout_seconds,
                    context=ssl.create_default_context(),
                ) as client:
                    self._authenticate_and_send(
                        client,
                        message,
                    )
                return

            with smtplib.SMTP(
                self.host,
                self.port,
                timeout=self.timeout_seconds,
            ) as client:
                if self.security == "starttls":
                    client.starttls(
                        context=ssl.create_default_context()
                    )

                self._authenticate_and_send(
                    client,
                    message,
                )
        except (
            OSError,
            smtplib.SMTPException,
        ) as error:
            raise EmailDeliveryError(
                failure_message
            ) from error

    def _authenticate_and_send(
        self,
        client: smtplib.SMTP,
        message: EmailMessage,
    ) -> None:
        if self.username:
            client.login(
                self.username,
                self.password or "",
            )
        client.send_message(message)
