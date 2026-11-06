"""Invitation SMTP content and failure regression coverage."""

import os
import smtplib
import unittest
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from unittest.mock import Mock, patch

from atlas_api.services.email_sender import EmailDeliveryError, SMTPEmailSender, invitation_expiry
from atlas_api.services.invitation_art import invitation_art
from atlas_api.services.invitation_email import deliver_invitation_email


class InvitationEmailTests(unittest.TestCase):
    environment = {
        "ATLAS_JWT_SECRET": "x" * 32,
        "ATLAS_BASE_URL": "https://atlas.example.test",
        "ATLAS_SMTP_HOST": "smtp.gmail.com",
        "ATLAS_SMTP_SENDER": "Project Atlas <atlas@example.test>",
        "ATLAS_SMTP_USERNAME": "atlas@example.test",
        "ATLAS_SMTP_PASSWORD": "private-app-password",
    }

    def test_invitation_is_multipart_and_uses_starttls(self):
        with patch("atlas_api.services.email_sender.smtplib.SMTP") as smtp:
            status = self.deliver()
        self.assertEqual(status, "accepted")
        client = smtp.return_value.__enter__.return_value
        client.starttls.assert_called_once()
        client.login.assert_called_once_with("atlas@example.test", "private-app-password")
        message = client.send_message.call_args.args[0]
        self.assertEqual(message["To"], "friend@example.test")
        self.assertIn("Project Atlas", message["From"])
        self.assertEqual(message.get_content_type(), "multipart/alternative")
        message = BytesParser(policy=policy.default).parsebytes(message.as_bytes())
        for kind in ("plain", "html"):
            part = message.get_body(preferencelist=(kind,))
            content = part.get_content()
            self.assertIn("https://atlas.example.test/register#token=atlas_inv_test", content)
            self.assertIn("January 01, 2030 at 00:00 UTC", content)
        self.assertIn("Accept invitation", message.get_body(preferencelist=("html",)).get_content())
        images = [part for part in message.walk() if part.get_content_type() == "image/jpeg"]
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["Content-ID"], "<atlas-invitation-art>")
        self.assertEqual(images[0].get_content_disposition(), "inline")
        self.assertEqual(images[0].get_payload(decode=True), invitation_art())
        self.assertLess(len(message.as_bytes()), 250_000)

    def test_button_and_fallback_link_work_with_unlinked_art(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
                self.image_link = None
                self.active = None
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "a":
                    self.active = attrs.get("href")
                    self.links.append(self.active)
                if tag == "img":
                    self.image_link = self.active
            def handle_endtag(self, tag):
                if tag == "a":
                    self.active = None
        sender = SMTPEmailSender(host="smtp.test", port=587, sender="atlas@example.test")
        sender._send = Mock()
        url = "https://atlas.test/register#token=private%2Btoken&test=1"
        sender.send_invitation(recipient="friend@example.test", registration_url=url,
                               expires_at="2030-01-01T00:00:00Z")
        html = sender._send.call_args.args[0].get_body(preferencelist=("html",)).get_content()
        parsed = Links()
        parsed.feed(html)
        self.assertEqual(parsed.links, [url, url])
        self.assertIsNone(parsed.image_link)
        self.assertNotIn('src="http', html)
        self.assertNotIn("Tap to accept", html)

    def test_welcome_covers_media_and_identifies_future_features(self):
        with patch("atlas_api.services.email_sender.smtplib.SMTP") as smtp:
            self.deliver()
        message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        expected = (
            "Welcome to Project Atlas, your home for all things media. "
            "Explore movies, shows, and sports, with game servers and "
            "tech and gaming news on the horizon."
        )
        for kind in ("plain", "html"):
            body = message.get_body(preferencelist=(kind,)).get_content()
            self.assertIn(expected, body)
            self.assertNotIn("Your next movie night starts here", body)

    def test_accept_button_declares_black_text_with_legacy_color_fallback(self):
        class Button(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
                self.labels = []
            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.links.append(dict(attrs))
                if tag == "font":
                    self.labels.append(dict(attrs))
        sender = SMTPEmailSender(host="smtp.test", port=587, sender="atlas@example.test")
        sender._send = Mock()
        sender.send_invitation(recipient="friend@example.test", registration_url="https://atlas.test/register",
                               expires_at="2030-01-01T00:00:00Z")
        html = sender._send.call_args.args[0].get_body(preferencelist=("html",)).get_content()
        parsed = Button()
        parsed.feed(html)
        self.assertEqual(len(parsed.links), 2)
        button_style = parsed.links[0]["style"]
        self.assertIn("background:#75c9ff", button_style)
        self.assertIn("color:#000000 !important", button_style)
        self.assertIn("-webkit-text-fill-color:#000000 !important", button_style)
        self.assertEqual(parsed.labels[0]["color"], "#000000")
        self.assertIn("color:#000000 !important", parsed.labels[0]["style"])

    def test_expiry_converts_offsets_without_guessing_naive_dates(self):
        self.assertEqual(invitation_expiry("2030-01-01T03:30:00+03:30"),
                         "January 01, 2030 at 00:00 UTC")
        self.assertEqual(invitation_expiry("2030-01-01T03:30:00"), "2030-01-01T03:30:00")

    def deliver(self, **environment):
        with patch.dict(os.environ, {**self.environment, **environment}, clear=True):
            return deliver_invitation_email(
                recipient="friend@example.test", token="atlas_inv_test",
                expires_at="2030-01-01T00:00:00Z",
            )

    def test_mail_failure_does_not_escape_or_expose_credentials(self):
        with patch("atlas_api.services.email_sender.smtplib.SMTP", side_effect=smtplib.SMTPException("private")):
            self.assertEqual(self.deliver(), "failed")

    def test_missing_expiration_never_attempts_email(self):
        with patch("atlas_api.services.invitation_email.SMTPEmailSender") as sender:
            for expiry in (None, "", "   "):
                self.assertEqual(deliver_invitation_email(
                    recipient="friend@example.test", token="secret", expires_at=expiry,
                ), "unavailable")
            sender.assert_not_called()

    def test_missing_recipient_skips_without_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(deliver_invitation_email(recipient=None, token="secret", expires_at="later"), "skipped")

    def test_localhost_and_fragment_base_urls_are_not_emailed(self):
        with patch("atlas_api.services.email_sender.smtplib.SMTP") as smtp:
            for url in ("http://localhost", "https://atlas.example.test/#wrong", "https://user:pass@atlas.example.test"):
                self.assertEqual(self.deliver(ATLAS_BASE_URL=url), "unavailable")
            smtp.assert_not_called()

    def test_html_attributes_escape_untrusted_content(self):
        sender = SMTPEmailSender(host="smtp.test", port=587, sender="atlas@example.test")
        sender._send = Mock()
        sender.send_invitation(
            recipient="friend@example.test", registration_url='https://atlas.test/#token="><script>',
            expires_at="<expiry>",
        )
        message = sender._send.call_args.args[0]
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn("&lt;expiry&gt;", html)
        self.assertNotIn("<script>", html)

    def test_password_recovery_keeps_existing_subject_and_plain_text(self):
        with patch("atlas_api.services.email_sender.smtplib.SMTP") as smtp:
            sender = SMTPEmailSender(host="smtp.test", port=587, sender="atlas@example.test")
            sender.send_password_reset(
                recipient="friend@example.test", reset_url="https://atlas.test/reset#token=test",
                expires_minutes=60,
            )
        message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertEqual(message["Subject"], "Reset your Project Atlas password")
        self.assertEqual(message.get_content_type(), "text/plain")
        self.assertIn("60 minutes", message.get_content())


if __name__ == "__main__":
    unittest.main()
