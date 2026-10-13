"""Durable ownership of explicitly opened Jellyfin live streams.

Ambiguous network outcomes are latched for operator reconciliation. They
are never retried automatically: Jellyfin may share a stream ID between
consumers, so repeating an uncertain close can affect another consumer.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import stat
import fcntl
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Callable, Iterator

from atlas.media.provider import MediaProviderError


class LiveStreamOwnershipError(MediaProviderError):
    pass


@dataclass(frozen=True)
class JellyfinProcessRetirement:
    """Evidence returned by a trusted, quiesced host-side verifier.

    This is an internal operator contract, not a client-supplied authorization
    token. The verifier must establish process retirement and upstream closure;
    quiet Sessions output or zero counters alone do not establish those facts.
    """

    old_generation: str
    new_generation: str
    old_started_at: float
    new_started_at: float
    observed_at: float
    old_process_absent: bool
    new_provider_healthy: bool
    admission_quiesced: bool
    native_upstream_closed: bool
    native_consumers_absent: bool


class OwnedJellyfinLiveStreams:
    def __init__(
        self,
        path: Path,
        *,
        ttl_seconds: int = 90,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.clock = clock

    @contextmanager
    def _locked(self) -> Iterator[dict]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                state = (
                    json.loads(self.path.read_text())
                    if self.path.exists()
                    else {"version": 1, "streams": {}}
                )
            except (OSError, ValueError) as exc:
                raise LiveStreamOwnershipError(
                    "Live stream ownership is unavailable"
                ) from exc
            if (
                not isinstance(state, dict)
                or set(state) != {"version", "streams"}
                or state["version"] != 1
                or not isinstance(state["streams"], dict)
            ):
                raise LiveStreamOwnershipError("Live stream ownership is invalid")
            for key, row in state["streams"].items():
                if (
                    not isinstance(key, str)
                    or not isinstance(row, dict)
                    or set(row)
                    != {
                        "user_id",
                        "item_id",
                        "last_seen",
                        "status",
                        "live_stream_id",
                        "play_session_id",
                        "media_source_id",
                    }
                ):
                    raise LiveStreamOwnershipError("Live stream ownership is invalid")
                if (
                    row["status"] not in {"opening", "active", "closing", "blocked"}
                    or not all(
                        isinstance(row[k], str) and row[k]
                        for k in ("user_id", "item_id")
                    )
                    or isinstance(row["last_seen"], bool)
                    or not isinstance(row["last_seen"], (int, float))
                    or not math.isfinite(row["last_seen"])
                ):
                    raise LiveStreamOwnershipError("Live stream ownership is invalid")
                if row["live_stream_id"] is not None and (
                    not isinstance(row["live_stream_id"], str)
                    or not row["live_stream_id"]
                ):
                    raise LiveStreamOwnershipError("Live stream ownership is invalid")
                if (
                    row["status"] in {"active", "closing"}
                    and row["live_stream_id"] is None
                ):
                    raise LiveStreamOwnershipError("Live stream ownership is invalid")
            yield state

    def _write(self, state: dict) -> None:
        previous = self.path.stat(follow_symlinks=False) if self.path.exists() else None
        if previous is not None and not stat.S_ISREG(previous.st_mode):
            raise LiveStreamOwnershipError("Live stream ownership path is invalid")
        fd, name = tempfile.mkstemp(prefix=".live-streams.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as out:
                if previous is not None:
                    current = os.fstat(out.fileno())
                    if (current.st_uid, current.st_gid) != (previous.st_uid, previous.st_gid):
                        os.fchown(out.fileno(), previous.st_uid, previous.st_gid)
                os.fchmod(out.fileno(), 0o600)
                json.dump(state, out, separators=(",", ":"), sort_keys=True)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, self.path)
            fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @contextmanager
    def scope(
        self,
        *,
        session_id: str,
        user_id: str,
        item_id: str,
        close: Callable[[str], None],
        stop_transcode: Callable[[str], None] | None = None,
    ) -> Iterator[LiveStreamOwner]:
        if not all(
            isinstance(v, str) and v.strip() for v in (session_id, user_id, item_id)
        ):
            raise LiveStreamOwnershipError("Live stream owner is required")
        owner = LiveStreamOwner(self, session_id, user_id, item_id)
        try:
            yield owner
        except Exception:
            # Known successful opens can be closed; ambiguous opens stay latched.
            self.release(
                session_id=session_id, user_id=user_id, close=close,
                stop_transcode=stop_transcode,
            )
            raise

    def open(
        self,
        owner: LiveStreamOwner,
        operation: Callable[[], dict],
        *,
        play_session_id: str | None = None,
        media_source_id: str | None = None,
    ) -> dict:
        with self._locked() as state:
            streams = state["streams"]
            if owner.session_id in streams or any(
                r["status"] != "active"
                or self.clock() - r["last_seen"] >= self.ttl_seconds
                for r in streams.values()
            ):
                raise LiveStreamOwnershipError(
                    "Live stream cleanup requires reconciliation"
                )
            row = dict(
                user_id=owner.user_id,
                item_id=owner.item_id,
                last_seen=self.clock(),
                status="opening",
                live_stream_id=None,
                play_session_id=play_session_id,
                media_source_id=media_source_id,
            )
            streams[owner.session_id] = row
            self._write(state)  # Write-ahead intent precedes the remote mutation.
            try:
                response = operation()
                source = (
                    response.get("MediaSource") if isinstance(response, dict) else None
                )
                stream_id = (
                    source.get("LiveStreamId") if isinstance(source, dict) else None
                )
                if not isinstance(stream_id, str) or not stream_id.strip():
                    raise LiveStreamOwnershipError(
                        "Jellyfin returned no opened live stream identity"
                    )
                row.update(
                    status="active",
                    live_stream_id=stream_id.strip(),
                    last_seen=self.clock(),
                )
                self._write(
                    state
                )  # Ownership is durable before URL validation/capability creation.
                return response
            except Exception:
                row["status"] = "blocked"
                self._write(state)
                raise

    def reconcile_failed_open_after_retirement(
        self,
        *,
        session_id: str,
        user_id: str,
        item_id: str,
        expected_sha256: str,
        backup_file: Path,
        receipt_file: Path,
        verify_retirement: Callable[[dict], JellyfinProcessRetirement],
    ) -> None:
        """Retire one unidentified blocked open after verified provider retirement.

        Admission and the scheduler must be quiesced by the trusted caller.
        Known stream IDs, uncertain closes, or multiple owners are excluded.
        The caller releases the exact linked session/lease only after success,
        using their existing ownership APIs. No provider open/close is issued.
        """
        if not all(isinstance(value, str) and value.strip()
                   for value in (session_id, user_id, item_id)):
            raise LiveStreamOwnershipError("Recovery ownership is required")
        if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
                or any(value not in "0123456789abcdef" for value in expected_sha256)):
            raise LiveStreamOwnershipError("Recovery digest is invalid")

        def verify(row: dict) -> JellyfinProcessRetirement:
            try:
                evidence = verify_retirement(dict(row))
            except Exception as exc:
                raise LiveStreamOwnershipError("Provider retirement is unverified") from exc
            if not isinstance(evidence, JellyfinProcessRetirement):
                raise LiveStreamOwnershipError("Provider retirement evidence is invalid")
            if not all(isinstance(value, str) and value.strip() and len(value) <= 512
                       for value in (evidence.old_generation, evidence.new_generation)):
                raise LiveStreamOwnershipError("Provider generation identity is invalid")
            times = (evidence.old_started_at, evidence.new_started_at,
                     evidence.observed_at, self.clock())
            if not all(not isinstance(value, bool) and isinstance(value, (int, float))
                       and math.isfinite(value) for value in times):
                raise LiveStreamOwnershipError("Provider retirement timestamp is invalid")
            if (evidence.old_generation == evidence.new_generation
                    or not (0 <= times[0] <= row["last_seen"] < times[1] <= times[2] <= times[3])
                    or times[3] - times[2] > 30
                    or any(value is not True for value in (
                        evidence.old_process_absent, evidence.new_provider_healthy,
                        evidence.admission_quiesced, evidence.native_upstream_closed,
                        evidence.native_consumers_absent))):
                raise LiveStreamOwnershipError("Provider retirement is unverified")
            return evidence

        def archive(path: Path, raw: bytes) -> None:
            if (not isinstance(path, Path) or not path.is_absolute()
                    or path in (self.path.absolute(), Path(str(self.path.absolute()) + ".lock"))
                    or path.parent.resolve() != path.parent
                    or not path.parent.is_dir()
                    or path.parent.stat().st_uid != os.geteuid()
                    or stat.S_IMODE(path.parent.stat().st_mode) & 0o077):
                raise LiveStreamOwnershipError("Private recovery archive directory is required")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(raw)
                out.flush()
                os.fsync(out.fileno())
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

        if backup_file == receipt_file:
            raise LiveStreamOwnershipError("Recovery archives must be distinct")
        with self._locked() as state:
            if not self.path.is_file() or self.path.is_symlink() or self.path.stat().st_nlink != 1:
                raise LiveStreamOwnershipError("Recovery registry must not be a symlink")
            raw = self.path.read_bytes()
            if len(raw) > 8 * 1024**2 or hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise LiveStreamOwnershipError("Recovery registry changed")
            row = state["streams"].get(session_id)
            if (len(state["streams"]) != 1 or row is None
                    or row["user_id"] != user_id or row["item_id"] != item_id
                    or row["status"] != "blocked" or row["live_stream_id"] is not None
                    or not all(isinstance(row[key], str) and row[key].strip()
                               for key in ("play_session_id", "media_source_id"))):
                raise LiveStreamOwnershipError("Unidentified failed-open recovery is unavailable")
            if json.loads(raw) != state:
                raise LiveStreamOwnershipError("Recovery registry changed")
            evidence = verify(row)
            archive(backup_file, raw)
            receipt = {
                "version": 1,
                "status": "prepared",
                "operation": "retire_unidentified_failed_open",
                "registry_before_sha256": expected_sha256,
                "registry_after_sha256": hashlib.sha256(
                    b'{"streams":{},"version":1}'
                ).hexdigest(),
                "session_reference_sha256": hashlib.sha256(session_id.encode()).hexdigest(),
                "provider_retirement": asdict(evidence),
                "backup_file": str(backup_file),
            }
            archive(receipt_file, json.dumps(receipt, sort_keys=True).encode())
            confirmed = verify(row)
            first, second = asdict(evidence), asdict(confirmed)
            first.pop("observed_at")
            second.pop("observed_at")
            if first != second or self.path.read_bytes() != raw:
                raise LiveStreamOwnershipError("Recovery evidence changed before commit")
            del state["streams"][session_id]
            self._write(state)

    def heartbeat(self, *, session_id: str, user_id: str) -> None:
        with self._locked() as state:
            row = state["streams"].get(session_id)
            if row is None:
                return  # Live sources that do not require opening have no record.
            if row["user_id"] != user_id or row["status"] != "active":
                raise LiveStreamOwnershipError("Live stream owner is unavailable")
            if self.clock() - row["last_seen"] >= self.ttl_seconds:
                raise LiveStreamOwnershipError("Live stream owner has expired")
            row["last_seen"] = self.clock()
            self._write(state)

    def _close(
        self, state: dict, key: str, close: Callable[[str], None],
        stop_transcode: Callable[[str], None] | None,
    ) -> None:
        row = state["streams"][key]
        if row["status"] != "active":
            raise LiveStreamOwnershipError(
                "Live stream cleanup requires reconciliation"
            )
        row["status"] = "closing"
        self._write(state)
        try:
            if stop_transcode is not None:
                # Stop the exact job before releasing its consumer. Otherwise its
                # delayed kill timer can close a newly opened shared stream ID.
                play_session_id = row["play_session_id"]
                if not isinstance(play_session_id, str) or not play_session_id.strip():
                    raise LiveStreamOwnershipError("Live transcode identity is required")
                stop_transcode(play_session_id)
            close(row["live_stream_id"])
        except Exception as exc:
            row["status"] = "blocked"
            self._write(state)
            raise LiveStreamOwnershipError(
                "Live stream cleanup outcome requires reconciliation"
            ) from exc
        del state["streams"][key]
        self._write(state)

    def release(
        self, *, session_id: str, user_id: str, close: Callable[[str], None],
        stop_transcode: Callable[[str], None] | None = None,
    ) -> bool:
        with self._locked() as state:
            row = state["streams"].get(session_id)
            if row is None:
                return False
            if row["user_id"] != user_id:
                raise LiveStreamOwnershipError("Live stream owner is unavailable")
            self._close(state, session_id, close, stop_transcode)
            return True

    def authorize(
        self,
        *,
        user_id: str,
        item_id: str,
        live_stream_id: str,
        play_session_id: str | None = None,
        media_source_id: str | None = None,
    ) -> None:
        with self._locked() as state:
            if not any(
                row["user_id"] == user_id
                and row["item_id"].replace("-", "").lower()
                == item_id.replace("-", "").lower()
                and row["live_stream_id"] == live_stream_id
                and row["status"] == "active"
                and row["play_session_id"] == play_session_id
                and row["media_source_id"] == media_source_id
                and self.clock() - row["last_seen"] < self.ttl_seconds
                for row in state["streams"].values()
            ):
                raise LiveStreamOwnershipError("Live stream owner is unavailable")

    def reap(
        self, close: Callable[[str], None], *,
        stop_transcode: Callable[[str], None] | None = None,
    ) -> int:
        with self._locked() as state:
            if any(row["status"] != "active" for row in state["streams"].values()):
                raise LiveStreamOwnershipError(
                    "Live stream cleanup requires reconciliation"
                )
            expired = [
                key
                for key, row in state["streams"].items()
                if row["status"] == "active"
                and self.clock() - row["last_seen"] >= self.ttl_seconds
            ]
            completed = 0
            for key in expired:
                self._close(state, key, close, stop_transcode)
                completed += 1
            return completed


class LiveStreamOwner:
    def __init__(
        self,
        store: OwnedJellyfinLiveStreams,
        session_id: str,
        user_id: str,
        item_id: str,
    ) -> None:
        self.store, self.session_id, self.user_id, self.item_id = (
            store,
            session_id,
            user_id,
            item_id,
        )

    def open(self, operation: Callable[[], dict], **identities: str) -> dict:
        return self.store.open(self, operation, **identities)
