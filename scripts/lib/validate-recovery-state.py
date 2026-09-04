#!/usr/bin/env python3
"""Validate isolated Atlas recovery state through its consumer contracts."""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path


class RecoveryStateValidationError(RuntimeError):
    """Raised when staged recovery state is not consumable."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryStateValidationError(message)


def _json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryStateValidationError(f"invalid JSON: {path}") from exc


def _json_object(path: Path) -> dict[str, object]:
    value = _json(path)
    _require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def _safe_child(root: Path, relative: object, label: str) -> Path:
    _require(isinstance(relative, str) and relative, f"invalid {label} path")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise RecoveryStateValidationError(f"{label} path escapes staged root") from exc
    _require(candidate.is_file() and not candidate.is_symlink(), f"missing {label} file")
    return candidate


def _policies(root: Path) -> dict[str, str]:
    path = root / "RECOVERY_MANIFEST.tsv"
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
    except OSError as exc:
        raise RecoveryStateValidationError("recovery manifest is unreadable") from exc
    return {
        row["surface"]: row["policy"]
        for row in rows
        if row.get("surface")
    }


def _validate_users(root: Path) -> str:
    from atlas.user_profiles import UserProfileStore, validate_profile

    store = UserProfileStore(root)
    registry = store._load_registry()
    seen_users: set[str] = set()
    seen_emails: set[str] = set()
    for user_id, entry in registry["users"].items():
        profile_path = _safe_child(root, entry["profile"], f"user {user_id}")
        payload = _json_object(profile_path)
        profile = validate_profile(payload)
        _require(profile["user_id"] == user_id, f"user profile ID mismatch: {user_id}")
        _require(profile["username"] == entry["username"], f"user registry mismatch: {user_id}")
        _require(profile["status"] == entry["status"], f"user status mismatch: {user_id}")
        _require(profile["username"] not in seen_users, "duplicate staged username")
        seen_users.add(profile["username"])
        if profile["email"]:
            _require(profile["email"] not in seen_emails, "duplicate staged user email")
            seen_emails.add(profile["email"])
    return f"{len(registry['users'])} profiles"


def _validate_invitations(identity_root: Path) -> str:
    from atlas.identity import IdentityPaths
    from atlas.invitations import InvitationStore, validate_invitation

    store = InvitationStore(IdentityPaths(identity_root))
    registry = store._load_registry()
    seen_hashes: set[str] = set()
    for invite_id, entry in registry["invitations"].items():
        path = store._safe_registry_path(entry["path"], invite_id)
        _require(path.is_file() and not path.is_symlink(), f"missing invitation: {invite_id}")
        record = validate_invitation(_json_object(path))
        _require(record["invite_id"] == invite_id, f"invitation ID mismatch: {invite_id}")
        _require(record["status"] == entry["status"], f"invitation status mismatch: {invite_id}")
        _require(record["token_hash"] not in seen_hashes, "duplicate invitation token hash")
        seen_hashes.add(record["token_hash"])
    return f"{len(registry['invitations'])} invitations"


def _validate_favorites(identity_root: Path) -> str:
    from atlas.favorites import FavoriteStore, validate_favorite

    store = FavoriteStore(identity_root)
    registry = store._load_registry()
    relationships: set[tuple[str, str, str]] = set()
    for favorite_id, entry in registry["favorites"].items():
        path = store._safe_path(entry["path"], favorite_id)
        _require(path.is_file() and not path.is_symlink(), f"missing favorite: {favorite_id}")
        record = validate_favorite(_json_object(path))
        _require(record["favorite_id"] == favorite_id, f"favorite ID mismatch: {favorite_id}")
        for field in ("user_id", "provider", "item_id", "media_type"):
            _require(record[field] == entry[field], f"favorite registry mismatch: {favorite_id}")
        relationship = (record["user_id"], record["provider"], record["item_id"])
        _require(relationship not in relationships, "duplicate favorite relationship")
        relationships.add(relationship)
    return f"{len(registry['favorites'])} favorites"


def _validate_requests(root: Path) -> str:
    from atlas.media_requests.repository import JsonMediaRequestRepository

    requests = JsonMediaRequestRepository(root).list()
    return f"{len(requests)} requests"


def _validate_scheduler(path: Path) -> str:
    from atlas.scheduler import TaskScheduler

    payload = _json_object(path)
    _require(isinstance(payload.get("tasks"), dict), "scheduler tasks must be an object")
    _require(isinstance(payload.get("history"), list), "scheduler history must be a list")
    _require(
        all(isinstance(item, Mapping) for item in payload["history"]),
        "scheduler history entries must be objects",
    )
    tasks = TaskScheduler(path).list_tasks()
    return f"{len(tasks)} tasks"


def _validate_runtime(runtime_root: Path) -> str:
    event_path = runtime_root / "events.jsonl"
    try:
        lines = event_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RecoveryStateValidationError("runtime event journal is unreadable") from exc
    event_count = 0
    for line_number, line in enumerate(lines, start=1):
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RecoveryStateValidationError(
                f"invalid runtime event JSON at line {line_number}"
            ) from exc
        _require(isinstance(event, dict), f"runtime event must be an object at line {line_number}")
        _require(
            isinstance(event.get("event"), str) and bool(event["event"].strip()),
            f"runtime event name is invalid at line {line_number}",
        )
        event_count += 1

    subscriber_root = runtime_root / "subscribers"
    _require(subscriber_root.is_dir(), "runtime subscriber directory is unavailable")
    subscriber_count = 0
    for cursor in sorted(subscriber_root.glob("*.cursor")):
        name = cursor.stem
        _require(bool(re.fullmatch(r"[A-Za-z0-9._-]+", name)), f"invalid subscriber name: {name}")
        raw = cursor.read_text(encoding="utf-8").strip()
        _require(raw.isdigit(), f"invalid subscriber cursor: {name}")
        _require(int(raw) <= event_count, f"subscriber cursor exceeds journal: {name}")
        filter_path = subscriber_root / f"{name}.filter"
        if filter_path.exists():
            _require(filter_path.is_file() and not filter_path.is_symlink(), f"invalid subscriber filter: {name}")
            _require(bool(filter_path.read_text(encoding="utf-8").strip()), f"empty subscriber filter: {name}")
        subscriber_count += 1
    return f"{event_count} events, {subscriber_count} subscribers"


def _validate_retention(root: Path) -> str:
    from atlas.ari.analytics import ARIAnalytics
    from atlas.ari.service import ARIService

    service = ARIService(root)

    # The current report is authoritative when present and must satisfy the
    # current ARI model. Historical reports intentionally use the analytics
    # compatibility boundary, which records old/incompatible snapshots as
    # skipped instead of treating preserved history as current-state damage.
    if service.latest_path().is_file():
        service.latest()

    history = ARIAnalytics(service).load_history()
    return (
        f"{len(history.reports)} compatible reports, "
        f"{len(history.skipped)} legacy/incompatible skipped"
    )


def _load_sports_modules(project_root: Path, subscriptions: Path, recordings: Path):
    sports_source = project_root / "modules" / "sports" / "src"
    sys.path.insert(0, str(sports_source))
    os.environ["SPORTS_SUBSCRIPTIONS_FILE"] = str(subscriptions)
    os.environ["SPORTS_RECORDINGS_FILE"] = str(recordings)
    import subscriptions as sports_subscriptions
    import recordings as sports_recordings
    return sports_subscriptions, sports_recordings



def _validate_sports_live_tv_bindings(path: Path) -> str:
    import json

    if not path.is_file() or path.is_symlink():
        raise ValueError("Sports Live TV binding state is unavailable")

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Sports Live TV binding state is invalid JSON") from exc

    if not isinstance(document, dict):
        raise ValueError("Sports Live TV binding state root must be an object")
    if document.get("version") != 1:
        raise ValueError("Sports Live TV binding state version is invalid")

    bindings = document.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("Sports Live TV bindings must be an object")

    seen_jellyfin_ids: set[str] = set()
    for atlas_channel_id, entry in bindings.items():
        if (
            not isinstance(atlas_channel_id, str)
            or not atlas_channel_id.strip()
            or len(atlas_channel_id.strip()) > 256
        ):
            raise ValueError("Sports Live TV binding channel identity is invalid")
        if not isinstance(entry, dict):
            raise ValueError("Sports Live TV binding entry must be an object")
        if set(entry) != {"jellyfin_item_id"}:
            raise ValueError("Sports Live TV binding entry fields are invalid")

        jellyfin_item_id = entry.get("jellyfin_item_id")
        if (
            not isinstance(jellyfin_item_id, str)
            or not jellyfin_item_id.strip()
            or len(jellyfin_item_id.strip()) > 256
        ):
            raise ValueError("Sports Live TV Jellyfin identity is invalid")
        normalized = jellyfin_item_id.strip()
        if normalized in seen_jellyfin_ids:
            raise ValueError("Sports Live TV Jellyfin identity is duplicated")
        seen_jellyfin_ids.add(normalized)

    return f"{len(bindings)} bindings"


def validate(root: Path, project_root: Path) -> list[tuple[str, str, str]]:
    _require(root.is_dir() and not root.is_symlink(), "staged recovery root is invalid")
    policies = _policies(root)
    state = root / "state"
    identity = state / "identity"
    results: list[tuple[str, str, str]] = []

    results.append(("users", "PASS", _validate_users(state / "users")))

    if policies.get("identity-invitations") == "captured":
        results.append(("identity-invitations", "PASS", _validate_invitations(identity)))
    else:
        results.append(("identity-invitations", "SKIP", "absent optional"))

    results.append(("favorites", "PASS", _validate_favorites(identity)))

    if policies.get("requests") == "captured":
        results.append(("requests", "PASS", _validate_requests(state / "requests")))
    else:
        results.append(("requests", "SKIP", "absent optional"))

    results.append(("scheduler", "PASS", _validate_scheduler(state / "scheduler/tasks.json")))
    results.append(("runtime", "PASS", _validate_runtime(state / "runtime")))
    results.append(("retention", "PASS", _validate_retention(state / "retention")))

    subscriptions_path = state / "sports/subscriptions.json"
    recordings_path = state / "sports/recordings.json"
    sports_subscriptions, sports_recordings = _load_sports_modules(
        project_root, subscriptions_path, recordings_path
    )

    subscription_document = _json_object(subscriptions_path)
    raw_subscriptions = subscription_document.get("subscriptions")
    _require(isinstance(raw_subscriptions, list), "Sports subscriptions must be a list")
    _require(all(isinstance(item, dict) for item in raw_subscriptions), "Sports subscription entries must be objects")
    for subscription in raw_subscriptions:
        sports_subscriptions.normalize_subscription(subscription)
    loaded_subscriptions = sports_subscriptions.load_subscriptions()
    _require(loaded_subscriptions == raw_subscriptions, "Sports subscription loader changed staged state")
    results.append(("sports-subscriptions", "PASS", f"{len(raw_subscriptions)} subscriptions"))
    results.append(
        (
            "sports-live-tv-bindings",
            "PASS",
            _validate_sports_live_tv_bindings(
                state / "sports/live-tv-bindings.json"
            ),
        )
    )

    recording_document = _json_object(recordings_path)
    _require(all(isinstance(item, dict) for item in recording_document.values()), "Sports recording entries must be objects")
    loaded_recordings = sports_recordings.load_recordings()
    _require(loaded_recordings == recording_document, "Sports recording loader changed staged state")
    results.append(("sports-recordings", "PASS", f"{len(recording_document)} recordings"))

    _json_object(state / "sports/scheduler.json")
    results.append(("sports-scheduler", "PASS", "JSON object"))
    return results


def main() -> int:
    if len(sys.argv) != 3:
        print("ERROR: usage: validate-recovery-state.py <staging-root> <project-root>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    project_root = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(project_root))
    try:
        results = validate(root, project_root)
    except Exception as exc:
        # Validation is a fail-closed CLI boundary. Consumer-specific errors
        # are reported uniformly rather than escaping as Python tracebacks.
        print(f"ERROR: staged recovery consumer validation failed: {exc}", file=sys.stderr)
        return 1
    for surface, status, detail in results:
        print(f"{status:<4} {surface:<24} {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
