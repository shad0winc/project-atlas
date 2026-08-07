from __future__ import annotations

import errno
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


SPORTS_SRC_DIR = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "sports"
    / "src"
)

if str(SPORTS_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SPORTS_SRC_DIR))

import recordings as sports_recordings  # noqa: E402


NOW = datetime(2026, 8, 7, tzinfo=timezone.utc)


def _recording() -> dict[str, Any]:
    return {
        "id": "recording-test",
        "status": "pending",
    }


def _launch_result(*, started: bool) -> dict[str, Any]:
    return {
        "pid": 4321,
        "process_start_time": 987654,
        "log_file": "/tmp/recording.log",
        "output_file": "/tmp/recording.mkv",
        "recorder_mode": "ffmpeg",
        "partial_file": "/tmp/recording.mkv.part",
        "exit_file": "/tmp/recording.exit",
        "command": ["ffmpeg"],
        "started": started,
    }


def _configure_pending_launch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    started: bool,
) -> None:
    monkeypatch.setattr(
        sports_recordings,
        "load_recordings",
        lambda: {"recording-test": _recording()},
    )
    monkeypatch.setattr(
        sports_recordings,
        "recording_status",
        lambda recording, now: "recording",
    )
    monkeypatch.setattr(
        sports_recordings,
        "launch_recording",
        lambda recording: _launch_result(started=started),
    )


def _enospc_write(recordings: dict[str, dict[str, Any]]) -> None:
    raise OSError(errno.ENOSPC, "No space left on device")


def test_registry_enospc_stops_only_new_exact_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_pending_launch(monkeypatch, started=True)
    stop_calls: list[tuple[int, int | None]] = []

    def stop_recording(
        pid: int,
        timeout_seconds: int = 10,
        expected_start_time: int | None = None,
    ) -> bool:
        stop_calls.append((pid, expected_start_time))
        return True

    monkeypatch.setattr(
        sports_recordings,
        "write_recordings",
        _enospc_write,
    )
    monkeypatch.setattr(
        sports_recordings,
        "stop_recording",
        stop_recording,
    )

    with pytest.raises(OSError) as exc_info:
        sports_recordings.update_recording_statuses(NOW)

    assert exc_info.value.errno == errno.ENOSPC
    assert stop_calls == [(4321, 987654)]


def test_registry_enospc_never_stops_adopted_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_pending_launch(monkeypatch, started=False)
    stop_calls: list[tuple[int, int | None]] = []

    def stop_recording(
        pid: int,
        timeout_seconds: int = 10,
        expected_start_time: int | None = None,
    ) -> bool:
        stop_calls.append((pid, expected_start_time))
        return True

    monkeypatch.setattr(
        sports_recordings,
        "write_recordings",
        _enospc_write,
    )
    monkeypatch.setattr(
        sports_recordings,
        "stop_recording",
        stop_recording,
    )

    with pytest.raises(OSError) as exc_info:
        sports_recordings.update_recording_statuses(NOW)

    assert exc_info.value.errno == errno.ENOSPC
    assert stop_calls == []


def test_failed_exact_identity_compensation_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_pending_launch(monkeypatch, started=True)

    monkeypatch.setattr(
        sports_recordings,
        "write_recordings",
        _enospc_write,
    )
    monkeypatch.setattr(
        sports_recordings,
        "stop_recording",
        lambda pid, timeout_seconds=10, expected_start_time=None: False,
    )

    with pytest.raises(
        RuntimeError,
        match="exact-identity compensation was incomplete",
    ) as exc_info:
        sports_recordings.update_recording_statuses(NOW)

    assert isinstance(exc_info.value.__cause__, OSError)
    assert exc_info.value.__cause__.errno == errno.ENOSPC


def test_write_recordings_enospc_preserves_registry_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = tmp_path / "recordings.json"
    registry.write_text('{"stable": true}\n', encoding="utf-8")
    temporary = registry.with_suffix(".tmp")
    original_write_text = Path.write_text

    def write_text(
        self: Path,
        data: str,
        *args: Any,
        **kwargs: Any,
    ) -> int:
        if self == temporary:
            original_write_text(
                self,
                "partial",
                encoding="utf-8",
            )
            raise OSError(errno.ENOSPC, "No space left on device")

        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(
        sports_recordings,
        "RECORDINGS_FILE",
        registry,
    )
    monkeypatch.setattr(Path, "write_text", write_text)

    with pytest.raises(OSError) as exc_info:
        sports_recordings.write_recordings({"replacement": {}})

    assert exc_info.value.errno == errno.ENOSPC
    assert registry.read_text(encoding="utf-8") == '{"stable": true}\n'
    assert not temporary.exists()
