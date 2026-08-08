"""Tests for the Atlas dashboard summary service."""

import unittest

from atlas.health import HealthCheck, HealthReport
from atlas_api.services.dashboard import DashboardSummaryService


class DashboardSummaryServiceTests(unittest.TestCase):
    """Verify HealthReport-to-dashboard contract adaptation."""

    def test_summary_maps_operational_health(self) -> None:
        report = HealthReport(
            checks=[
                HealthCheck(
                    "Docker Engine",
                    "infrastructure",
                    "healthy",
                ),
                HealthCheck(
                    "Storage Root",
                    "infrastructure",
                    "warning",
                ),
                HealthCheck(
                    "jellyfin",
                    "services",
                    "healthy",
                ),
                HealthCheck(
                    "sonarr",
                    "services",
                    "critical",
                ),
                HealthCheck(
                    "Movies",
                    "storage",
                    "healthy",
                ),
            ],
            generated_at="2026-07-26T18:00:00Z",
        )

        service = DashboardSummaryService(lambda: report)

        summary = service.read_summary()

        self.assertEqual(
            summary.generated_at,
            "2026-07-26T18:00:00Z",
        )
        self.assertEqual(
            tuple(metric.id for metric in summary.metrics),
            (
                "system-health",
                "infrastructure",
                "services",
                "storage",
            ),
        )

        metrics = {
            metric.id: metric
            for metric in summary.metrics
        }

        self.assertEqual(metrics["system-health"].status, "offline")
        self.assertEqual(metrics["infrastructure"].status, "warning")
        self.assertEqual(metrics["services"].status, "offline")
        self.assertEqual(metrics["storage"].status, "healthy")

    def test_summary_uses_unknown_for_missing_category(self) -> None:
        report = HealthReport(
            checks=[
                HealthCheck(
                    "Python Runtime",
                    "core",
                    "healthy",
                ),
            ],
            generated_at="2026-07-26T18:00:00Z",
        )

        summary = DashboardSummaryService(lambda: report).read_summary()

        metrics = {
            metric.id: metric
            for metric in summary.metrics
        }

        self.assertEqual(metrics["services"].value, "Unknown")
        self.assertEqual(metrics["services"].status, "unknown")
        self.assertEqual(
            metrics["services"].detail,
            "No checks reported",
        )

    def test_service_rejects_non_health_report(self) -> None:
        service = DashboardSummaryService(lambda: object())

        with self.assertRaises(TypeError):
            service.read_summary()

    def test_service_rejects_non_callable_factory(self) -> None:
        with self.assertRaises(TypeError):
            DashboardSummaryService(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
