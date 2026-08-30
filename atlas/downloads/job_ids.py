from __future__ import annotations

import hashlib
import hmac

JOB_ID_PREFIX = "dl_"
JOB_ID_HEX_LENGTH = 32

def opaque_job_id(torrent_hash: str, key: str) -> str:
    normalized_hash = torrent_hash.strip().lower()
    if not normalized_hash:
        raise ValueError("torrent hash is required")
    if not key or key == "CHANGE_ME":
        raise ValueError("Downloads job-id key is not configured")
    digest = hmac.new(key.encode("utf-8"), normalized_hash.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{JOB_ID_PREFIX}{digest[:JOB_ID_HEX_LENGTH]}"

def is_opaque_job_id(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith(JOB_ID_PREFIX):
        return False
    suffix = value[len(JOB_ID_PREFIX):]
    return len(suffix) == JOB_ID_HEX_LENGTH and all(c in "0123456789abcdef" for c in suffix)
