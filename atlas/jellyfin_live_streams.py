"""Durable ownership of explicitly opened Jellyfin live streams.

Ambiguous network outcomes are latched for operator reconciliation. They
are never retried automatically: Jellyfin may share a stream ID between
consumers, so repeating an uncertain close can affect another consumer.
"""

from __future__ import annotations

from contextlib import contextmanager
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
        fd, name = tempfile.mkstemp(prefix=".live-streams.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as out:
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
