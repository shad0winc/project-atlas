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
            }
        )

        self.assertEqual(settings.jwt_issuer, "atlas-test")
        self.assertEqual(
            settings.jwt_audience,
            "atlas-test-client",
        )
        self.assertEqual(settings.access_token_minutes, 20)
        self.assertEqual(settings.refresh_token_days, 14)

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
