from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlas.identity import IdentityPaths
from atlas.invitations import InvitationError, InvitationStore, TOKEN_PREFIX


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class InvitationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "identity"
        self.clock = MutableClock(datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc))
        self.store = InvitationStore(IdentityPaths(self.root), self.clock)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_initializes_identity_layout_and_registry(self) -> None:
        self.store.initialize()
        self.assertTrue((self.root / "invitations" / "active").is_dir())
        self.assertTrue((self.root / "invitations" / "completed").is_dir())
        self.assertTrue((self.root / "invitations" / "revoked").is_dir())
        registry = json.loads(
            (self.root / "invitations" / "invitations.json").read_text()
        )
        self.assertEqual(registry, {"schema_version": 1, "invitations": {}})

    def test_create_returns_plaintext_once_and_persists_only_hash(self) -> None:
        issue = self.store.create(email="FRIEND@EXAMPLE.COM", created_by="usr_admin")
        self.assertTrue(issue.token.startswith(TOKEN_PREFIX))
        persisted = self.store.get(issue.invitation["invite_id"])
        self.assertNotIn(issue.token, json.dumps(persisted))
        self.assertEqual(
            persisted["token_hash"],
            hashlib.sha256(issue.token.encode()).hexdigest(),
        )
        self.assertEqual(persisted["email"], "friend@example.com")
        self.assertEqual(persisted["status"], "pending")

    def test_verify_token_rejects_invalid_and_accepts_valid_token(self) -> None:
        issue = self.store.create()
        with self.assertRaisesRegex(InvitationError, "invalid invitation token"):
            self.store.verify_token(TOKEN_PREFIX + "wrong")
        verified = self.store.verify_token(issue.token)
        self.assertEqual(verified["invite_id"], issue.invitation["invite_id"])

    def test_expired_token_is_archived_and_rejected(self) -> None:
        issue = self.store.create(expires_in=timedelta(hours=1))
        self.clock.value += timedelta(hours=2)
        with self.assertRaisesRegex(InvitationError, "expired"):
            self.store.verify_token(issue.token)
        record = self.store.get(issue.invitation["invite_id"])
        self.assertEqual(record["status"], "expired")
        self.assertTrue((self.root / "invitations" / "revoked" / f"{record['invite_id']}.json").exists())

    def test_revoke_moves_record_and_preserves_audit_metadata(self) -> None:
        issue = self.store.create()
        record = self.store.revoke(issue.invitation["invite_id"], revoked_by="usr_admin")
        self.assertEqual(record["status"], "revoked")
        self.assertEqual(record["revoked_by"], "usr_admin")
        self.assertFalse((self.root / "invitations" / "active" / f"{record['invite_id']}.json").exists())
        with self.assertRaisesRegex(InvitationError, "invalid invitation token"):
            self.store.verify_token(issue.token)

    def test_complete_moves_record_and_requires_actor(self) -> None:
        issue = self.store.create()
        with self.assertRaisesRegex(InvitationError, "completed_by is required"):
            self.store.complete(issue.invitation["invite_id"], completed_by="")
        record = self.store.complete(issue.invitation["invite_id"], completed_by="usr_member")
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["completed_by"], "usr_member")
        self.assertTrue((self.root / "invitations" / "completed" / f"{record['invite_id']}.json").exists())

    def test_cleanup_expired_archives_only_expired_pending_records(self) -> None:
        expired = self.store.create(expires_in=timedelta(hours=1))
        active = self.store.create(expires_in=timedelta(days=1))
        self.clock.value += timedelta(hours=2)
        self.assertEqual(self.store.cleanup_expired(), [expired.invitation["invite_id"]])
        self.assertEqual(self.store.get(expired.invitation["invite_id"])["status"], "expired")
        self.assertEqual(self.store.get(active.invitation["invite_id"])["status"], "pending")

    def test_rejects_nonpositive_expiration(self) -> None:
        with self.assertRaisesRegex(InvitationError, "greater than zero"):
            self.store.create(expires_in=timedelta(0))

    def test_verify_detects_registry_mismatch_and_orphan(self) -> None:
        issue = self.store.create()
        registry_path = self.root / "invitations" / "invitations.json"
        registry = json.loads(registry_path.read_text())
        registry["invitations"][issue.invitation["invite_id"]]["status"] = "completed"
        registry_path.write_text(json.dumps(registry))
        orphan = self.root / "invitations" / "active" / "inv_00000000000000000000000000000000.json"
        orphan.write_text("{}")
        errors = self.store.verify()
        self.assertTrue(any("status does not match" in error for error in errors))
        self.assertTrue(any("unregistered invitation record" in error for error in errors))

    def test_registry_path_escape_is_rejected(self) -> None:
        issue = self.store.create()
        registry_path = self.root / "invitations" / "invitations.json"
        registry = json.loads(registry_path.read_text())
        registry["invitations"][issue.invitation["invite_id"]]["path"] = "../../escape.json"
        registry_path.write_text(json.dumps(registry))
        with self.assertRaisesRegex(InvitationError, "escapes identity directory"):
            self.store.get(issue.invitation["invite_id"])


if __name__ == "__main__":
    unittest.main()
