"""Bounded effective Xtream identity for a future verified live owner.

Verified playback must build its URL from this returned tuple. The legacy
helper may silently fall back after a rewrite error, so its output cannot be
used as independent proof of the transformed login.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from apps.m3u.verified_live_policy import VerifiedLivePolicyUnavailable

TRANSFORM_TIMEOUT_SECONDS = 0.1


def _valid_origin(value: str) -> bool:
    parsed = urlsplit(value)
    return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and not parsed.query and not parsed.fragment)


def strict_effective_credentials(account, profile) -> tuple[str, str, str]:
    try:
        if (account.account_type != "XC" or account.is_active is not True
                or profile.m3u_account_id != account.id or profile.is_active is not True):
            raise VerifiedLivePolicyUnavailable("Verified playback identity unavailable")
        from core.xtream_codes import normalize_server_url

        server_url = normalize_server_url(account.server_url)
        username, password = account.username, account.password
        if (not all(isinstance(item, str) and item for item in (server_url, username, password))
                or not _valid_origin(server_url)):
            raise VerifiedLivePolicyUnavailable("Verified playback identity unavailable")
        search, replacement = profile.search_pattern, profile.replace_pattern
        if bool(search) != bool(replacement):
            raise VerifiedLivePolicyUnavailable("Incomplete profile rewrite")
        if not search:
            return server_url, username, password
        if not isinstance(search, str) or not isinstance(replacement, str):
            raise VerifiedLivePolicyUnavailable("Invalid profile rewrite")

        import regex

        # Match the running helper's JS-style replacement conversion and
        # synthetic stream shape, with a bounded search and no secret logging.
        safe_replace = regex.sub(r"\$<([^>]+)>", r"\\g<\1>", replacement)
        safe_replace = regex.sub(r"\$(\d+)", r"\\\1", safe_replace)
        sample = f"{server_url.rstrip('/')}/live/{username}/{password}/1234.ts"
        transformed, substitutions = regex.subn(
            search, safe_replace, sample, timeout=TRANSFORM_TIMEOUT_SECONDS,
        )
        if substitutions < 1:
            raise VerifiedLivePolicyUnavailable("Profile rewrite did not match")
        parsed = urlsplit(transformed)
        parts = [part for part in parsed.path.split("/") if part]
        if (not _valid_origin(f"{parsed.scheme}://{parsed.netloc}")
                or len(parts) < 4 or parts[-4] != "live" or parts[-1] != "1234.ts"
                or not parts[-3] or not parts[-2]):
            raise VerifiedLivePolicyUnavailable("Transformed playback identity unavailable")
        base_path = "/" + "/".join(parts[:-4]) if len(parts) > 4 else ""
        origin = f"{parsed.scheme}://{parsed.netloc}{base_path}"
        if not _valid_origin(origin) or parsed.query or parsed.fragment:
            raise VerifiedLivePolicyUnavailable("Transformed playback identity unavailable")
        return origin, parts[-3], parts[-2]
    except VerifiedLivePolicyUnavailable:
        raise
    except Exception:
        # Regex and URL errors can contain credentials or profile patterns.
        raise VerifiedLivePolicyUnavailable("Verified playback identity unavailable") from None


def verified_live_stream_url(stream, credentials: tuple[str, str, str]) -> str:
    """Construct the owner's upstream URL from the same attested identity."""
    try:
        if (not isinstance(credentials, tuple) or len(credentials) != 3
                or not all(isinstance(item, str) and item for item in credentials)
                or not _valid_origin(credentials[0])):
            raise VerifiedLivePolicyUnavailable("Verified playback identity unavailable")
        stream_id = str(stream.stream_id)
        if not re.fullmatch(r"[0-9]+", stream_id):
            raise VerifiedLivePolicyUnavailable("Verified stream identity unavailable")
        return f"{credentials[0].rstrip('/')}/live/{credentials[1]}/{credentials[2]}/{stream_id}.ts"
    except VerifiedLivePolicyUnavailable:
        raise
    except Exception:
        raise VerifiedLivePolicyUnavailable("Verified stream identity unavailable") from None
