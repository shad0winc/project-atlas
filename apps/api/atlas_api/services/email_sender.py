"""Minimal first-party SMTP transport for security/account email."""

from __future__ import annotations

from email.message import EmailMessage
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
                "Password recovery email delivery failed."
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
