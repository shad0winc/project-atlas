"""Privacy contract for temporary playback-origin diagnostics."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "infra" / "caddy" / "sites" / "atlas.caddy"


def _playback_site() -> str:
    source = SITE.read_text(encoding="utf-8")
    start = source.index("playback.shadowinc.co {\n")
    end = source.index(
        "\n# Jellyfin is the playback/transcoding backend",
        start,
    )
    return source[start:end]


def _logging_block() -> str:
    site = _playback_site()
    match = re.search(
        r"(?m)^        log \{\n(?P<body>.*?)"
        r"^        \}\n",
        site,
        re.DOTALL,
    )
    assert match is not None, "Playback diagnostic log is absent."
    return match.group("body")


def test_playback_log_excludes_sensitive_request_material() -> None:
    log = _logging_block()

    assert "format filter {" in log
    assert "request delete" in log
    assert "resp_headers delete" in log
    assert "user_id delete" in log
    assert "err_id delete" in log
    assert "err_trace delete" in log
    assert "wrap json" in log

    assert "log_credentials" not in _playback_site()
    assert "import atlas_access_log" not in _playback_site()


def test_playback_diagnostic_uses_separate_short_retention() -> None:
    log = _logging_block()

    assert (
        "/var/log/caddy/atlas-playback-diagnostic.log"
        in log
    )
    assert "roll_size 1MiB" in log
    assert "roll_keep 2" in log
    assert "roll_keep_for 24h" in log


def test_playback_diagnostic_does_not_change_media_routing() -> None:
    site = _playback_site()

    assert "@playback_media path /videos/*" in site
    assert "forward_auth atlas-api:8000" in site
    assert "uri /_atlas/playback/authorize" in site
    assert "reverse_proxy jellyfin:8096" in site

    assert (
        'header Access-Control-Allow-Origin '
        '"https://atlas.shadowinc.co"'
    ) in site
    assert (
        'header Access-Control-Allow-Credentials "true"'
    ) in site

    assert "response_header_timeout" not in site
    assert "read_timeout" not in site
    assert "write_timeout" not in site
    assert "flush_interval" not in site


def test_playback_diagnostic_uses_only_fixed_request_type_labels() -> None:
    site = _playback_site()
    log = _logging_block()

    expected = {
        "HLS_PLAYLIST": (
            r"@playback_diagnostic_playlist "
            r"path_regexp ^/videos/[^/]+/.*\.m3u8$"
        ),
        "HLS_SEGMENT": (
            r"@playback_diagnostic_segment "
            r"path_regexp ^/videos/[^/]+/.*\.(ts|m4s|mp4)$"
        ),
        "PLAYBACK_BOOTSTRAP": (
            "@playback_diagnostic_bootstrap "
            "path /_atlas/playback/bootstrap"
        ),
    }

    for label, matcher in expected.items():
        assert matcher in site
        matcher_name = matcher.split()[0]
        assert (
            f"log_append {matcher_name} "
            f"playback_request_type {label}"
        ) in site

    assert site.count(
        "log_append @playback_diagnostic_"
    ) == len(expected)

    # Classification must not preserve request.uri or any other
    # portion of the request object in the diagnostic output.
    assert "request delete" in log
    assert "resp_headers delete" in log
    assert "log_credentials" not in site
    assert "import atlas_access_log" not in site
    assert "log_append request" not in site
    assert "log_append uri" not in site
