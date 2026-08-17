"""Immutable repository for Atlas sustained-use samples."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Final, Protocol

from atlas.atomic import write_json_atomic

from .models import (
    SustainedUseModelError,
    SustainedUseSample,
    SustainedUseSession,
)


DEFAULT_SUSTAINED_USE_DIRECTORY: Final = Path(
    "/mnt/storage/configs/atlas/sustained-use",
)


class SustainedUseRepositoryError(RuntimeError):
    """Raised when sustained-use persistence cannot complete safely."""


class SustainedUseSampleNotFoundError(
    SustainedUseRepositoryError,
):
    """Raised when requested sustained-use evidence does not exist."""


class SustainedUseRepository(Protocol):
    """Persistence contract for immutable sustained-use samples."""

    def save(
        self,
        sample: SustainedUseSample,
    ) -> Path:
        """Persist one immutable sample."""

        ...

    def latest(self) -> SustainedUseSample:
        """Return the latest persisted sample."""

        ...

    def history(
        self,
        limit: int = 25,
    ) -> tuple[SustainedUseSample, ...]:
        """Return persisted samples newest first."""

        ...



    def create_session(
        self,
        session: SustainedUseSession,
    ) -> Path:
        """Create the durable Q.6 session boundary."""

        ...

    def session(self) -> SustainedUseSession:
        """Return the current durable Q.6 session."""

        ...

    def update_session(
        self,
        session: SustainedUseSession,
    ) -> Path:
        """Atomically update lifecycle state for the same run."""

        ...


    def archive_session(
        self,
        session: SustainedUseSession,
    ) -> Path:
        """Archive one terminal Q.6 run and reopen the active root."""

        ...


class FileSustainedUseRepository:
    """Persist sustained-use samples as atomic JSON files."""

    def __init__(
        self,
        root: str | Path = DEFAULT_SUSTAINED_USE_DIRECTORY,
    ) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        """Return the configured repository root."""

        return self._root

    @property
    def history_directory(self) -> Path:
        """Return the immutable history directory."""

        return self.root / "history"

    @property
    def latest_path(self) -> Path:
        """Return the latest-sample path."""

        return self.root / "latest.json"

    @property
    def session_path(self) -> Path:
        """Return the durable session lifecycle path."""

        return self.root / "session.json"

    @property
    def archive_directory(self) -> Path:
        """Return the immutable completed-run archive directory."""

        return self.root / "archive"

    def _archive_path(
        self,
        run_id: str,
    ) -> Path:
        """Return the archive path for one safe run identity."""

        if (
            not isinstance(run_id, str)
            or not run_id.strip()
        ):
            raise SustainedUseRepositoryError(
                "run_id must be a non-empty string",
            )

        normalized = run_id.strip()

        if (
            Path(normalized).name != normalized
            or normalized in {".", ".."}
        ):
            raise SustainedUseRepositoryError(
                "run_id is not safe for archive storage",
            )

        return self.archive_directory / normalized

    def create_session(
        self,
        session: SustainedUseSession,
    ) -> Path:
        """Create session.json exactly once for a new Q.6 run."""

        if not isinstance(session, SustainedUseSession):
            raise SustainedUseRepositoryError(
                "session must be a SustainedUseSession",
            )

        archived = self._archive_path(
            session.run_id,
        )

        if archived.exists():
            raise SustainedUseRepositoryError(
                "sustained-use run is already archived: "
                f"{archived}",
            )

        if self.session_path.exists():
            raise SustainedUseRepositoryError(
                "sustained-use session already exists: "
                f"{self.session_path}",
            )

        try:
            write_json_atomic(
                self.session_path,
                session.to_dict(),
            )
        except OSError as error:
            raise SustainedUseRepositoryError(
                "unable to create sustained-use session: "
                f"{self.session_path}",
            ) from error

        return self.session_path

    def session(self) -> SustainedUseSession:
        """Load and validate session.json."""

        if not self.session_path.exists():
            raise SustainedUseSampleNotFoundError(
                "sustained-use session was not found: "
                f"{self.session_path}",
            )

        return self._load_session(
            self.session_path,
        )

    def update_session(
        self,
        session: SustainedUseSession,
    ) -> Path:
        """Update lifecycle state without changing the run boundary."""

        if not isinstance(session, SustainedUseSession):
            raise SustainedUseRepositoryError(
                "session must be a SustainedUseSession",
            )

        current = self.session()

        immutable_fields = (
            "run_id",
            "git_commit",
            "started_at",
            "scheduled_end_at",
            "duration_seconds",
            "interval_seconds",
            "expected_sample_count",
            "expected_running_containers",
            "schema_version",
        )

        changed = tuple(
            field
            for field in immutable_fields
            if getattr(current, field) != getattr(session, field)
        )

        if changed:
            raise SustainedUseRepositoryError(
                "session boundary fields cannot change: "
                + ", ".join(changed)
            )

        if current.status != "active":
            raise SustainedUseRepositoryError(
                "only an active sustained-use session can be updated",
            )

        if session.status == "active":
            raise SustainedUseRepositoryError(
                "session update must transition out of active status",
            )

        try:
            write_json_atomic(
                self.session_path,
                session.to_dict(),
            )
        except OSError as error:
            raise SustainedUseRepositoryError(
                "unable to update sustained-use session: "
                f"{self.session_path}",
            ) from error

        return self.session_path

    def archive_session(
        self,
        session: SustainedUseSession,
    ) -> Path:
        """Move one terminal run into its immutable archive."""

        if not isinstance(
            session,
            SustainedUseSession,
        ):
            raise SustainedUseRepositoryError(
                "session must be a SustainedUseSession",
            )

        current = self.session()

        if current != session:
            raise SustainedUseRepositoryError(
                "archive session does not match current session",
            )

        if session.status == "active":
            raise SustainedUseRepositoryError(
                "active sustained-use session cannot be archived",
            )

        archive_path = self._archive_path(
            session.run_id,
        )

        try:
            archive_path.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as error:
            raise SustainedUseRepositoryError(
                "unable to create sustained-use archive: "
                f"{archive_path}",
            ) from error

        moves = (
            (
                self.history_directory,
                archive_path / "history",
                False,
            ),
            (
                self.latest_path,
                archive_path / "latest.json",
                False,
            ),
            (
                self.session_path,
                archive_path / "session.json",
                True,
            ),
        )

        for source, destination, required in moves:
            source_exists = source.exists()
            destination_exists = destination.exists()

            if source_exists and destination_exists:
                raise SustainedUseRepositoryError(
                    "archive source and destination both exist: "
                    f"{source} -> {destination}",
                )

            if not source_exists:
                if destination_exists:
                    continue

                if required:
                    raise SustainedUseRepositoryError(
                        "required archive source is missing: "
                        f"{source}",
                    )

                continue

            try:
                source.rename(
                    destination,
                )
            except OSError as error:
                raise SustainedUseRepositoryError(
                    "unable to archive sustained-use evidence: "
                    f"{source} -> {destination}",
                ) from error

        archived_session_path = (
            archive_path / "session.json"
        )

        archived_session = self._load_session(
            archived_session_path,
        )

        if archived_session != session:
            raise SustainedUseRepositoryError(
                "archived session failed identity validation",
            )

        return archive_path

    def save(
        self,
        sample: SustainedUseSample,
    ) -> Path:
        """Persist one immutable sample and update latest.json."""

        if not isinstance(sample, SustainedUseSample):
            raise SustainedUseRepositoryError(
                "sample must be a SustainedUseSample",
            )

        snapshot_path = self._snapshot_path(sample)

        if snapshot_path.exists():
            raise SustainedUseRepositoryError(
                "sustained-use sample already exists: "
                f"{snapshot_path}",
            )

        payload = sample.to_dict()

        try:
            write_json_atomic(
                snapshot_path,
                payload,
            )
        except OSError as error:
            raise SustainedUseRepositoryError(
                "unable to persist sustained-use sample: "
                f"{snapshot_path}",
            ) from error

        try:
            write_json_atomic(
                self.latest_path,
                payload,
            )
        except OSError as error:
            raise SustainedUseRepositoryError(
                "sample persisted but latest sample could not "
                f"be updated: {self.latest_path}",
            ) from error

        return snapshot_path

    def latest(self) -> SustainedUseSample:
        """Load and validate the latest sample."""

        if not self.latest_path.exists():
            raise SustainedUseSampleNotFoundError(
                "latest sustained-use sample was not found: "
                f"{self.latest_path}",
            )

        return self._load(
            self.latest_path,
        )

    def history(
        self,
        limit: int = 25,
    ) -> tuple[SustainedUseSample, ...]:
        """Load immutable history newest first."""

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit <= 0
        ):
            raise SustainedUseRepositoryError(
                "limit must be a positive integer",
            )

        if not self.history_directory.exists():
            return ()

        if not self.history_directory.is_dir():
            raise SustainedUseRepositoryError(
                "sustained-use history path is not a directory: "
                f"{self.history_directory}",
            )

        try:
            paths = tuple(
                sorted(
                    self.history_directory.glob("*.json"),
                    reverse=True,
                )[:limit]
            )
        except OSError as error:
            raise SustainedUseRepositoryError(
                "unable to list sustained-use history: "
                f"{self.history_directory}",
            ) from error

        return tuple(
            self._load(path)
            for path in paths
        )

    def _snapshot_path(
        self,
        sample: SustainedUseSample,
    ) -> Path:
        filename = (
            sample.generated_at.replace(":", "-")
            + ".json"
        )

        return self.history_directory / filename

    def _load(
        self,
        path: Path,
    ) -> SustainedUseSample:
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)
        except FileNotFoundError as error:
            raise SustainedUseSampleNotFoundError(
                f"sustained-use sample was not found: {path}",
            ) from error
        except PermissionError as error:
            raise SustainedUseRepositoryError(
                f"sustained-use sample is not readable: {path}",
            ) from error
        except json.JSONDecodeError as error:
            raise SustainedUseRepositoryError(
                "sustained-use sample contains invalid JSON: "
                f"{path}",
            ) from error
        except OSError as error:
            raise SustainedUseRepositoryError(
                f"unable to read sustained-use sample: {path}",
            ) from error

        if not isinstance(payload, Mapping):
            raise SustainedUseRepositoryError(
                "sustained-use sample must contain an object: "
                f"{path}",
            )

        try:
            return SustainedUseSample.from_dict(
                payload,
            )
        except SustainedUseModelError as error:
            raise SustainedUseRepositoryError(
                f"sustained-use sample is invalid: {path}: {error}",
            ) from error

    def _load_session(
        self,
        path: Path,
    ) -> SustainedUseSession:
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)
        except FileNotFoundError as error:
            raise SustainedUseSampleNotFoundError(
                f"sustained-use session was not found: {path}",
            ) from error
        except PermissionError as error:
            raise SustainedUseRepositoryError(
                f"sustained-use session is not readable: {path}",
            ) from error
        except json.JSONDecodeError as error:
            raise SustainedUseRepositoryError(
                "sustained-use session contains invalid JSON: "
                f"{path}",
            ) from error
        except OSError as error:
            raise SustainedUseRepositoryError(
                f"unable to read sustained-use session: {path}",
            ) from error

        if not isinstance(payload, Mapping):
            raise SustainedUseRepositoryError(
                "sustained-use session must contain an object: "
                f"{path}",
            )

        try:
            return SustainedUseSession.from_dict(
                payload,
            )
        except SustainedUseModelError as error:
            raise SustainedUseRepositoryError(
                f"sustained-use session is invalid: {path}: {error}",
            ) from error
