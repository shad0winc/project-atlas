"""Process-local maintenance credentials bound to active refresh sessions.

Only hashes of opaque browser credentials are retained. Refresh rotation, logout,
subject revocation, API restart and expiry invalidate maintenance authorization.
"""
from dataclasses import dataclass
import hashlib
from threading import RLock
import secrets
import time
from collections.abc import Callable


@dataclass(frozen=True)
class Binding:
    subject: str
    refresh_id: str
    refresh_expires: int
    expires: int


class MaintenanceSessions:
    def __init__(self, active: Callable[[str, str, int], bool], *, clock=None):
        self.active = active
        self.clock = clock or (lambda: int(time.time()))
        self.browser: dict[str, Binding] = {}
        self.access: dict[str, Binding] = {}
        self.media: dict[str, Binding] = {}
        self.media_salt = secrets.token_bytes(32)
        self.lock = RLock()

    def _prune(self):
        now = self.clock()
        for table in (self.browser, self.access, self.media):
            for key, binding in list(table.items()):
                if binding.expires <= now or not self.active(binding.subject, binding.refresh_id, binding.refresh_expires):
                    table.pop(key, None)

    def bind_access(self, token_id: str, subject: str, expires: int, refresh_id: str, refresh_expires: int):
        with self.lock:
            self._prune()
            self.access[token_id] = Binding(subject, refresh_id, refresh_expires, expires)

    def access_active(self, token_id: str, subject: str) -> bool:
        with self.lock:
            self._prune()
            binding = self.access.get(token_id)
            return binding is not None and binding.subject == subject

    def issue_browser(self, subject: str, refresh_id: str, refresh_expires: int) -> tuple[str, int]:
        with self.lock:
            self._prune()
            if not self.active(subject, refresh_id, refresh_expires):
                raise ValueError('Maintenance session is inactive.')
            value = secrets.token_urlsafe(32)
            lifetime = min(900, refresh_expires - self.clock())
            if lifetime <= 0:
                raise ValueError('Maintenance session is expired.')
            self.browser[hashlib.sha256(value.encode()).hexdigest()] = Binding(
                subject, refresh_id, refresh_expires, self.clock() + lifetime)
            return value, lifetime

    def browser_subject(self, value: str) -> str | None:
        if not isinstance(value, str) or len(value) != 43:
            return None
        with self.lock:
            self._prune()
            binding = self.browser.get(hashlib.sha256(value.encode()).hexdigest())
            return binding.subject if binding is not None else None

    def issue_media(self, access_id: str, subject: str) -> str:
        with self.lock:
            self._prune()
            binding = self.access.get(access_id)
            if binding is None or binding.subject != subject:
                raise ValueError('Maintenance media session is inactive.')
            # One opaque signed-claim reference per access session. It exposes
            # neither the access ID nor the refresh ID and cannot authorize alone.
            reference = hashlib.sha256(self.media_salt + access_id.encode()).hexdigest()
            self.media[reference] = binding
            return reference

    def media_subject(self, reference: str) -> str | None:
        if not isinstance(reference, str) or len(reference) != 64:
            return None
        with self.lock:
            self._prune()
            binding = self.media.get(reference)
            return binding.subject if binding is not None else None
