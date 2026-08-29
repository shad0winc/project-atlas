"""Atomic filesystem publication for Service Lifecycle snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Mapping, Any

from .models import ServiceLifecycleError


RUNTIME_DIRECTORY_MODE = 0o750
RUNTIME_FILE_MODE = 0o640
RUNTIME_OWNER_UID = 0
RUNTIME_GROUP_GID = 20000


def publish_runtime_snapshot(
    payload: Mapping[str, Any],
    destination: str | Path,
) -> Path:
    """Atomically publish one bounded Service Lifecycle snapshot."""

    if not isinstance(payload, Mapping):
        raise ServiceLifecycleError(
            "runtime snapshot payload must be a mapping"
        )

    if not isinstance(destination, (str, Path)):
        raise TypeError(
            "destination must be a path"
        )

    target = Path(destination).expanduser()
    directory = target.parent

    if not target.name:
        raise ServiceLifecycleError(
            "runtime snapshot destination must name a file"
        )

    if not directory.exists():
        try:
            directory.mkdir()
        except OSError as exc:
            raise ServiceLifecycleError(
                "unable to create Service Lifecycle "
                "runtime directory"
            ) from exc

    if not directory.is_dir():
        raise ServiceLifecycleError(
            "Service Lifecycle runtime directory "
            "is not a directory"
        )

    try:
        os.chown(
            directory,
            RUNTIME_OWNER_UID,
            RUNTIME_GROUP_GID,
        )
        os.chmod(
            directory,
            RUNTIME_DIRECTORY_MODE,
        )
    except OSError as exc:
        raise ServiceLifecycleError(
            "unable to secure Service Lifecycle "
            "runtime directory"
        ) from exc

    temporary_path: Path | None = None

    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            dir=directory,
        )

        temporary_path = Path(temporary_name)

        try:
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
            ) as stream:
                json.dump(
                    payload,
                    stream,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())

                os.fchown(
                    stream.fileno(),
                    RUNTIME_OWNER_UID,
                    RUNTIME_GROUP_GID,
                )
                os.fchmod(
                    stream.fileno(),
                    RUNTIME_FILE_MODE,
                )

            os.replace(
                temporary_path,
                target,
            )

            temporary_path = None

            _sync_directory(directory)

        except Exception:
            raise

    except (
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        raise ServiceLifecycleError(
            "unable to publish Service Lifecycle "
            "runtime snapshot"
        ) from exc

    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            try:
                temporary_path.unlink()
            except OSError:
                pass

    return target


def _sync_directory(
    directory: Path,
) -> None:
    """Persist the atomic directory-entry replacement when supported."""

    flags = os.O_RDONLY

    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY

    descriptor = os.open(
        directory,
        flags,
    )

    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
