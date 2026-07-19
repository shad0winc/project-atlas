from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path

from atlas.identity import IdentityPaths
from atlas.invitations import InvitationStore
from atlas.registration import RegistrationError, RegistrationService
from atlas.user_profiles import UserProfileStore


class FixedClock:
    def __call__(self) -> datetime:
        return datetime(2026, 7, 19, 20, 0, tzinfo=timezone.utc)


class FakeProvisioner:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.deleted: list[str] = []
        self.fail_create = False
        self.fail_delete = False

    def create_user(self, **values: object) -> str:
        self.created.append(values)
        if self.fail_create:
            raise RuntimeError("Jellyfin unavailable")
        return "a" * 32

    def delete_user(self, user_id: str) -> None:
        self.deleted.append(user_id)
        if self.fail_delete:
            raise RuntimeError("delete failed")


class RegistrationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.invitations = InvitationStore(IdentityPaths(root / "identity"), FixedClock())
        self.profiles = UserProfileStore(root / "users")
        self.provisioner = FakeProvisioner()
        self.events: list[tuple[str, dict[str, object]]] = []
        self.service = RegistrationService(
            self.invitations,
            self.profiles,
            self.provisioner,
            lambda name, payload: self.events.append((name, dict(payload))),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def issue(self, **values: object):
        return self.invitations.create(**values)

    def test_success_creates_linked_profile_completes_invite_and_publishes_event(self) -> None:
        issue = self.issue(email="friend@example.com", role="user")
        result = self.service.register(
            token=issue.token,
            username="friend",
            password="not-stored",
            display_name="Friend",
        )
        self.assertEqual(result.profile["jellyfin_user_id"], "a" * 32)
        self.assertEqual(result.profile["email"], "friend@example.com")
        self.assertEqual(result.invitation["status"], "completed")
        self.assertEqual(result.invitation["completed_by"], result.profile["user_id"])
        self.assertEqual(result.event_error, None)
        self.assertEqual(self.provisioner.created[0]["password"], "not-stored")
        self.assertEqual(self.events[0][0], "identity.registration.completed")
        self.assertNotIn("password", self.events[0][1])

    def test_invalid_token_does_not_provision(self) -> None:
        with self.assertRaisesRegex(RegistrationError, "invalid invitation token"):
            self.service.register(token="bad", username="friend", password="secret")
        self.assertEqual(self.provisioner.created, [])

    def test_invitation_email_must_match(self) -> None:
        issue = self.issue(email="friend@example.com")
        with self.assertRaisesRegex(RegistrationError, "does not match"):
            self.service.register(
                token=issue.token,
                username="friend",
                password="secret",
                email="other@example.com",
            )
        self.assertEqual(self.provisioner.created, [])

    def test_provisioning_failure_leaves_invitation_pending(self) -> None:
        issue = self.issue()
        self.provisioner.fail_create = True
        with self.assertRaisesRegex(RegistrationError, "Jellyfin unavailable"):
            self.service.register(token=issue.token, username="friend", password="secret")
        self.assertEqual(self.invitations.get(issue.invitation["invite_id"])["status"], "pending")
        self.assertEqual(self.profiles.list_users(), [])

    def test_profile_failure_deletes_external_user_and_preserves_invitation(self) -> None:
        issue = self.issue()
        self.profiles.create_user("friend")
        with self.assertRaisesRegex(RegistrationError, "username already exists"):
            self.service.register(token=issue.token, username="friend", password="secret")
        self.assertEqual(self.provisioner.deleted, ["a" * 32])
        self.assertEqual(self.invitations.get(issue.invitation["invite_id"])["status"], "pending")

    def test_completion_failure_rolls_back_profile_and_external_user(self) -> None:
        issue = self.issue()
        failing_invitations = mock.Mock(wraps=self.invitations)
        failing_invitations.complete.side_effect = RuntimeError("archive failed")
        service = RegistrationService(
            failing_invitations, self.profiles, self.provisioner
        )
        with self.assertRaisesRegex(RegistrationError, "archive failed"):
            service.register(token=issue.token, username="friend", password="secret")
        self.assertEqual(self.profiles.list_users(), [])
        self.assertEqual(self.provisioner.deleted, ["a" * 32])
        self.assertEqual(self.invitations.get(issue.invitation["invite_id"])["status"], "pending")

    def test_event_failure_does_not_rollback_successful_registration(self) -> None:
        issue = self.issue()
        service = RegistrationService(
            self.invitations,
            self.profiles,
            self.provisioner,
            lambda _name, _payload: (_ for _ in ()).throw(RuntimeError("event offline")),
        )
        result = service.register(token=issue.token, username="friend", password="secret")
        self.assertEqual(result.event_error, "event offline")
        self.assertEqual(len(self.profiles.list_users()), 1)
        self.assertEqual(result.invitation["status"], "completed")

    def test_password_is_required(self) -> None:
        issue = self.issue()
        with self.assertRaisesRegex(RegistrationError, "password is required"):
            self.service.register(token=issue.token, username="friend", password="")


class UserProfileDeletionTests(unittest.TestCase):
    def test_delete_user_removes_profile_and_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = UserProfileStore(Path(temporary_directory) / "users")
            profile = store.create_user("friend")
            deleted = store.delete_user(profile["user_id"])
            self.assertEqual(deleted, profile)
            self.assertEqual(store.list_users(), [])


if __name__ == "__main__":
    unittest.main()
