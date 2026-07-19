import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from atlas.health import (
    HealthCheck,
    HealthReport,
    HealthStatus,
    _command_check,
    collect_foundation_health,
    collect_operational_health,
    render_text,
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


class OperationalHealthTests(unittest.TestCase):
    def test_operational_report_collects_shared_categories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = root / "project"
            storage = root / "storage"
            media = storage / "media"
            downloads = storage / "downloads"
            (project / "config").mkdir(parents=True)
            (project / "config" / "atlas.conf").write_text("", encoding="utf-8")
            for relative in (
                "VERSION", "CHARTER.md", "ROADMAP.md", "CHANGELOG.md",
                "docs/BUILD_LOG.md", "docs/MATURITY.md", "docs/INDEXERS.md",
            ):
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            for path in (
                media / "Movies", media / "TV", media / "Anime Movies",
                media / "Anime TV", downloads,
            ):
                path.mkdir(parents=True, exist_ok=True)

            def runner(command):
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            report = collect_operational_health(
                project_dir=project,
                storage_root=storage,
                media_root=media,
                downloads_root=downloads,
                runner=runner,
            )

            self.assertNotEqual(report.status, HealthStatus.CRITICAL)
            self.assertTrue({"core", "infrastructure", "services", "storage", "project"}.issubset(report.category_scores()))

    def test_command_failure_is_critical(self) -> None:
        def runner(command):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="failure")

        check = _command_check(
            name="Docker Engine",
            category="infrastructure",
            command=("docker", "info"),
            success_message="ok",
            failure_message="failed",
            runner=runner,
        )
        self.assertEqual(check.status, HealthStatus.CRITICAL)

    def test_text_renderer_includes_score_and_status(self) -> None:
        report = HealthReport(
            checks=[HealthCheck("Docker", "infrastructure", "healthy", "reachable")],
            generated_at="2026-07-19T00:00:00Z",
        )
        rendered = render_text(report)
        self.assertIn("Overall Status: HEALTHY", rendered)
        self.assertIn("Overall Score:  100%", rendered)
        self.assertIn("OK      Docker", rendered)


if __name__ == "__main__":
    unittest.main()
