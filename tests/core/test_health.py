import json
import tempfile
import unittest
from pathlib import Path

from atlas.health import (
    HealthCheck,
    HealthReport,
    HealthStatus,
    collect_foundation_health,
)


class HealthCheckTests(unittest.TestCase):
    def test_health_check_serializes_normalized_contract(self):
        check = HealthCheck(
            name=" Docker ",
            category=" infrastructure ",
            status="healthy",
            message="Docker daemon reachable",
            details={"socket": "/var/run/docker.sock"},
        )

        self.assertEqual(check.name, "Docker")
        self.assertEqual(check.category, "infrastructure")
        self.assertEqual(check.status, HealthStatus.HEALTHY)
        self.assertEqual(check.score, 100)
        self.assertEqual(check.to_dict()["status"], "healthy")

    def test_health_check_rejects_invalid_status(self):
        with self.assertRaises(ValueError):
            HealthCheck("Docker", "infrastructure", "broken")

    def test_health_check_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            HealthCheck("", "core", "healthy")


class HealthReportTests(unittest.TestCase):
    def test_empty_report_is_unknown(self):
        report = HealthReport(generated_at="2026-07-18T00:00:00Z")

        self.assertEqual(report.status, HealthStatus.UNKNOWN)
        self.assertEqual(report.score, 0)

    def test_report_aggregates_status_and_scores(self):
        report = HealthReport(generated_at="2026-07-18T00:00:00Z")
        report.add(HealthCheck("CLI", "core", "healthy"))
        report.add(HealthCheck("Storage", "infrastructure", "warning"))

        self.assertEqual(report.status, HealthStatus.WARNING)
        self.assertEqual(report.score, 75)
        self.assertEqual(report.category_scores(), {"core": 100, "infrastructure": 50})

    def test_report_json_is_machine_readable(self):
        report = HealthReport(generated_at="2026-07-18T00:00:00Z")
        report.add(HealthCheck("CLI", "core", "healthy"))

        payload = json.loads(report.to_json())

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["checks"][0]["name"], "CLI")

    def test_foundation_report_detects_project_and_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            config_dir = project_dir / "config"
            config_dir.mkdir()
            (config_dir / "atlas.conf").write_text("ATLAS_PROJECT_DIR=/tmp\n", encoding="utf-8")

            report = collect_foundation_health(project_dir)

        self.assertEqual(report.status, HealthStatus.HEALTHY)
        self.assertEqual(len(report.checks), 3)
        self.assertEqual(report.score, 100)

    def test_foundation_report_marks_missing_project_critical(self):
        report = collect_foundation_health("/path/that/does/not/exist")

        self.assertEqual(report.status, HealthStatus.CRITICAL)
        self.assertEqual(report.checks[1].status, HealthStatus.CRITICAL)
        self.assertEqual(report.checks[2].status, HealthStatus.CRITICAL)


if __name__ == "__main__":
    unittest.main()
