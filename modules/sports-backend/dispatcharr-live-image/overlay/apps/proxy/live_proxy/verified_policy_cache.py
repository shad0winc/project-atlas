"""Short-lived per-viewer policy result; Redis attestation still runs per batch."""

from __future__ import annotations

import time

from apps.m3u.reservation_ledger import ReservationSpec


class VerifiedPolicyCache:
    __slots__ = ("_builder", "_clock", "_ttl", "_identity", "_spec", "_at")

    def __init__(self, builder, *, ttl_seconds=20.0, clock=time.monotonic):
        if (not callable(builder) or type(ttl_seconds) not in (int, float)
            or not 0 < ttl_seconds <= 30 or not callable(clock)):
            raise ValueError("Invalid verified policy cache")
        self._builder = builder
        self._clock = clock
        self._ttl = ttl_seconds
        self._identity = None
        self._spec = None
        self._at = None

    def __repr__(self):
        return "<VerifiedPolicyCache>"

    def build(self, stream_id, profile_id, account_id, owner_lease):
        identity = (stream_id, profile_id, account_id, owner_lease)
        now = self._clock()
        if (self._spec is not None and self._identity == identity
            and self._at is not None and 0 <= now - self._at < self._ttl):
            return self._spec
        # Never serve the previous result after an attempted refresh fails.
        self._spec = None
        self._identity = None
        self._at = None
        spec = self._builder(*identity)
        if not isinstance(spec, ReservationSpec) or spec.mode != "live":
            raise ValueError("Verified policy response invalid")
        self._spec = spec
        self._identity = identity
        self._at = now
        return spec
