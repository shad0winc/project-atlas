"""Tests for Atlas API authentication settings."""

import unittest

from atlas_api.core.settings import AtlasAPISettings, SettingsError


class AtlasAPISettingsTests(unittest.TestCase):
    def test_reads_environment_values(self) -> None:
        settings = AtlasAPISettings.from_environment(
            {
                "ATLAS_JWT_SECRET": "s" * 64,
                "ATLAS_JWT_ISSUER": "atlas-test",
                "ATLAS_JWT_AUDIENCE": "atlas-test-client",
                "ATLAS_ACCESS_TOKEN_MINUTES": "20",
                "ATLAS_REFRESH_TOKEN_DAYS": "14",
                "ATLAS_BASE_URL": "https://atlas.example.test",
                "ATLAS_PASSWORD_RECOVERY_MINUTES": "45",
                "ATLAS_SMTP_HOST": "smtp.example.test",
                "ATLAS_SMTP_PORT": "2525",
                "ATLAS_SMTP_SENDER": "atlas@example.test",
                "ATLAS_SMTP_USERNAME": "atlas-user",
                "ATLAS_SMTP_PASSWORD": "secret",
                "ATLAS_SMTP_SECURITY": "ssl",
            }
        )

        self.assertEqual(settings.jwt_issuer, "atlas-test")
        self.assertEqual(
            settings.jwt_audience,
            "atlas-test-client",
        )
        self.assertEqual(settings.access_token_minutes, 20)
        self.assertEqual(settings.refresh_token_days, 14)
        self.assertEqual(
            settings.base_url,
            "https://atlas.example.test",
        )
        self.assertEqual(
            settings.password_recovery_minutes,
            45,
        )
        self.assertEqual(
            settings.smtp_host,
            "smtp.example.test",
        )
        self.assertEqual(settings.smtp_port, 2525)
        self.assertEqual(
            settings.smtp_sender,
            "atlas@example.test",
        )
        self.assertEqual(
            settings.smtp_security,
            "ssl",
        )

    def test_rejects_short_secret(self) -> None:
        with self.assertRaises(SettingsError):
            AtlasAPISettings(jwt_secret="too-short")

    def test_rejects_non_integer_lifetime(self) -> None:
        with self.assertRaises(SettingsError):
            AtlasAPISettings.from_environment(
                {
                    "ATLAS_JWT_SECRET": "s" * 64,
                    "ATLAS_ACCESS_TOKEN_MINUTES": "invalid",
                }
            )


if __name__ == "__main__":
    unittest.main()
