from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "infra" / "caddy" / "sites" / "atlas.caddy"


def test_playback_origin_uses_internal_forward_auth() -> None:
    source = SITE.read_text(encoding="utf-8")
    assert "playback.shadowinc.co {" in source
    assert "forward_auth atlas-api:8000" in source
    assert "uri /_atlas/playback/authorize" in source
    assert "copy_headers X-Atlas-Jellyfin-Token" in source
    assert "reverse_proxy jellyfin:8096" in source
    assert (
        "header_up X-Emby-Token "
        "{http.request.header.X-Atlas-Jellyfin-Token}"
    ) in source
    assert "header_down -Access-Control-Allow-Origin" in source
    assert "header_down -Access-Control-Allow-Credentials" in source


def test_playback_origin_does_not_embed_jellyfin_secret() -> None:
    source = SITE.read_text(encoding="utf-8")
    assert "ATLAS_JELLYFIN_API_KEY" not in source
    assert "ApiKey=" not in source
    assert "api_key=" not in source


def test_private_authorize_route_is_not_publicly_handled() -> None:
    source = SITE.read_text(encoding="utf-8")
    assert "handle /_atlas/playback/authorize" not in source
    assert "handle /_atlas/playback/bootstrap" in source
