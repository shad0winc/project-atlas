"""Security contracts for the Atlas Request API runtime boundary."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE_COMPOSE = ROOT / "docker-compose.yml"
INGRESS_COMPOSE = ROOT / "stack" / "ingress.yml"


def _named_block(content: str, name: str) -> str:
    """Return one two-space-indented YAML mapping block."""

    lines = content.splitlines(keepends=True)
    marker = f"  {name}:\n"

    try:
        start = lines.index(marker)
    except ValueError as exc:
        raise AssertionError(
            f"two-space YAML block not found: {name}"
        ) from exc

    end = len(lines)

    for index in range(start + 1, len(lines)):
        line = lines[index]

        if (
            line.startswith("  ")
            and not line.startswith("    ")
            and line.rstrip().endswith(":")
        ):
            end = index
            break

    return "".join(lines[start:end])


def test_backend_network_is_declared_external_across_stacks() -> None:
    core = CORE_COMPOSE.read_text(encoding="utf-8")
    ingress = INGRESS_COMPOSE.read_text(encoding="utf-8")

    core_backend = _named_block(core, "atlas-backend")
    ingress_backend = _named_block(ingress, "atlas-backend")

    assert "    name: atlas-backend\n" in core_backend
    assert "    external: true\n" in core_backend

    assert "    name: atlas-backend\n" in ingress_backend
    assert "    external: true\n" in ingress_backend


def test_jellyseerr_joins_private_backend_without_losing_media_network() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    jellyseerr = _named_block(content, "jellyseerr")

    assert "      - atlas\n" in jellyseerr
    assert "      - atlas-backend\n" in jellyseerr


def test_ingress_api_has_narrow_request_runtime_access() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")
    api = _named_block(content, "api")

    assert "      - atlas-ingress\n" in api
    assert "      - atlas-backend\n" in api
    assert "      - atlas-identity\n" in api

    assert (
        "      - /mnt/storage/configs/atlas/runtime/requests:"
        "/mnt/storage/configs/atlas/runtime/requests:rw\n"
        in api
    )

    assert (
        '      ATLAS_REQUESTS_DIR: '
        '"/mnt/storage/configs/atlas/runtime/requests"\n'
        in api
    )

    assert (
        "      - /mnt/storage/configs/atlas/runtime:"
        "/mnt/storage/configs/atlas/runtime:rw\n"
        not in api
    )


def test_ingress_api_uses_internal_jellyseerr_dns_and_required_secret() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")
    api = _named_block(content, "api")

    assert (
        '      ATLAS_JELLYSEERR_URL: "http://jellyseerr:5055"\n'
        in api
    )

    assert (
        '      ATLAS_JELLYSEERR_API_KEY: '
        '"${ATLAS_JELLYSEERR_API_KEY:'
        '?ATLAS_JELLYSEERR_API_KEY is required}"\n'
        in api
    )

    assert "${ATLAS_JELLYSEERR_API_KEY:-" not in api


def test_public_ingress_services_do_not_join_private_backend() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")

    portal = _named_block(content, "portal")
    caddy = _named_block(content, "caddy")

    assert "atlas-backend" not in portal
    assert "atlas-backend" not in caddy
