"""Shared filesystem layout for Atlas identity services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IdentityPaths:
    """Resolved runtime paths used by Atlas identity services."""

    root: Path

    @property
    def invitations_root(self) -> Path:
        return self.root / "invitations"

    @property
    def invitation_registry(self) -> Path:
        return self.invitations_root / "invitations.json"

    @property
    def active_invitations(self) -> Path:
        return self.invitations_root / "active"

    @property
    def completed_invitations(self) -> Path:
        return self.invitations_root / "completed"

    @property
    def revoked_invitations(self) -> Path:
        return self.invitations_root / "revoked"

    def initialize(self) -> None:
        """Create the durable identity directory structure."""
        for directory in (
            self.active_invitations,
            self.completed_invitations,
            self.revoked_invitations,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def default_identity_paths() -> IdentityPaths:
    """Return identity paths from the shared Atlas environment."""
    root = Path(
        os.getenv("ATLAS_IDENTITY_DIR", "/mnt/storage/configs/atlas/identity")
    ).expanduser()
    return IdentityPaths(root.resolve())
