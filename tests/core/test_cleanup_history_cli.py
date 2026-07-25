"""Tests for cleanup history CLI integration."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import Mock, patch

from atlas.cleanup.history_models import CleanupHistoryError
from atlas.cleanup_cli import main


class CleanupHistoryCliTests(unittest.TestCase):
    """Validate cleanup history CLI behavior."""

    def test_history_human_output(self) -> None:
        service = Mock()
        service.list.return_value = ()

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                ["history"],
                history_service=service,
            )

        self.assertEqual(result, 0)
        self.assertIn(
            "Atlas Cleanup History",
            stdout.getvalue(),
        )
        self.assertIn(
            "No cleanup execution history found.",
            stdout.getvalue(),
        )
        service.list.assert_called_once_with(
            last=None,
            provider=None,
            has_failures=None,
        )

    def test_history_json_output(self) -> None:
        entry = Mock()
        entry.to_dict.return_value = {
            "execution_id": (
                "cln_0123456789abcdef"
                "0123456789abcdef"
            ),
            "provider": "jellyfin",
        }

        service = Mock()
        service.list.return_value = (entry,)

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                [
                    "history",
                    "--json",
                ],
                history_service=service,
            )

        self.assertEqual(result, 0)

        payload = json.loads(stdout.getvalue())

        self.assertEqual(len(payload), 1)
        self.assertEqual(
            payload[0]["provider"],
            "jellyfin",
        )
        service.list.assert_called_once_with(
            last=None,
            provider=None,
            has_failures=None,
        )

    def test_history_empty_json_output(self) -> None:
        service = Mock()
        service.list.return_value = ()

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                [
                    "history",
                    "--json",
                ],
                history_service=service,
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            json.loads(stdout.getvalue()),
            [],
        )

    @patch("atlas.cleanup_cli.JsonlCleanupHistoryStore")
    @patch("atlas.cleanup_cli.CleanupHistoryService")
    def test_history_uses_default_audit_path(
        self,
        service_class,
        store_class,
    ) -> None:
        service = service_class.return_value
        service.list.return_value = ()

        with patch(
            "atlas.cleanup_cli.default_cleanup_audit_path",
            return_value="/tmp/default-audit.jsonl",
        ):
            result = main(["history"])

        self.assertEqual(result, 0)

        store_class.assert_called_once_with(
            "/tmp/default-audit.jsonl"
        )
        service_class.assert_called_once_with(
            store_class.return_value
        )

    @patch("atlas.cleanup_cli.JsonlCleanupHistoryStore")
    @patch("atlas.cleanup_cli.CleanupHistoryService")
    def test_history_accepts_explicit_audit_path(
        self,
        service_class,
        store_class,
    ) -> None:
        service = service_class.return_value
        service.list.return_value = ()

        result = main(
            [
                "history",
                "--audit-path",
                "/tmp/custom-audit.jsonl",
            ]
        )

        self.assertEqual(result, 0)

        store_class.assert_called_once_with(
            "/tmp/custom-audit.jsonl"
        )

    def test_history_forwards_last_filter(self) -> None:
        service = Mock()
        service.list.return_value = ()

        result = main(
            [
                "history",
                "--last",
                "20",
            ],
            history_service=service,
        )

        self.assertEqual(result, 0)
        service.list.assert_called_once_with(
            last=20,
            provider=None,
            has_failures=None,
        )

    def test_history_forwards_provider_filter(self) -> None:
        service = Mock()
        service.list.return_value = ()

        result = main(
            [
                "history",
                "--provider",
                "jellyfin",
            ],
            history_service=service,
        )

        self.assertEqual(result, 0)
        service.list.assert_called_once_with(
            last=None,
            provider="jellyfin",
            has_failures=None,
        )

    def test_history_forwards_failure_filter(self) -> None:
        service = Mock()
        service.list.return_value = ()

        result = main(
            [
                "history",
                "--failures",
            ],
            history_service=service,
        )

        self.assertEqual(result, 0)
        service.list.assert_called_once_with(
            last=None,
            provider=None,
            has_failures=True,
        )

    def test_history_forwards_without_failures_filter(
        self,
    ) -> None:
        service = Mock()
        service.list.return_value = ()

        result = main(
            [
                "history",
                "--without-failures",
            ],
            history_service=service,
        )

        self.assertEqual(result, 0)
        service.list.assert_called_once_with(
            last=None,
            provider=None,
            has_failures=False,
        )

    def test_history_forwards_combined_filters(self) -> None:
        service = Mock()
        service.list.return_value = ()

        result = main(
            [
                "history",
                "--last",
                "5",
                "--provider",
                "JELLYFIN",
                "--failures",
                "--json",
            ],
            history_service=service,
        )

        self.assertEqual(result, 0)
        service.list.assert_called_once_with(
            last=5,
            provider="JELLYFIN",
            has_failures=True,
        )

    def test_history_reports_service_error(self) -> None:
        service = Mock()
        service.list.side_effect = CleanupHistoryError(
            "history unavailable"
        )

        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                ["history"],
                history_service=service,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "cleanup history failed: history unavailable",
            stderr.getvalue(),
        )

    def test_history_reports_invalid_last(self) -> None:
        service = Mock()
        service.list.side_effect = CleanupHistoryError(
            "last must be greater than zero"
        )

        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                [
                    "history",
                    "--last",
                    "0",
                ],
                history_service=service,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "cleanup history failed: "
            "last must be greater than zero",
            stderr.getvalue(),
        )

    def test_history_rejects_conflicting_failure_filters(
        self,
    ) -> None:
        service = Mock()

        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as context:
                main(
                    [
                        "history",
                        "--failures",
                        "--without-failures",
                    ],
                    history_service=service,
                )

        self.assertEqual(context.exception.code, 2)
        self.assertIn(
            "not allowed with argument",
            stderr.getvalue(),
        )
        service.list.assert_not_called()


if __name__ == "__main__":
    unittest.main()
