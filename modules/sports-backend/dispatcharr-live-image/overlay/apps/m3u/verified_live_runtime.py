"""Server-held, default-off dependency wiring for verified live playback."""

from __future__ import annotations

import os
import stat


class VerifiedLiveConfigurationError(RuntimeError):
    """Verified live dependencies are missing or unsafe."""


def _scope_key_from_file(path: str) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            status = os.fstat(descriptor)
            if not stat.S_ISREG(status.st_mode) or status.st_size != 32:
                raise ValueError("invalid key file")
            key = os.read(descriptor, 33)
            if len(key) != 32:
                raise ValueError("invalid key length")
            return key
        finally:
            os.close(descriptor)
    except Exception:
        raise VerifiedLiveConfigurationError(
            "Verified live scope key unavailable") from None


def build_verified_live_dependencies(environ=None):
    """Return classifier and policy only when the complete strict mode is set.

    No request field or Redis alias can supply an origin, bearer token, or HMAC
    key. `off` is the only default. A partial strict configuration fails startup.
    """
    settings = os.environ if environ is None else environ
    mode = settings.get("ATLAS_VERIFIED_LIVE_MODE", "off")
    if mode == "off":
        return None, None
    if mode != "strict":
        raise VerifiedLiveConfigurationError("Verified live mode invalid")
    origin = settings.get("ATLAS_SPORTS_POLICY_ORIGIN", "")
    token = settings.get("ATLAS_SPORTS_LIVE_POLICY_TOKEN", "")
    key_path = settings.get("ATLAS_VERIFIED_LIVE_SCOPE_KEY_FILE", "")
    if not all(isinstance(value, str) and value for value in
               (origin, token, key_path)):
        raise VerifiedLiveConfigurationError(
            "Verified live authority configuration incomplete")
    key = _scope_key_from_file(key_path)
    try:
        from apps.m3u.atlas_channel_classification import AtlasManagedChannelClient
        from apps.m3u.atlas_policy_claims import AtlasPolicyClaimClient
        from apps.m3u.atlas_verified_policy_adapter import AtlasVerifiedPolicyAdapter
        from apps.m3u.provider_capacity_observation import XtreamCapacityReader
        from apps.m3u.strict_effective_credentials import strict_effective_credentials

        classifier = AtlasManagedChannelClient(origin=origin, token=token)
        policy = AtlasVerifiedPolicyAdapter(
            claim_client=AtlasPolicyClaimClient(origin=origin, token=token),
            capacity_reader=XtreamCapacityReader(),
            transformed_credentials=strict_effective_credentials,
            scope_key=key,
        )
        return classifier, policy
    except Exception:
        # Constructors and transport implementations must not reveal secrets.
        raise VerifiedLiveConfigurationError(
            "Verified live authority configuration unavailable") from None
