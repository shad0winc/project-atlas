from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEDIA_COMPOSE = ROOT / "docker-compose.yml"
INGRESS_COMPOSE = ROOT / "stack" / "ingress.yml"
CADDY_SITE = ROOT / "infra" / "caddy" / "sites" / "atlas.caddy"


def _service_block(content: str, service: str, next_service: str) -> str:
    start = content.index(f"  {service}:\n")
    end = content.index(f"\n  {next_service}:\n", start)
    return content[start:end]


def test_jellyfin_joins_public_ingress_without_exposing_caddy_to_identity():
    media = MEDIA_COMPOSE.read_text(encoding="utf-8")
    ingress = INGRESS_COMPOSE.read_text(encoding="utf-8")

    jellyfin = _service_block(media, "jellyfin", "prowlarr")
    caddy = ingress[
        ingress.index("  caddy:\n"):
        ingress.rindex("\nnetworks:\n")
    ]

    assert "      - atlas-ingress\n" in jellyfin
    assert "      - atlas-identity\n" in jellyfin
    assert "      - atlas-ingress\n" in caddy
    assert "      - atlas-identity\n" not in caddy

    assert "  atlas-ingress:\n" in media
    assert "    name: atlas-ingress\n" in media
    assert "    external: true\n" in media


def test_jellyfin_public_playback_url_is_https_and_non_secret():
    ingress = INGRESS_COMPOSE.read_text(encoding="utf-8")

    assert (
        '      ATLAS_JELLYFIN_PUBLIC_URL: '
        '"https://jellyfin.shadowinc.co"\n'
    ) in ingress
    assert "ATLAS_JELLYFIN_PUBLIC_URL: http://" not in ingress
    assert "192.168.30.213" not in ingress


def test_caddy_exposes_only_the_jellyfin_service_on_playback_host():
    caddy = CADDY_SITE.read_text(encoding="utf-8")

    start = caddy.index("jellyfin.shadowinc.co {\n")
    jellyfin_host = caddy[start:]

    assert "reverse_proxy jellyfin:8096" in jellyfin_host
    assert "atlas-api:8000" not in jellyfin_host
    assert "atlas-portal:3000" not in jellyfin_host
    assert "192.168.30.213" not in jellyfin_host
