"""Owner routing decision; no policy or transport failure falls back to legacy."""

from __future__ import annotations

from apps.m3u.atlas_channel_classification import AtlasManagedClassificationUnavailable


def owner_route(channel_uuid: str, *, classifier, verified_policy) -> str:
    """Return a route only after an authoritative classification response.

    The caller may use `legacy` only for explicit `managed: false`. A managed
    channel requires a configured trusted policy resolver before selecting or
    reserving any upstream stream. Errors propagate to a generic 503 response.
    """
    if classifier is None or not callable(getattr(classifier, "classify", None)):
        raise AtlasManagedClassificationUnavailable("Classification unavailable")
    try:
        managed = classifier.classify(channel_uuid)
    except AtlasManagedClassificationUnavailable:
        raise
    except Exception:
        raise AtlasManagedClassificationUnavailable("Classification unavailable") from None
    if type(managed) is not bool:
        raise AtlasManagedClassificationUnavailable("Classification invalid")
    if managed:
        if not callable(verified_policy):
            raise AtlasManagedClassificationUnavailable("Verified policy unavailable")
        return "verified"
    return "legacy"
