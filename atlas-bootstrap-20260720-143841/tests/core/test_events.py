from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import patch

from atlas.events import publish_event


class PublishEventTests(unittest.TestCase):
    @patch("atlas.events.subprocess.run")
    def test_publish_event_uses_atlas_module_contract(
        self,
        run_mock,
    ) -> None:
        publish_event(
            "sports",
            "sports.game-started",
            {
                "game_id": "game-123",
                "active": True,
            },
            atlas_binary="/custom/atlas",
        )

        command = run_mock.call_args.args[0]

        self.assertEqual(
            command[:5],
            [
                "/custom/atlas",
                "module",
                "publish",
                "sports",
                "sports.game-started",
            ],
        )
        self.assertEqual(
            json.loads(command[5]),
            {
                "game_id": "game-123",
                "active": True,
            },
        )
        run_mock.assert_called_once_with(
            command,
            check=True,
        )

    @patch("atlas.events.subprocess.run")
    def test_publish_event_defaults_to_empty_payload(
        self,
        run_mock,
    ) -> None:
        publish_event(
            "sports",
            "sports.refresh",
            atlas_binary="/bin/atlas",
        )

        command = run_mock.call_args.args[0]
        self.assertEqual(command[5], "{}")

    def test_publish_event_rejects_empty_module(self) -> None:
        with self.assertRaises(ValueError):
            publish_event(" ", "sports.refresh")

    def test_publish_event_rejects_empty_event(self) -> None:
        with self.assertRaises(ValueError):
            publish_event("sports", " ")

    @patch("atlas.events.subprocess.run")
    def test_publish_event_propagates_cli_failure(
        self,
        run_mock,
    ) -> None:
        run_mock.side_effect = subprocess.CalledProcessError(
            1,
            ["/bin/atlas"],
        )

        with self.assertRaises(subprocess.CalledProcessError):
            publish_event(
                "sports",
                "sports.refresh",
            )


class PublishCoreEventTests(unittest.TestCase):
    @patch("atlas.events.subprocess.run")
    def test_publish_core_event_uses_atlas_event_contract(self, run):
        from atlas.events import publish_core_event
        publish_core_event("favorite.created", {"id": "fav_1"}, atlas_binary="/tmp/atlas")
        run.assert_called_once_with(["/tmp/atlas", "event", "publish", "favorite.created", '{"id":"fav_1"}', "atlas"], check=True)
