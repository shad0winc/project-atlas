from __future__ import annotations

from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[3]

PRIVATE_API = (
    ROOT
    / "modules"
    / "sports"
    / "src"
    / "private_api.py"
)

LIVE_SOURCES = (
    ROOT
    / "modules"
    / "sports"
    / "src"
    / "live_sources.py"
)


def private_api_text() -> str:
    return PRIVATE_API.read_text(
        encoding="utf-8"
    )


def method_block(
    content: str,
    name: str,
    next_name: str | None,
) -> str:
    start = content.index(
        f"    def {name}"
    )

    if next_name is None:
        return content[start:]

    end = content.index(
        f"    def {next_name}",
        start + 1,
    )

    return content[
        start:end
    ]


def test_live_source_resource_is_distinct() -> None:
    content = private_api_text()

    assert (
        '"/internal/v1/live-sources"'
        in content
    )

    assert (
        '"/internal/v1/live-sources/"'
        in content
    )

    assert (
        '"/internal/v1/sources"'
        in content
    )


def test_get_live_sources_uses_safe_summary() -> None:
    content = private_api_text()

    block = method_block(
        content,
        "do_GET(self) -> None:",
        "do_POST(self) -> None:",
    )

    start = block.index(
        'if parsed.path == "/internal/v1/live-sources":'
    )

    end = block.index(
        'if parsed.path == "/internal/v1/sources":',
        start,
    )

    route = block[
        start:end
    ]

    assert (
        "default_live_source_registry"
        in route
    )

    assert (
        "safe_source_summary"
        in route
    )

    assert "stream_url" not in route


def test_post_live_source_is_create_only_and_safe() -> None:
    content = private_api_text()

    block = method_block(
        content,
        "do_POST(self) -> None:",
        "do_DELETE(self) -> None:",
    )

    start = block.index(
        'if parsed.path == "/internal/v1/live-sources":'
    )

    end = block.index(
        'if parsed.path == "/internal/v1/live-tv/bindings":',
        start,
    )

    route = block[
        start:end
    ]

    assert (
        "normalize_live_source"
        in route
    )

    assert (
        "registry.add("
        in route
    )

    assert (
        "sports_live_source_exists"
        in route
    )

    assert (
        "safe_source_summary"
        in route
    )

    assert (
        'payload["stream_url"]'
        not in route
    )


def test_delete_live_source_requires_auth() -> None:
    content = private_api_text()

    block = method_block(
        content,
        "do_DELETE(self) -> None:",
        None,
    )

    start = block.index(
        '"/internal/v1/live-sources/"'
    )

    next_route = block.index(
        '"/internal/v1/sources/"',
        start,
    )

    route = block[
        start:next_route
    ]

    assert "_require_auth()" in route

    assert (
        "default_live_source_registry"
        in route
    )

    assert (
        ".delete(source_id)"
        in route
    )


def test_writer_initializes_registry() -> None:
    content = private_api_text()

    assert (
        "default_live_source_registry().ensure()"
        in content
    )

    assert (
        "default_live_tv_binding_registry().ensure()"
        in content
    )


def test_safe_summary_does_not_expose_stream_url() -> None:
    content = LIVE_SOURCES.read_text(
        encoding="utf-8"
    )

    start = content.index(
        "def safe_source_summary("
    )

    body = content[
        start:
    ]

    assert '"stream_url"' not in body


def test_no_live_source_put_or_patch_route() -> None:
    content = private_api_text()

    for method in (
        "do_PUT",
        "do_PATCH",
    ):
        token = (
            f"    def {method}"
        )

        if token not in content:
            continue

        start = content.index(
            token
        )

        remainder = content[
            start:
        ]

        later_methods = [
            position
            for candidate in (
                "    def do_GET",
                "    def do_POST",
                "    def do_DELETE",
            )
            if (
                (
                    position
                    := remainder.find(
                        candidate,
                        1,
                    )
                )
                != -1
            )
        ]

        end = min(
            later_methods,
            default=len(remainder),
        )

        block = remainder[
            :end
        ]

        assert (
            "/internal/v1/live-sources"
            not in block
        )
