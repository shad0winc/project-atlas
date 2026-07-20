from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from atlas.invitation_cli import main


class InvitationCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.identity = Path(self.temp.name) / "identity"
        self.base = ["--identity-directory", str(self.identity), "--base-url", "https://atlas.example.com"]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main([*self.base, *arguments])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_create_outputs_one_time_registration_url_without_persisting_token(self) -> None:
        code, output, error = self.run_cli("create", "--email", "FRIEND@EXAMPLE.COM", "--json")
        self.assertEqual((code, error), (0, ""))
        result = json.loads(output)
        self.assertEqual(result["email"], "friend@example.com")
        self.assertIn("/register?token=atlas_inv_", result["registration_url"])
        persisted = (self.identity / "invitations" / "active" / f"{result['invite_id']}.json").read_text()
        self.assertNotIn(result["token"], persisted)

    def test_list_show_revoke_and_verify_storage(self) -> None:
        _, output, _ = self.run_cli("create", "--json")
        invite_id = json.loads(output)["invite_id"]
        code, output, _ = self.run_cli("list", "--status", "pending", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)[0]["invite_id"], invite_id)
        code, output, _ = self.run_cli("show", invite_id)
        self.assertEqual(json.loads(output)["status"], "pending")
        code, output, _ = self.run_cli("revoke", invite_id, "--revoked-by", "usr_admin")
        self.assertEqual(json.loads(output)["status"], "revoked")
        code, output, _ = self.run_cli("verify")
        self.assertEqual((code, output), (0, "PASS\tinvitation storage valid\n"))

    def test_token_verification_and_invalid_expiration(self) -> None:
        _, output, _ = self.run_cli("create", "--json")
        result = json.loads(output)
        code, output, _ = self.run_cli("verify", "--token", result["token"])
        self.assertEqual(code, 0)
        self.assertIn(result["invite_id"], output)
        code, _, error = self.run_cli("create", "--days", "0")
        self.assertEqual(code, 1)
        self.assertIn("greater than zero", error)

    def test_cleanup_reports_count(self) -> None:
        code, output, _ = self.run_cli("cleanup")
        self.assertEqual((code, output), (0, "Archived expired invitations: 0\n"))


if __name__ == "__main__":
    unittest.main()
