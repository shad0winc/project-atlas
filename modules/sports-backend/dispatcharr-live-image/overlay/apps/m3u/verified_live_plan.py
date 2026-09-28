"""Private owner plan; playback URL and reservation share one credential tuple."""

from dataclasses import dataclass

from apps.m3u.reservation_ledger import ReservationSpec


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedLivePlan:
    spec: ReservationSpec
    upstream_url: str
