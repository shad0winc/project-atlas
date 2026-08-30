from __future__ import annotations

import pytest

from atlas.downloads.job_ids import is_opaque_job_id, opaque_job_id

def test_opaque_job_id_is_stable_and_keyed() -> None:
    torrent_hash = "0123456789abcdef0123456789abcdef01234567"
    first = opaque_job_id(torrent_hash, "first-secret")
    same = opaque_job_id(torrent_hash.upper(), "first-secret")
    different = opaque_job_id(torrent_hash, "second-secret")
    assert first == same
    assert first != different
    assert first.startswith("dl_")
    assert is_opaque_job_id(first)
    assert torrent_hash not in first

@pytest.mark.parametrize("key", ["", "CHANGE_ME"])
def test_opaque_job_id_rejects_unconfigured_key(key: str) -> None:
    with pytest.raises(ValueError):
        opaque_job_id("0123456789abcdef", key)

@pytest.mark.parametrize("value", [None, "", "dl_", "bad", "dl_" + ("g" * 32), "dl_" + ("a" * 31)])
def test_opaque_job_id_validation_is_strict(value: object) -> None:
    assert not is_opaque_job_id(value)
