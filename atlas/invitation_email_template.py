"""Validated plain-text invitation copy, persisted only by the identity writer."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Mapping

from atlas.identity import IdentityPaths

DEFAULT_TEMPLATE = {
    "subject": "You're invited to Project Atlas",
    "heading": "We saved you a seat.",
    "welcome": (
        "Welcome to Project Atlas, your home for all things media. "
        "Explore movies, shows, and sports. Game servers and the latest "
        "tech/gaming news are on the horizon."
    ),
    "instructions": "Use the button below to create your account. We'd love to have you join us.",
    "button_label": "Accept invitation",
}
FIELD_LIMITS = {"subject": 160, "heading": 100, "welcome": 1200,
                "instructions": 500, "button_label": 40}
MULTILINE_FIELDS = {"welcome", "instructions"}


class InvitationTemplateError(ValueError):
    """Invitation copy is invalid or its stored document cannot be read."""


def validate_template(value: Mapping[str, object]) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != set(DEFAULT_TEMPLATE):
        raise InvitationTemplateError("Provide exactly the five invitation text fields.")
    result = {}
    for name, limit in FIELD_LIMITS.items():
        text = value[name]
        if not isinstance(text, str):
            raise InvitationTemplateError(f"{name} must be text.")
        allowed = "\n\t" if name in MULTILINE_FIELDS else ""
        if any((ord(char) < 32 or ord(char) == 127) and char not in allowed for char in text):
            raise InvitationTemplateError(f"{name} contains unsupported control characters.")
        text = text.strip()
        if not text or len(text) > limit:
            raise InvitationTemplateError(f"{name} must contain between 1 and {limit} characters.")
        result[name] = text
    return result


def template_document(template: Mapping[str, object]) -> dict:
    return {"template": validate_template(template), "defaults": dict(DEFAULT_TEMPLATE),
            "limits": dict(FIELD_LIMITS)}


class InvitationEmailTemplateStore:
    def __init__(self, paths: IdentityPaths):
        self.path = paths.invitations_root / "email-template.json"

    def load(self) -> dict[str, str]:
        # Reading defaults never initializes identity or password-recovery storage.
        if not self.path.exists() and not self.path.is_symlink():
            return dict(DEFAULT_TEMPLATE)
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 32768:
                    raise InvitationTemplateError("Invitation template document is unsafe.")
                raw = stream.read(32769)
            data = json.loads(raw)
            if not isinstance(data, dict) or set(data) != {"schema_version", "template"} or data["schema_version"] != 1:
                raise InvitationTemplateError("Unsupported invitation template document.")
            return validate_template(data["template"])
        except (OSError, UnicodeError, ValueError) as error:
            raise InvitationTemplateError("Invitation email settings are unavailable.") from error

    def save(self, template: Mapping[str, object]) -> dict[str, str]:
        normalized = validate_template(template)
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise InvitationTemplateError("Invitation template path must not be a link.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps({"schema_version": 1, "template": normalized}, ensure_ascii=False,
                          sort_keys=True, indent=2) + "\n").encode("utf-8")
        fd, temporary = tempfile.mkstemp(prefix=".email-template-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fchmod(stream.fileno(), 0o644)
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return normalized
