from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import tempfile
from typing import Any


STATE_VERSION = 1


class DispatcharrChannelBindingError(
    ValueError
):
    """Dispatcharr channel binding state is invalid."""


@dataclass(frozen=True, slots=True)
class DispatcharrChannelBinding:
    atlas_channel_id: str
    dispatcharr_channel_id: int
    dispatcharr_channel_uuid: str

    def safe_dict(
        self,
    ) -> dict[str, object]:
        return {
            "atlas_channel_id": (
                self.atlas_channel_id
            ),
            "dispatcharr_channel_id": (
                self.dispatcharr_channel_id
            ),
            "dispatcharr_channel_uuid": (
                self.dispatcharr_channel_uuid
            ),
        }


def _required_identifier(
    value: object,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise DispatcharrChannelBindingError(
            f"{field} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise DispatcharrChannelBindingError(
            f"{field} is required"
        )

    if len(normalized) > 256:
        raise DispatcharrChannelBindingError(
            f"{field} exceeds 256 characters"
        )

    if any(
        ord(character) < 32
        for character in normalized
    ):
        raise DispatcharrChannelBindingError(
            f"{field} contains control characters"
        )

    return normalized


def _positive_identifier(
    value: object,
    field: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise DispatcharrChannelBindingError(
            f"{field} must be a positive integer"
        )

    return value


def _reject_duplicate_keys(
    pairs: list[
        tuple[str, Any]
    ],
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for key, value in pairs:
        if key in result:
            raise DispatcharrChannelBindingError(
                "duplicate JSON object key: "
                f"{key}"
            )

        result[key] = value

    return result


class DispatcharrChannelBindingRegistry:
    """Durable Atlas-to-Dispatcharr channel identity state."""

    def __init__(
        self,
        path: str | os.PathLike[str],
    ) -> None:
        self.path = Path(path)
        self.lock_path = Path(
            f"{self.path}.lock"
        )

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "bindings": {},
        }

    def _validate_paths(
        self,
    ) -> None:
        if self.path.is_symlink():
            raise DispatcharrChannelBindingError(
                "Dispatcharr channel binding state "
                "must not be a symlink"
            )

        if self.lock_path.is_symlink():
            raise DispatcharrChannelBindingError(
                "Dispatcharr channel binding lock "
                "must not be a symlink"
            )

    def _load(
        self,
    ) -> dict[str, Any]:
        self._validate_paths()

        if not self.path.exists():
            return self._empty()

        try:
            raw = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                ),
                object_pairs_hook=(
                    _reject_duplicate_keys
                ),
            )
        except DispatcharrChannelBindingError:
            raise
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise DispatcharrChannelBindingError(
                "Dispatcharr channel binding state "
                "could not be read"
            ) from error

        if not isinstance(raw, dict):
            raise DispatcharrChannelBindingError(
                "Dispatcharr channel binding state "
                "root must be an object"
            )

        if set(raw) != {
            "version",
            "bindings",
        }:
            raise DispatcharrChannelBindingError(
                "Dispatcharr channel binding state "
                "contains unsupported fields"
            )

        if raw.get("version") != STATE_VERSION:
            raise DispatcharrChannelBindingError(
                "unsupported Dispatcharr channel "
                "binding state version"
            )

        bindings = raw.get(
            "bindings"
        )

        if not isinstance(bindings, dict):
            raise DispatcharrChannelBindingError(
                "Dispatcharr channel bindings "
                "must be an object"
            )

        normalized: dict[
            str,
            dict[str, object],
        ] = {}

        seen_channel_ids: set[int] = set()
        seen_channel_uuids: set[str] = set()

        for (
            atlas_channel_id_raw,
            entry,
        ) in bindings.items():
            atlas_channel_id = (
                _required_identifier(
                    atlas_channel_id_raw,
                    "atlas_channel_id",
                )
            )

            if not isinstance(entry, dict):
                raise DispatcharrChannelBindingError(
                    "Dispatcharr channel binding "
                    "entries must be objects"
                )

            if set(entry) != {
                "dispatcharr_channel_id",
                "dispatcharr_channel_uuid",
            }:
                raise DispatcharrChannelBindingError(
                    "Dispatcharr channel binding "
                    "entry contains unsupported fields"
                )

            dispatcharr_channel_id = (
                _positive_identifier(
                    entry.get(
                        "dispatcharr_channel_id"
                    ),
                    "dispatcharr_channel_id",
                )
            )

            dispatcharr_channel_uuid = (
                _required_identifier(
                    entry.get(
                        "dispatcharr_channel_uuid"
                    ),
                    "dispatcharr_channel_uuid",
                )
            )

            if (
                dispatcharr_channel_id
                in seen_channel_ids
            ):
                raise DispatcharrChannelBindingError(
                    "one Dispatcharr channel ID cannot "
                    "bind to multiple Atlas channels"
                )

            if (
                dispatcharr_channel_uuid
                in seen_channel_uuids
            ):
                raise DispatcharrChannelBindingError(
                    "one Dispatcharr channel UUID cannot "
                    "bind to multiple Atlas channels"
                )

            seen_channel_ids.add(
                dispatcharr_channel_id
            )
            seen_channel_uuids.add(
                dispatcharr_channel_uuid
            )

            normalized[
                atlas_channel_id
            ] = {
                "dispatcharr_channel_id": (
                    dispatcharr_channel_id
                ),
                "dispatcharr_channel_uuid": (
                    dispatcharr_channel_uuid
                ),
            }

        return {
            "version": STATE_VERSION,
            "bindings": normalized,
        }

    def _write_locked(
        self,
        document: dict[str, Any],
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_name: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = (
                    temporary.name
                )

                json.dump(
                    document,
                    temporary,
                    indent=2,
                    sort_keys=True,
                )

                temporary.write("\n")
                temporary.flush()
                os.fsync(
                    temporary.fileno()
                )

            os.chmod(
                temporary_name,
                0o600,
            )

            os.replace(
                temporary_name,
                self.path,
            )

            temporary_name = None

            os.chmod(
                self.path,
                0o600,
            )

        finally:
            if temporary_name is not None:
                try:
                    Path(
                        temporary_name
                    ).unlink()
                except FileNotFoundError:
                    pass

    def _exclusive_lock(
        self,
    ):
        self._validate_paths()

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        lock_fd = os.open(
            self.lock_path,
            os.O_RDWR
            | os.O_CREAT,
            0o600,
        )

        os.chmod(
            self.lock_path,
            0o600,
        )

        return os.fdopen(
            lock_fd,
            "r+",
            encoding="utf-8",
        )

    def ensure(
        self,
    ) -> None:
        with self._exclusive_lock() as lock:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                if self.path.exists():
                    self._load()
                    return

                self._write_locked(
                    self._empty()
                )

            finally:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_UN,
                )

    def list_bindings(
        self,
    ) -> tuple[
        DispatcharrChannelBinding,
        ...,
    ]:
        document = self._load()

        return tuple(
            DispatcharrChannelBinding(
                atlas_channel_id=(
                    atlas_channel_id
                ),
                dispatcharr_channel_id=int(
                    entry[
                        "dispatcharr_channel_id"
                    ]
                ),
                dispatcharr_channel_uuid=str(
                    entry[
                        "dispatcharr_channel_uuid"
                    ]
                ),
            )
            for atlas_channel_id, entry
            in sorted(
                document[
                    "bindings"
                ].items()
            )
        )

    def resolve(
        self,
        atlas_channel_id: str,
    ) -> DispatcharrChannelBinding | None:
        normalized_atlas_id = (
            _required_identifier(
                atlas_channel_id,
                "atlas_channel_id",
            )
        )

        entry = self._load()[
            "bindings"
        ].get(
            normalized_atlas_id
        )

        if entry is None:
            return None

        return DispatcharrChannelBinding(
            atlas_channel_id=(
                normalized_atlas_id
            ),
            dispatcharr_channel_id=int(
                entry[
                    "dispatcharr_channel_id"
                ]
            ),
            dispatcharr_channel_uuid=str(
                entry[
                    "dispatcharr_channel_uuid"
                ]
            ),
        )

    def set(
        self,
        atlas_channel_id: str,
        dispatcharr_channel_id: int,
        dispatcharr_channel_uuid: str,
    ) -> DispatcharrChannelBinding:
        normalized_atlas_id = (
            _required_identifier(
                atlas_channel_id,
                "atlas_channel_id",
            )
        )

        normalized_channel_id = (
            _positive_identifier(
                dispatcharr_channel_id,
                "dispatcharr_channel_id",
            )
        )

        normalized_channel_uuid = (
            _required_identifier(
                dispatcharr_channel_uuid,
                "dispatcharr_channel_uuid",
            )
        )

        with self._exclusive_lock() as lock:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                document = self._load()

                for (
                    other_atlas_id,
                    entry,
                ) in document[
                    "bindings"
                ].items():
                    if (
                        other_atlas_id
                        != normalized_atlas_id
                        and entry[
                            "dispatcharr_channel_id"
                        ]
                        == normalized_channel_id
                    ):
                        raise (
                            DispatcharrChannelBindingError(
                                "Dispatcharr channel ID "
                                "is already bound to "
                                "another Atlas channel"
                            )
                        )

                    if (
                        other_atlas_id
                        != normalized_atlas_id
                        and entry[
                            "dispatcharr_channel_uuid"
                        ]
                        == normalized_channel_uuid
                    ):
                        raise (
                            DispatcharrChannelBindingError(
                                "Dispatcharr channel UUID "
                                "is already bound to "
                                "another Atlas channel"
                            )
                        )

                document[
                    "bindings"
                ][normalized_atlas_id] = {
                    "dispatcharr_channel_id": (
                        normalized_channel_id
                    ),
                    "dispatcharr_channel_uuid": (
                        normalized_channel_uuid
                    ),
                }

                self._write_locked(
                    document
                )

            finally:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_UN,
                )

        return DispatcharrChannelBinding(
            atlas_channel_id=(
                normalized_atlas_id
            ),
            dispatcharr_channel_id=(
                normalized_channel_id
            ),
            dispatcharr_channel_uuid=(
                normalized_channel_uuid
            ),
        )

    def delete(
        self,
        atlas_channel_id: str,
    ) -> bool:
        normalized_atlas_id = (
            _required_identifier(
                atlas_channel_id,
                "atlas_channel_id",
            )
        )

        with self._exclusive_lock() as lock:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                document = self._load()

                if (
                    normalized_atlas_id
                    not in document[
                        "bindings"
                    ]
                ):
                    return False

                del document[
                    "bindings"
                ][normalized_atlas_id]

                self._write_locked(
                    document
                )

                return True

            finally:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_UN,
                )


def default_dispatcharr_channel_binding_registry(
) -> DispatcharrChannelBindingRegistry:
    return DispatcharrChannelBindingRegistry(
        os.getenv(
            "SPORTS_DISPATCHARR_CHANNEL_BINDINGS_FILE",
            (
                "/mnt/storage/configs/"
                "sportyfin/state/"
                "dispatcharr-channel-bindings.json"
            ),
        )
    )


__all__ = [
    "DispatcharrChannelBinding",
    "DispatcharrChannelBindingError",
    "DispatcharrChannelBindingRegistry",
    "default_dispatcharr_channel_binding_registry",
]
