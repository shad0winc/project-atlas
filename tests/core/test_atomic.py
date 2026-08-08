"""Failure-contract tests for shared Atlas atomic persistence."""

from __future__ import annotations

import errno
import json
from pathlib import Path

import pytest

from atlas.atomic import (
    write_json_atomic,
    write_text_atomic,
)


def test_write_text_atomic_replaces_committed_content(
    tmp_path: Path,
) -> None:
    target = tmp_path / "state.txt"
    target.write_text("before\n", encoding="utf-8")

    write_text_atomic(target, "after\n")

    assert target.read_text(encoding="utf-8") == "after\n"
    assert (tmp_path / ".state.txt.tmp").exists() is False


def test_enospc_preserves_last_durable_state_and_removes_partial_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "state.txt"
    target.write_text("last-good\n", encoding="utf-8")
    temporary = tmp_path / ".state.txt.tmp"
    original_write_text = Path.write_text

    def fail_temporary_write(
        self: Path,
        content: str,
        *,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if self == temporary:
            original_write_text(
                self,
                "partial",
                encoding="utf-8",
            )
            raise OSError(
                errno.ENOSPC,
                "No space left on device",
            )

        return original_write_text(
            self,
            content,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    monkeypatch.setattr(Path, "write_text", fail_temporary_write)

    with pytest.raises(OSError) as captured:
        write_text_atomic(target, "replacement\n")

    assert captured.value.errno == errno.ENOSPC
    assert target.read_text(encoding="utf-8") == "last-good\n"
    assert temporary.exists() is False


def test_write_json_atomic_serializes_deterministically(
    tmp_path: Path,
) -> None:
    target = tmp_path / "state.json"

    write_json_atomic(
        target,
        {
            "zeta": 2,
            "alpha": 1,
        },
    )

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "alpha": 1,
        "zeta": 2,
    }
    assert target.read_text(encoding="utf-8") == (
        '{\n  "alpha": 1,\n  "zeta": 2\n}\n'
    )
